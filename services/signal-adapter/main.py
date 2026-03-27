import asyncio
import json
import math
import os
import struct
import time as _time
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import Any

import numpy as np

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, Header
from fastapi.middleware.cors import CORSMiddleware


async def verify_api_key(authorization: str | None = Header(None)):
    """Verify Bearer token for mutation endpoints. Skip if RUVIEW_API_KEY not set."""
    api_key = os.getenv("RUVIEW_API_KEY")
    if not api_key:
        return  # auth disabled when key not configured
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    if authorization[7:] != api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")

try:
    from .ws_manager import ConnectionManager
    from .csi_processor import CSIProcessor, ProcessedCSI, WelfordStats
    from .event_engine import EventEngine
    from .supabase_client import get_supabase
    from .fall_detector import FallDetector, extract_features as extract_fall_features
    from .notifier import Notifier, ConsoleBackend, WebSocketBackend, WebhookBackend
    from .mmwave_bridge import MmWaveBridge
except ImportError:
    from ws_manager import ConnectionManager
    from csi_processor import CSIProcessor, ProcessedCSI, WelfordStats
    from event_engine import EventEngine
    from supabase_client import get_supabase
    from fall_detector import FallDetector, extract_features as extract_fall_features
    from notifier import Notifier, ConsoleBackend, WebSocketBackend, WebhookBackend
    from mmwave_bridge import MmWaveBridge


load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

UDP_HOST = os.getenv("CSI_UDP_HOST", "0.0.0.0")
UDP_PORT = int(os.getenv("CSI_UDP_PORT", os.getenv("ESP_TARGET_PORT", "5005")))
DEFAULT_ZONES = [
    {
        "id": "zone-1001",
        "name": "Room 1001",
        "polygon": [
            {"x": 20, "y": 20},
            {"x": 210, "y": 20},
            {"x": 210, "y": 380},
            {"x": 20, "y": 380},
        ],
        "status": "active",
        "presenceCount": 0,
        "lastActivity": None,
    },
    {
        "id": "zone-1002",
        "name": "Room 1002",
        "polygon": [
            {"x": 210, "y": 20},
            {"x": 400, "y": 20},
            {"x": 400, "y": 380},
            {"x": 210, "y": 380},
        ],
        "status": "active",
        "presenceCount": 0,
        "lastActivity": None,
    },
    {
        "id": "zone-1003",
        "name": "Room 1003",
        "polygon": [
            {"x": 400, "y": 20},
            {"x": 590, "y": 20},
            {"x": 590, "y": 380},
            {"x": 400, "y": 380},
        ],
        "status": "active",
        "presenceCount": 0,
        "lastActivity": None,
    },
    {
        "id": "zone-1004",
        "name": "Room 1004",
        "polygon": [
            {"x": 590, "y": 20},
            {"x": 780, "y": 20},
            {"x": 780, "y": 380},
            {"x": 590, "y": 380},
        ],
        "status": "active",
        "presenceCount": 0,
        "lastActivity": None,
    },
]
DEVICE_POSITIONS = [
    (60, 330),    # Node 1 — A5 (1001호 좌하)
    (60, 80),     # Node 2 — A2 (1001호 좌상)
    (740, 30),    # Node 3 — H1 (1004호 우상)
    (650, 250),   # Node 4 — G4 (1004호 중간)
    (500, 80),    # Node 5 — F2 (1003호 근처)
    (350, 330),   # Node 6 — D5 (1002호 하단)
]
CSI_MAGIC = 0xC5110001
VITALS_MAGIC = 0xC5110002


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class KalmanSmooth:
    """Simple 1D Kalman filter for presenceCount smoothing.

    State: estimated presenceCount (float).
    Process noise Q allows gradual change; measurement noise R
    accounts for noisy CSI-based estimates.
    """

    def __init__(self, process_noise: float = 0.5, measurement_noise: float = 2.0):
        self.x = 0.0          # state estimate
        self.p = 1.0          # estimate uncertainty
        self.q = process_noise
        self.r = measurement_noise

    def predict(self) -> float:
        """Predict step — increase uncertainty by process noise."""
        self.p += self.q
        return self.x

    def update(self, measurement: float) -> float:
        """Update step — fuse measurement with prediction."""
        k = self.p / (self.p + self.r)   # Kalman gain
        self.x = self.x + k * (measurement - self.x)
        self.p = (1.0 - k) * self.p
        return self.x

    def smooth(self, measurement: float) -> float:
        """Single-call predict+update, returns smoothed value."""
        self.predict()
        return self.update(measurement)


def to_event_payload(event) -> dict[str, Any]:
    return {
        "id": event.id,
        "type": event.type,
        "severity": event.severity,
        "zone": event.zone,
        "deviceId": event.device_id,
        "confidence": event.confidence,
        "timestamp": event.timestamp,
        "metadata": event.metadata,
    }


def avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _zone_center(zone: dict[str, Any]) -> tuple[float, float]:
    """Compute the center of a zone polygon."""
    poly = zone["polygon"]
    cx = sum(p["x"] for p in poly) / len(poly)
    cy = sum(p["y"] for p in poly) / len(poly)
    return cx, cy


def assign_device_zone(device: dict[str, Any], zones: list[dict[str, Any]]) -> str:
    """Return the zone id whose center is closest to the device position."""
    dx, dy = device.get("x", 0), device.get("y", 0)
    best_id = zones[0]["id"]
    best_dist = float("inf")
    for z in zones:
        cx, cy = _zone_center(z)
        dist = (dx - cx) ** 2 + (dy - cy) ** 2
        if dist < best_dist:
            best_dist = dist
            best_id = z["id"]
    return best_id


class SignalAdapterRuntime:
    def __init__(self) -> None:
        self.manager = ConnectionManager()
        self.csi_processor = CSIProcessor()
        self.event_engine = EventEngine()
        self.devices: dict[str, dict[str, Any]] = {}
        self.zones: list[dict[str, Any]] = [dict(z) for z in DEFAULT_ZONES]
        self.transport = None
        self.bridge: "BridgeClient | None" = None
        # Prometheus metrics
        self._csi_frames_total: int = 0
        # Broadcast throttling
        self._last_broadcast_time = 0.0
        self._broadcast_interval = 0.2  # seconds
        # Lazy-init state (P3-13 fix)
        self._presence_welford: dict = {}
        self._motion_baseline: dict = {}
        self._motion_baseline_samples: dict = {}
        self._baseline_ready = False
        # Learning Report state
        self._empty_room_calibrated = False
        self._empty_room_calibrated_at: str | None = None
        self._empty_room_baselines: dict = {}  # device_id -> presence_score baseline
        # Kalman filter for presenceCount smoothing (Phase 5-3)
        self._kalman = KalmanSmooth(process_noise=0.5, measurement_noise=2.0)
        # Camera detection timestamp for time-based fusion staleness check
        self._camera_detection_ts: float = 0.0  # monotonic seconds
        # Last time camera detected at least one person (monotonic seconds)
        self._camera_last_person_ts: float = 0.0
        # Active modality for confidence-based switching (Phase 5-4)
        self._active_modality: str = "csi_only"
        self._camera_confidence: float = 0.0   # rolling camera reliability (0-1)
        self._csi_confidence: float = 0.5       # rolling CSI reliability (0-1)
        # Fall detection ML framework (Phase 3-1~3-3)
        self.fall_detector = FallDetector()
        self._motion_history: dict[str, list[float]] = {}  # device_id -> recent motion values
        self._motion_history_max = 50  # keep last 50 motion samples per device
        # Alert notification system (Phase 3-5)
        self.notifier = Notifier()
        self.notifier.add_backend(ConsoleBackend())
        # WebSocket and Webhook backends are added after broadcast is available (see _init_notifier_backends)
        self._notifier_backends_ready = False
        # Track previous device status for online/offline transitions
        self._prev_device_status: dict[str, str] = {}
        # Fall cross-validation: camera+CSI (Phase 3-4)
        self._fall_cross_validation_history: list[dict[str, Any]] = []
        self._camera_fall_candidates: dict[str, bool] = {}  # detection_id -> True
        # mmWave integration framework (Phase 5-5)
        self.mmwave_bridge: MmWaveBridge | None = None

    def _ensure_notifier_backends(self) -> None:
        """Lazily add WebSocket and Webhook backends once broadcast is available."""
        if not self._notifier_backends_ready:
            self.notifier.add_backend(WebSocketBackend(self.broadcast))
            self.notifier.add_backend(WebhookBackend())
            self._notifier_backends_ready = True

    def device_key(self, node_id: int) -> str:
        return f"node-{node_id}"

    def device_position(self, node_id: int) -> tuple[int, int]:
        return DEVICE_POSITIONS[(node_id - 1) % len(DEVICE_POSITIONS)]

    def _fuse_person_count(self) -> int:
        """Fuse person count estimates from all online nodes.

        Each node reports n_persons based on its local CSI analysis.
        Since nodes observe overlapping areas, we use the median of
        non-zero reports as the fused estimate, scaled by the number
        of nodes reporting presence (more nodes = higher confidence
        of more people spread across the space).
        """
        counts = []
        for dev in self.devices.values():
            if dev.get("status") == "online" and "n_persons" in dev:
                counts.append(dev["n_persons"])
        if not counts:
            return 0
        non_zero = [c for c in counts if c > 0]
        if not non_zero:
            return 0
        # Use max of node estimates — each node sees its local area,
        # people in different areas are counted by different nodes
        total = max(non_zero)
        # If multiple nodes report high counts, people may be spread out
        nodes_with_presence = len(non_zero)
        if nodes_with_presence >= 3 and total < sum(non_zero) // nodes_with_presence + 1:
            total = sum(non_zero) // nodes_with_presence + 1
        return total

    def _recompute_presence_count(self) -> int:
        """Fuse vitals n_persons, Welford z-score presence, and camera.

        Uses three presence indicators with priority:
        1. Camera person count (most accurate when available)
        2. Firmware vitals n_persons (requires calibration)
        3. Welford z-score on CSI presence_score (server-side, adaptive)

        Welford z-score approach (ref: edge_processing.c adaptive calibration):
        - First 60 samples: learn baseline presence_score per node
        - After calibration: z > 3.0 = human presence detected
        - More robust than breathing baseline (no false positives from WiFi noise)
        """
        camera = self.zones[0].get("camera_person_count", 0)
        fused = self._fuse_person_count()

        # Welford z-score presence detection

        nodes_with_presence = 0
        for dev in self.devices.values():
            if dev.get("status") != "online":
                continue
            did = dev["id"]
            score = dev.get("presence_score", 0)
            if score <= 0:
                continue

            # Initialize Welford tracker per node
            if did not in self._presence_welford:
                self._presence_welford[did] = {
                    "stats": WelfordStats(),
                    "calibrated": False,
                    "threshold": 0.0,
                }

            tracker = self._presence_welford[did]

            # Calibration phase: first 60 samples
            if not tracker["calibrated"]:
                tracker["stats"].update(score)
                if tracker["stats"].count >= 60:
                    tracker["calibrated"] = True
                    tracker["threshold"] = tracker["stats"].mean + 3.0 * tracker["stats"].std()
                    dev["_presence_baseline"] = tracker["stats"].mean
                    dev["_presence_threshold"] = tracker["threshold"]
                continue

            # Detection: score above calibrated threshold
            if score > tracker["threshold"]:
                nodes_with_presence += 1
                dev["_presence_z"] = tracker["stats"].z_score(score)
            else:
                dev["_presence_z"] = 0.0

            # Slow threshold drift (don't corrupt Welford stats)
            tracker["threshold"] = tracker["threshold"] * 0.999 + score * 0.001

        # Count nodes with valid breathing ONLY if Welford also confirms presence
        # (prevents false positives from WiFi noise in empty rooms)
        nodes_breathing = 0
        for dev in self.devices.values():
            if dev.get("status") != "online":
                continue
            # Require Welford z-score > 0 (presence confirmed by variance change)
            if dev.get("_presence_z", 0) <= 0:
                continue
            csi_br = dev.get("csi_breathing_bpm")
            csi_hr = dev.get("csi_heart_rate")
            if csi_br and 8 <= csi_br <= 25 and csi_hr and 50 <= csi_hr <= 100:
                nodes_breathing += 1

        # CSI subcarrier clustering person estimate (multi-person separation)
        # Use the max across nodes — each node sees its local area
        csi_person_max = 0
        for dev in self.devices.values():
            if dev.get("status") != "online":
                continue
            csi_persons = dev.get("csi_estimated_persons", 0)
            if csi_persons > csi_person_max:
                csi_person_max = csi_persons

        # Check if any CSI node shows active motion
        any_motion = any(
            dev.get("motion_index", 0) > 0.5
            for dev in self.devices.values()
            if dev.get("status") == "online"
        )

        # Time-based camera fusion: only use camera if detection is fresh (< 2s)
        camera_age = _time.monotonic() - self._camera_detection_ts
        if camera_age > 2.0:
            camera = 0  # stale camera data — use CSI-only

        # --- Confidence-based modality switching (Phase 5-4) ---
        now = _time.monotonic()
        if camera > 0:
            self._camera_last_person_ts = now

        camera_person_age = now - self._camera_last_person_ts
        csi_estimate = max(fused, nodes_with_presence, nodes_breathing, csi_person_max)

        # Update rolling confidence scores (EMA α=0.1)
        alpha = 0.1
        camera_responsive = self._camera_last_person_ts > 0 and camera_person_age <= 30.0
        self._camera_confidence += alpha * ((1.0 if camera_responsive else 0.0) - self._camera_confidence)
        csi_active = nodes_with_presence > 0 or any_motion
        self._csi_confidence += alpha * ((1.0 if csi_active else 0.3) - self._csi_confidence)

        # Select modality based on confidence thresholds
        if self._camera_confidence >= 0.5 and camera_responsive:
            # Camera reliable — full fusion mode
            self._active_modality = "camera+csi"
            cam_w = min(self._camera_confidence, 0.8)
            csi_w = 1.0 - cam_w
            total = round(camera * cam_w + csi_estimate * csi_w)
            total = max(total, 1)
        elif self._camera_confidence >= 0.2 and camera_responsive:
            # Camera degraded — equal weight fusion
            self._active_modality = "camera+csi_degraded"
            total = round(camera * 0.5 + csi_estimate * 0.5)
            total = max(total, 1) if camera > 0 or csi_estimate > 0 else 0
        else:
            # Camera dark/unavailable — CSI-only mode
            self._active_modality = "csi_only"
            total = csi_estimate

        # --- Per-zone presence counts ---
        self._recompute_zone_presence()

        # Kalman-smooth the final presenceCount (Phase 5-3)
        smoothed = self._kalman.smooth(float(total))
        total = max(0, round(smoothed))

        return total

    def _recompute_zone_presence(self) -> None:
        """Assign each online device to its closest zone and set per-zone presenceCount."""
        zone_counts: dict[str, int] = {z["id"]: 0 for z in self.zones}

        for dev in self.devices.values():
            if dev.get("status") != "online":
                continue
            zone_id = assign_device_zone(dev, self.zones)
            dev["zone_id"] = zone_id

            # Count presence signals per zone
            if dev.get("n_persons", 0) > 0:
                zone_counts[zone_id] += dev["n_persons"]
            elif dev.get("_presence_z", 0) > 0:
                zone_counts[zone_id] += 1
            elif dev.get("csi_breathing_bpm") and 8 <= dev["csi_breathing_bpm"] <= 25:
                # Only count breathing if Welford is calibrated — prevents false positives
                # during the empty-room baseline learning phase (< 60 samples)
                did = dev["id"]
                if self._presence_welford.get(did, {}).get("calibrated"):
                    zone_counts[zone_id] += 1

        for z in self.zones:
            if not z.get("_manual_override"):
                z["presenceCount"] = zone_counts.get(z["id"], 0)

    def ensure_device(self, node_id: int, ip: str | None = None) -> dict[str, Any]:
        device_id = self.device_key(node_id)
        if device_id not in self.devices:
            x, y = self.device_position(node_id)
            self.devices[device_id] = {
                "id": device_id,
                "name": f"ESP32 Node {node_id}",
                "mac": ip or "",
                "status": "online",
                "x": x,
                "y": y,
                "signalStrength": None,
                "lastSeen": iso_now(),
                "firmwareVersion": "RuView CSI Node / ESP-IDF v5.5.3",
                "model": "ESP32-S3-WROOM-1-N8R8",
                "chipType": "ESP32-S3 LX7×2 240MHz",
                "flashSize": "8MB QSPI DIO 80MHz",
                "psramSize": "8MB Octal SPI",
                "idfVersion": "v5.5.3",
            }
        else:
            existing_ip = self.devices[device_id].get("mac", "")
            if ip and existing_ip and existing_ip != ip and not existing_ip.startswith("node"):
                import logging
                logging.warning(
                    f"[node_id collision] node_id={node_id} already registered from {existing_ip}, "
                    f"new packet from {ip}. Check provision.py — each node must have a unique ID."
                )
        return self.devices[device_id]

    async def broadcast(self, message_type: str, payload: dict[str, Any]) -> None:
        encoded = json.dumps(
            {
                "type": message_type,
                "payload": payload,
                "timestamp": iso_now(),
            }
        )
        # Local WebSocket clients
        await self.manager.broadcast(encoded)
        # Cloudflare relay (if bridge connected)
        if self.bridge and self.bridge.is_connected:
            await self.bridge.send(encoded)

    async def check_offline_devices(self) -> None:
        """Mark devices as offline if no data received for 30 seconds."""
        self._ensure_notifier_backends()
        now = datetime.now(timezone.utc)
        changed = False
        for dev in self.devices.values():
            last = datetime.fromisoformat(dev["lastSeen"])
            delta = (now - last).total_seconds()
            new_status = "online" if delta < 30 else "offline"
            prev_status = self._prev_device_status.get(dev["id"], dev["status"])
            if dev["status"] != new_status:
                dev["status"] = new_status
                changed = True
                if new_status == "offline":
                    for key in ("breathing_bpm", "heart_rate", "csi_breathing_bpm",
                                "csi_heart_rate", "motion_energy", "presence_score",
                                "n_persons", "csi_estimated_persons"):
                        dev[key] = 0
                    # Alert: device went offline
                    await self.notifier.notify(
                        f"device_offline_{dev['id']}",
                        f"{dev['name']} ({dev['id']}) is offline (no data for {int(delta)}s)",
                        "warning",
                        {"device_id": dev["id"], "last_seen": dev["lastSeen"]},
                    )
                elif new_status == "online" and prev_status == "offline":
                    # Alert: device came back online
                    await self.notifier.notify(
                        f"device_online_{dev['id']}",
                        f"{dev['name']} ({dev['id']}) is back online",
                        "info",
                        {"device_id": dev["id"]},
                    )
            self._prev_device_status[dev["id"]] = new_status
        if changed:
            await self.broadcast_devices()
            self._recompute_presence_count()
            await self.broadcast_zones()

    async def broadcast_devices(self) -> None:
        await self.broadcast("device_update", {"devices": list(self.devices.values())})

    async def broadcast_zones(self) -> None:
        await self.broadcast("zone_update", {"zones": self.zones})

    def calibrate_empty_room(self) -> dict:
        """Snapshot current CSI presence_score as empty-room baseline per device."""
        now = iso_now()
        baselines = {}
        for dev in self.devices.values():
            if dev.get("status") == "online":
                baselines[dev["id"]] = dev.get("presence_score", 0.0)
                # Reset Welford tracker so it relearns from this empty state
                if dev["id"] in self._presence_welford:
                    self._presence_welford[dev["id"]] = {
                        "stats": WelfordStats(),
                        "calibrated": False,
                        "threshold": 0.0,
                    }
        self._empty_room_baselines = baselines
        self._empty_room_calibrated = True
        self._empty_room_calibrated_at = now
        return {"calibrated_at": now, "nodes": len(baselines)}

    def build_learning_report(self) -> dict:
        """Build Learning Report snapshot."""
        total_presence = sum(z["presenceCount"] for z in self.zones)
        online_count = sum(1 for d in self.devices.values() if d.get("status") == "online")

        zone_details = []
        for z in self.zones:
            count = z["presenceCount"]
            note = "빈 방 정상" if count == 0 and self._empty_room_calibrated else None
            zone_details.append({
                "name": z["name"],
                "presenceCount": count,
                "note": note,
            })

        summary_parts = [
            "빈 방 캘리브레이션 완료." if self._empty_room_calibrated else "캘리브레이션 미완료.",
            "모니터링 시작.",
            f"presenceCount: {total_presence}, {online_count}대 온라인,",
        ]
        for zd in zone_details:
            if zd["note"]:
                summary_parts.append(f"{zd['name']}: {zd['presenceCount']}명 ({zd['note']}).")

        return {
            "title": "RuView Learning Report",
            "timestamp": iso_now(),
            "calibrated": self._empty_room_calibrated,
            "calibrated_at": self._empty_room_calibrated_at,
            "presenceCount": total_presence,
            "active_modality": self._active_modality,
            "onlineDevices": online_count,
            "zones": zone_details,
            "summary": " ".join(summary_parts),
        }

    async def handle_processed(self, processed: ProcessedCSI) -> None:
        events = self.event_engine.evaluate(processed)

        # --- Fall Detection ML integration (Phase 3-1~3-3) ---
        # Track motion history per device
        from collections import deque
        did = processed.device_id
        if did not in self._motion_history:
            self._motion_history[did] = deque(maxlen=self._motion_history_max)
        self._motion_history[did].append(processed.motion_index)

        # Ensure notifier backends are ready
        self._ensure_notifier_backends()

        # When fall is suspected by event_engine, run ML fall detector
        fall_events = [e for e in events if e.type == "fall_suspected"]
        for fe in fall_events:
            motion_hist = self._motion_history.get(did, [])
            if len(motion_hist) >= 4:
                features = extract_fall_features(motion_hist, self.csi_processor.SAMPLE_RATE)
                is_fall, confidence = self.fall_detector.detect(features)
                # Update the event confidence with ML result
                fe.confidence = confidence
                fe.metadata["ml_fall_detected"] = is_fall
                fe.metadata["ml_confidence"] = confidence
                fe.metadata["fall_features"] = features
                if not is_fall:
                    # ML says not a fall — downgrade severity
                    fe.severity = "warning"
                    fe.type = "fall_suspected_low_confidence"
                else:
                    # ML confirmed fall — send critical alert
                    await self.notifier.notify(
                        "fall",
                        f"Fall detected on {did} (confidence: {confidence:.2f})",
                        "critical",
                        {
                            "device_id": did,
                            "confidence": confidence,
                            "features": features,
                        },
                    )

        # Broadcast gesture if detected
        if processed.gesture is not None:
            await self.broadcast("gesture", {
                "device_id": processed.device_id,
                "gesture": processed.gesture,
                "confidence": processed.gesture_confidence,
                "timestamp": processed.timestamp,
            })

        # Include breathing and heart rate in signal payload for chart
        dev = self.devices.get(processed.device_id, {})

        # Sample up to 30 subcarrier amplitudes for Observatory CSI heatmap
        _amp = processed.amplitude or []
        _step = max(1, len(_amp) // 30)
        _sampled = [round(float(_amp[i]), 3) for i in range(0, min(len(_amp), _step * 30), _step)]

        signal_payload = {
            "device_id": processed.device_id,
            "time": processed.timestamp[11:19] if len(processed.timestamp) >= 19 else processed.timestamp,
            "rssi": round(processed.rssi, 1),
            "snr": round(processed.rssi - processed.noise_floor, 1),
            "csi_amplitude": round(avg(processed.amplitude), 2),
            "motion_index": round(processed.motion_index, 3),
            "breathing_rate": round(dev.get("breathing_bpm", 0) or 0, 1),
            "heart_rate": round(dev.get("heart_rate", 0) or 0, 1),
            "csi_amplitudes": _sampled,
            "n_subcarriers": len(_amp),
        }
        await self.broadcast("signal", signal_payload)

        for event in events:
            await self.broadcast("event", to_event_payload(event))

        sb = get_supabase()
        if sb and events:
            try:
                sb.table("events").insert([e.model_dump() for e in events]).execute()
            except Exception:
                pass  # Non-critical: Supabase may be unavailable

    async def handle_csi_frame(self, data: bytes, addr: tuple[str, int]) -> None:
        if len(data) < 20:
            return

        self._csi_frames_total += 1
        node_id = data[4]
        n_subcarriers = struct.unpack_from("<H", data, 6)[0]
        rssi = struct.unpack_from("<b", data, 16)[0]
        noise_floor = struct.unpack_from("<b", data, 17)[0]
        iq_bytes = data[20:]

        device = self.ensure_device(node_id, addr[0])
        device["status"] = "online"
        device["mac"] = addr[0]
        device["signalStrength"] = rssi
        device["lastSeen"] = iso_now()

        # Fast I/Q parsing via numpy (replaces per-element struct.unpack)
        pairs = min(n_subcarriers, len(iq_bytes) // 2)
        if pairs > 0:
            iq_arr = np.frombuffer(iq_bytes[:pairs * 2], dtype=np.int8)
            csi_data = (iq_arr[0::2] + 1j * iq_arr[1::2]).tolist()
        else:
            csi_data = []

        loop = asyncio.get_running_loop()
        processed = await loop.run_in_executor(
            None,
            self.csi_processor.process,
            {
                "device_id": device["id"],
                "timestamp": iso_now(),
                "csi_data": csi_data,
                "rssi": float(rssi),
                "noise_floor": float(noise_floor),
            },
        )

        # Assign device to closest zone and update zone lastActivity
        device_zone_id = assign_device_zone(device, self.zones)
        device["zone_id"] = device_zone_id
        for z in self.zones:
            if z["id"] == device_zone_id:
                z["lastActivity"] = processed.timestamp
                break

        # Track per-device CSI metrics
        device["motion_energy"] = processed.motion_index
        device["presence_score"] = processed.presence_score

        # Multi-person separation from CSI subcarrier clustering
        if processed.estimated_persons > 0:
            device["csi_estimated_persons"] = processed.estimated_persons
            device["csi_per_person_breathing"] = processed.per_person_breathing

        # Body Velocity Profile (BVP)
        if processed.velocity_profile is not None:
            device["velocity_profile"] = processed.velocity_profile
            device["max_velocity"] = processed.max_velocity

        # CSI pose classification
        device["csi_pose"] = processed.csi_pose or "unknown"
        device["csi_pose_confidence"] = processed.csi_pose_confidence

        # HRV analysis (Phase Additional C)
        if processed.hrv is not None:
            device["hrv"] = processed.hrv

        # Server-side vitals extraction (supplement firmware vitals)
        if processed.breathing_rate is not None:
            device["csi_breathing_bpm"] = processed.breathing_rate
        if processed.heart_rate is not None:
            device["csi_heart_rate"] = processed.heart_rate
        # Use server vitals as fallback when firmware vitals unavailable
        if device.get("breathing_bpm", 0) == 0 and processed.breathing_rate:
            device["breathing_bpm"] = processed.breathing_rate
        if device.get("heart_rate", 0) == 0 and processed.heart_rate:
            device["heart_rate"] = processed.heart_rate

        # Recompute presence for all zones
        self._recompute_presence_count()

        # Throttled broadcast: max once per 500ms to keep event loop responsive
        now = _time.monotonic()
        if now - self._last_broadcast_time >= 0.5:
            self._last_broadcast_time = now
            await self.broadcast_devices()
            await self.broadcast_zones()
            await self.handle_processed(processed)

    async def handle_vitals_frame(self, data: bytes, addr: tuple[str, int]) -> None:
        if len(data) < 24:
            return

        node_id = data[4]
        flags = data[5]
        breathing_bpm = struct.unpack_from("<H", data, 6)[0] / 100.0
        heart_rate = struct.unpack_from("<I", data, 8)[0] / 10000.0
        if not (20.0 <= heart_rate <= 250.0):
            heart_rate = 0.0
        rssi = struct.unpack_from("<b", data, 12)[0]
        n_persons = data[13]
        motion_energy = struct.unpack_from("<f", data, 16)[0]
        presence_score = struct.unpack_from("<f", data, 20)[0]

        device = self.ensure_device(node_id, addr[0])
        device["status"] = "online"
        device["signalStrength"] = rssi
        device["lastSeen"] = iso_now()

        # Track per-node vitals
        device["n_persons"] = n_persons
        device["presence_score"] = presence_score
        device["motion_energy"] = motion_energy
        device["breathing_bpm"] = breathing_bpm
        device["heart_rate"] = heart_rate

        # Assign device to closest zone
        device_zone_id = assign_device_zone(device, self.zones)
        device["zone_id"] = device_zone_id

        # Multi-node fusion: aggregate person estimates per zone
        self._recompute_presence_count()
        for z in self.zones:
            if z["id"] == device_zone_id:
                z["lastActivity"] = iso_now()
                break
        await self.broadcast_devices()
        await self.broadcast_zones()

        # Broadcast vitals to all WS clients (observatory, dashboard)
        vitals_payload = {
            "device_id": self.device_key(node_id),
            "breathing_rate_bpm": breathing_bpm,
            "heart_rate_bpm": heart_rate,
            "motion_energy": motion_energy,
            "presence_score": presence_score,
            "n_persons": n_persons,
            "flags": flags,
        }
        await self.broadcast("vitals", vitals_payload)

        if flags & 0x02:
            event_payload = {
                "id": f"{node_id}-{int(datetime.now().timestamp() * 1000)}",
                "type": "fall_suspected",
                "severity": "critical",
                "zone": device.get("zone_id", "zone-1001"),
                "deviceId": self.device_key(node_id),
                "confidence": min(max(motion_energy / 5.0, 0.6), 0.99),
                "timestamp": iso_now(),
                "metadata": vitals_payload,
            }
            await self.broadcast("event", event_payload)

    def generate_learning_report(self) -> dict:
        """Generate hourly learning report — calibration status + presence summary."""
        KST = timezone(timedelta(hours=9))
        now_kst = datetime.now(KST)

        online_devices = [d for d in self.devices.values() if d.get("status") == "online"]

        # Welford calibration status per device
        calibration = {}
        all_calibrated = True
        for did, tracker in self._presence_welford.items():
            stats = tracker["stats"]
            calibrated = tracker["calibrated"]
            if not calibrated:
                all_calibrated = False
            calibration[did] = {
                "calibrated": calibrated,
                "samples": stats.count,
                "samples_needed": 60,
                "mean": round(stats.mean, 4),
                "std": round(stats.std(), 4),
            }

        # Per-zone summary
        zones_summary = [
            {
                "zone_id": z["id"],
                "name": z["name"],
                "presenceCount": z.get("presenceCount", 0),
            }
            for z in self.zones
        ]

        # Determine report number from existing files
        log_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(log_dir, exist_ok=True)
        existing = [f for f in os.listdir(log_dir) if f.startswith("learning_report_")]
        report_num = len(existing) + 1

        total_presence = sum(z.get("presenceCount", 0) for z in self.zones)

        report = {
            "report": f"Learning Report #{report_num}",
            "timestamp_kst": now_kst.strftime("%Y-%m-%d %H:%M KST"),
            "online_devices": len(online_devices),
            "presence_count": total_presence,
            "active_modality": self._active_modality,
            "calibration_complete": all_calibrated,
            "calibration": calibration,
            "zones": zones_summary,
        }

        # Save to logs/
        log_file = os.path.join(log_dir, f"learning_report_{now_kst.strftime('%Y%m%d_%H%M')}.json")
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(
            f"[learning-report] #{report_num} | "
            f"presenceCount: {total_presence} | "
            f"{len(online_devices)}대 온라인 | "
            f"캘리브레이션: {'완료' if all_calibrated else '진행 중'}"
        )
        return report

    async def route_datagram(self, data: bytes, addr: tuple[str, int]) -> None:
        if len(data) < 4:
            return

        magic = struct.unpack_from("<I", data, 0)[0]
        if magic == CSI_MAGIC:
            await self.handle_csi_frame(data, addr)
        elif magic == VITALS_MAGIC:
            await self.handle_vitals_frame(data, addr)


runtime = SignalAdapterRuntime()


class UDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop
        self._active_tasks = 0  # Backpressure counter (asyncio single-thread safe)

    def datagram_received(self, data: bytes, addr) -> None:
        # asyncio is single-threaded so plain counter is safe (no TOCTOU race)
        if self._active_tasks >= 2:
            return  # Drop frame under backpressure
        self._active_tasks += 1
        self.loop.create_task(self._handle(data, addr))

    async def _handle(self, data, addr):
        try:
            await runtime.route_datagram(data, addr)
        except Exception:
            import traceback
            traceback.print_exc()
        finally:
            self._active_tasks -= 1


async def _offline_check_loop():
    """Periodically check for offline devices."""
    while True:
        await asyncio.sleep(5)
        await runtime.check_offline_devices()


async def _hourly_report_loop():
    """Generate hourly learning reports, save to logs/, and broadcast to WS clients."""
    while True:
        await asyncio.sleep(3600)
        report = runtime.generate_learning_report()
        await runtime.broadcast("learning_report", report)
        print(f"[signal-adapter] [Learning Report] {report.get('summary', report.get('report'))}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: UDPProtocol(loop),
        local_addr=(UDP_HOST, UDP_PORT),
    )
    runtime.transport = transport
    offline_task = asyncio.create_task(_offline_check_loop())
    hourly_report_task = asyncio.create_task(_hourly_report_loop())

    # Cloudflare bridge (outbound relay for external access)
    bridge_url = os.getenv("RUVIEW_BRIDGE_URL")
    bridge_session = os.getenv("RUVIEW_BRIDGE_SESSION", "default")
    bridge_token = os.getenv("RUVIEW_BRIDGE_TOKEN")
    print(f"[signal-adapter] Bridge URL: {bridge_url}")
    if bridge_url:
        from bridge_client import BridgeClient

        async def _bridge_on_connected():
            """Send full state when bridge connects (for external front clients)."""
            return json.dumps({
                "type": "init",
                "payload": {
                    "devices": list(runtime.devices.values()),
                    "zones": runtime.zones,
                },
                "timestamp": iso_now(),
            })

        runtime.bridge = BridgeClient(
            bridge_url, bridge_session, bridge_token,
            on_connected=_bridge_on_connected,
        )
        await runtime.bridge.start()
        print(f"[signal-adapter] Bridge connected to {bridge_url}")

    # mmWave bridge (Phase 5-5): start if RUVIEW_MMWAVE_PORT is set
    mmwave_port = os.getenv("RUVIEW_MMWAVE_PORT")
    mmwave_task = None
    if mmwave_port:
        runtime.mmwave_bridge = MmWaveBridge(
            udp_port=int(mmwave_port),
            udp_host=os.getenv("RUVIEW_MMWAVE_HOST", "0.0.0.0"),
        )
        mmwave_task = asyncio.create_task(runtime.mmwave_bridge.start_listener(loop))
        print(f"[signal-adapter] mmWave bridge started on UDP port {mmwave_port}")
    else:
        print("[signal-adapter] mmWave bridge disabled (RUVIEW_MMWAVE_PORT not set)")

    print(f"[signal-adapter] Starting up on UDP {UDP_HOST}:{UDP_PORT}...")
    yield
    print("[signal-adapter] Shutting down...")
    if runtime.mmwave_bridge:
        runtime.mmwave_bridge.stop()
    if mmwave_task:
        mmwave_task.cancel()
    if runtime.bridge:
        runtime.bridge.stop()
    offline_task.cancel()
    hourly_report_task.cancel()
    if runtime.transport is not None:
        runtime.transport.close()


app = FastAPI(
    title="RuView Signal Adapter",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "signal-adapter",
        "mode": "hardware",
        "udp_host": UDP_HOST,
        "udp_port": UDP_PORT,
        "devices": len(runtime.devices),
    }


@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus-compatible metrics endpoint (text/plain exposition format)."""
    from fastapi.responses import PlainTextResponse

    lines: list[str] = []

    # ruview_online_devices gauge
    online = sum(1 for d in runtime.devices.values() if d.get("status") == "online")
    lines.append("# HELP ruview_online_devices Number of online ESP32 devices")
    lines.append("# TYPE ruview_online_devices gauge")
    lines.append(f"ruview_online_devices {online}")

    # ruview_presence_count gauge (per zone)
    lines.append("# HELP ruview_presence_count Presence count per zone")
    lines.append("# TYPE ruview_presence_count gauge")
    for z in runtime.zones:
        zone_id = z["id"]
        zone_name = z["name"]
        count = z.get("presenceCount", 0)
        lines.append(f'ruview_presence_count{{zone_id="{zone_id}",zone_name="{zone_name}"}} {count}')

    # ruview_csi_frames_total counter
    lines.append("# HELP ruview_csi_frames_total Total CSI frames received")
    lines.append("# TYPE ruview_csi_frames_total counter")
    lines.append(f"ruview_csi_frames_total {runtime._csi_frames_total}")

    # ruview_breathing_bpm gauge (per device)
    lines.append("# HELP ruview_breathing_bpm Breathing rate in BPM per device")
    lines.append("# TYPE ruview_breathing_bpm gauge")
    for dev in runtime.devices.values():
        did = dev["id"]
        bpm = dev.get("breathing_bpm", 0) or dev.get("csi_breathing_bpm", 0) or 0
        lines.append(f'ruview_breathing_bpm{{device="{did}"}} {round(bpm, 1)}')

    # ruview_heart_rate_bpm gauge (per device)
    lines.append("# HELP ruview_heart_rate_bpm Heart rate in BPM per device")
    lines.append("# TYPE ruview_heart_rate_bpm gauge")
    for dev in runtime.devices.values():
        did = dev["id"]
        hr = dev.get("heart_rate", 0) or dev.get("csi_heart_rate", 0) or 0
        lines.append(f'ruview_heart_rate_bpm{{device="{did}"}} {round(hr, 1)}')

    # ruview_active_modality info
    lines.append("# HELP ruview_active_modality Current active sensing modality")
    lines.append("# TYPE ruview_active_modality gauge")
    lines.append(f'ruview_active_modality{{modality="{runtime._active_modality}"}} 1')

    body = "\n".join(lines) + "\n"
    return PlainTextResponse(body, media_type="text/plain; version=0.0.4; charset=utf-8")


@app.get("/api/devices")
async def list_devices():
    return {"data": list(runtime.devices.values())}


@app.put("/api/devices/{device_id}/position", dependencies=[Depends(verify_api_key)])
async def update_device_position(device_id: str, body: dict):
    """Update device position on floor plan (drag-drop)."""
    if device_id not in runtime.devices:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
    x = body.get("x")
    y = body.get("y")
    if x is None or y is None:
        raise HTTPException(status_code=400, detail="x and y required")
    runtime.devices[device_id]["x"] = int(x)
    runtime.devices[device_id]["y"] = int(y)
    await runtime.broadcast_devices()
    return {"status": "ok", "x": int(x), "y": int(y)}


def _fuse_poses(camera_pose: str | None, camera_conf: float,
                 csi_pose: str | None, csi_conf: float) -> tuple[str, float]:
    """Fuse camera and CSI pose estimates.

    Camera weight = 0.8, CSI weight = 0.2.
    If both agree, confidence is boosted to 0.9+.
    """
    if camera_pose and csi_pose:
        if camera_pose == csi_pose:
            # Agreement — high confidence
            fused_conf = min(0.9 + 0.1 * min(camera_conf, csi_conf), 1.0)
            return (camera_pose, round(fused_conf, 3))
        else:
            # Disagreement — weighted blend, camera wins
            fused_conf = camera_conf * 0.8 + csi_conf * 0.2
            return (camera_pose, round(fused_conf, 3))
    elif camera_pose:
        return (camera_pose, round(camera_conf, 3))
    elif csi_pose:
        return (csi_pose, round(csi_conf, 3))
    return ("unknown", 0.0)


@app.post("/api/camera/detections", dependencies=[Depends(verify_api_key)])
async def camera_detections(body: dict):
    """Receive detection results from camera-service for CSI+camera fusion."""
    person_count = body.get("person_count", 0)
    detections = body.get("detections", [])

    # Record camera detection timestamp for staleness check (Phase 5-3)
    runtime._camera_detection_ts = _time.monotonic()

    # Store camera data per zone (distribute based on detection floor positions)
    # Reset all zones first
    for z in runtime.zones:
        z["camera_person_count"] = 0
        z["camera_detections"] = []
    # Assign each detection to its closest zone
    for det in detections:
        fp = det.get("floor_pos", {})
        if fp:
            dummy_dev = {"x": fp.get("x", 400), "y": fp.get("y", 200)}
            zone_id = assign_device_zone(dummy_dev, runtime.zones)
            for z in runtime.zones:
                if z["id"] == zone_id:
                    z["camera_person_count"] = z.get("camera_person_count", 0) + 1
                    z.setdefault("camera_detections", []).append(det)
                    break
        else:
            # No floor position — assign to first zone as fallback
            runtime.zones[0]["camera_person_count"] = runtime.zones[0].get("camera_person_count", 0) + 1
            runtime.zones[0].setdefault("camera_detections", []).append(det)

    # --- Pose fusion: camera + CSI ---
    # Check if camera data is within 2s of latest CSI data for valid fusion
    latest_csi_ts = max(
        (datetime.fromisoformat(d["lastSeen"]).timestamp()
         for d in runtime.devices.values() if d.get("status") == "online"),
        default=0.0,
    )
    camera_ts = body.get("timestamp", datetime.now(timezone.utc).timestamp())
    if isinstance(camera_ts, str):
        camera_ts = datetime.fromisoformat(camera_ts).timestamp()
    camera_csi_fresh = abs(camera_ts - latest_csi_ts) <= 2.0

    pose_updates = []
    for det in detections:
        cam_pose = det.get("pose")
        cam_pose_conf = det.get("pose_confidence", 0.0)
        cam_keypoints = det.get("keypoints")

        # --- Fall cross-validation: camera side (Phase 3-4) ---
        camera_fall_candidate = False
        if cam_pose in ("fallen", "lying"):
            camera_fall_candidate = True
            det["camera_fall_candidate"] = True

        # Find the closest device for CSI pose lookup
        # Use bbox center to match against device positions
        bbox = det.get("bbox", [0, 0, 0, 0])
        det_cx = (bbox[0] + bbox[2]) / 2 if len(bbox) == 4 else 0
        det_cy = (bbox[1] + bbox[3]) / 2 if len(bbox) == 4 else 0

        # Try to fuse with any device that has a CSI pose
        best_device = None
        best_dist = float("inf")
        for dev in runtime.devices.values():
            if dev.get("status") != "online":
                continue
            if dev.get("csi_pose") is None:
                continue
            dx = dev.get("x", 0) - det_cx
            dy = dev.get("y", 0) - det_cy
            dist = dx * dx + dy * dy
            if dist < best_dist:
                best_dist = dist
                best_device = dev

        csi_pose = best_device.get("csi_pose") if best_device else None
        csi_pose_conf = best_device.get("csi_pose_confidence", 0.0) if best_device else 0.0

        # --- Fall cross-validation: CSI side (Phase 3-4) ---
        # Check if CSI/event_engine also detected fall for this device
        csi_fall_detected = False
        if best_device is not None:
            csi_state = runtime.event_engine._state.get(best_device["id"], "")
            csi_fall_detected = csi_state == "fall" or csi_pose in ("fallen",)

        # Cross-validate camera + CSI fall detection
        if camera_fall_candidate or csi_fall_detected:
            if camera_fall_candidate and csi_fall_detected:
                # Both agree: high confidence cross-validated fall
                cross_val_type = "cross_validated_fall"
                cross_val_confidence = 0.95
                print(f"[fall-xval] CROSS-VALIDATED fall: camera+CSI agree (device={best_device['id'] if best_device else 'unknown'})")
            elif camera_fall_candidate and not csi_fall_detected:
                # Camera only: lower confidence
                cross_val_type = "camera_only_fall"
                cross_val_confidence = 0.5
                print(f"[fall-xval] Camera-only fall detected (CSI does not confirm)")
            else:
                # CSI only: moderate confidence
                cross_val_type = "csi_only_fall"
                cross_val_confidence = 0.6
                print(f"[fall-xval] CSI-only fall detected (camera does not confirm)")

            cross_val_record = {
                "type": cross_val_type,
                "confidence": cross_val_confidence,
                "camera_fall": camera_fall_candidate,
                "csi_fall": csi_fall_detected,
                "device_id": best_device["id"] if best_device else None,
                "timestamp": iso_now(),
                "camera_pose": cam_pose,
                "csi_pose": csi_pose,
            }
            runtime._fall_cross_validation_history.append(cross_val_record)
            # Keep last 100 cross-validation records
            if len(runtime._fall_cross_validation_history) > 100:
                runtime._fall_cross_validation_history = runtime._fall_cross_validation_history[-100:]

            # Store in alert history via notifier
            runtime._ensure_notifier_backends()
            await runtime.notifier.notify(
                cross_val_type,
                f"Fall {cross_val_type}: confidence={cross_val_confidence:.2f} "
                f"(camera={camera_fall_candidate}, csi={csi_fall_detected})",
                "critical" if cross_val_confidence >= 0.9 else "warning",
                cross_val_record,
            )

            # Override pose confidence with cross-validated confidence
            if camera_fall_candidate:
                cam_pose_conf = cross_val_confidence

        # Skip fusion if camera-CSI time gap > 2s; use CSI-only
        if camera_csi_fresh:
            fused_pose, fused_conf = _fuse_poses(cam_pose, cam_pose_conf, csi_pose, csi_pose_conf)
        else:
            fused_pose, fused_conf = (csi_pose or "unknown", round(csi_pose_conf, 3))

        # Store fused pose on the matched device
        if best_device is not None:
            best_device["pose"] = fused_pose
            best_device["pose_confidence"] = fused_conf

        pose_updates.append({
            "pose": fused_pose,
            "pose_confidence": fused_conf,
            "device_id": best_device["id"] if best_device else None,
            "camera_pose": cam_pose,
            "csi_pose": csi_pose,
            "keypoints": cam_keypoints,
        })

    # Cross-validate: camera provides more accurate person count
    if not runtime.zones[0].get("_manual_override") and person_count > 0:
        csi_count = runtime._recompute_presence_count()
        # Camera count is more reliable — use it, but keep CSI as minimum
        fused = max(csi_count, person_count)
        runtime.zones[0]["presenceCount"] = fused

    # Broadcast camera detections to frontend
    await runtime.broadcast("camera_detection", {
        "detections": detections,
        "person_count": person_count,
    })

    # Broadcast pose updates
    if pose_updates:
        await runtime.broadcast("pose_update", {"poses": pose_updates})

    await runtime.broadcast_zones()

    return {"status": "ok", "fused_count": runtime.zones[0]["presenceCount"]}


@app.get("/api/zones")
async def list_zones():
    return {"data": runtime.zones}


@app.put("/api/zones/presence", dependencies=[Depends(verify_api_key)])
async def set_presence_count(body: dict):
    """Manually set presenceCount (overrides sensor fusion)."""
    count = body.get("count")
    if count is None or not isinstance(count, int) or count < 0:
        raise HTTPException(status_code=400, detail="'count' must be a non-negative integer")
    runtime.zones[0]["presenceCount"] = count
    runtime.zones[0]["_manual_override"] = True
    await runtime.broadcast_zones()
    return {"presenceCount": count, "mode": "manual"}


@app.delete("/api/zones/presence", dependencies=[Depends(verify_api_key)])
async def clear_presence_override():
    """Clear manual override, return to sensor fusion mode."""
    runtime.zones[0].pop("_manual_override", None)
    runtime.zones[0]["presenceCount"] = runtime._recompute_presence_count()
    await runtime.broadcast_zones()
    return {"presenceCount": runtime.zones[0]["presenceCount"], "mode": "fusion"}


@app.get("/api/scenario")
async def get_scenario():
    return {"scenario": "hardware-live", "mode": "hardware", "supported": False}


@app.post("/api/scenario/{scenario}", dependencies=[Depends(verify_api_key)])
async def set_scenario(scenario: str):
    raise HTTPException(status_code=409, detail=f"Scenario switching is disabled in hardware mode: {scenario}")


@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    await runtime.manager.connect(websocket)
    try:
        await websocket.send_text(
            json.dumps(
                {
                    "type": "init",
                    "payload": {
                        "devices": list(runtime.devices.values()),
                        "zones": runtime.zones,
                    },
                    "timestamp": iso_now(),
                }
            )
        )
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, Exception):
        runtime.manager.disconnect(websocket)


@app.post("/api/calibration/empty-room", dependencies=[Depends(verify_api_key)])
async def calibrate_empty_room():
    """Snapshot current state as empty-room baseline and reset Welford trackers."""
    result = runtime.calibrate_empty_room()
    await runtime.broadcast("learning_report", runtime.build_learning_report())
    return {"status": "ok", **result}


@app.get("/api/learning-report")
async def get_learning_report():
    """Return current Learning Report snapshot (saves to logs/)."""
    return runtime.generate_learning_report()


@app.post("/api/fall/record", dependencies=[Depends(verify_api_key)])
async def fall_record(body: dict):
    """Record a fall/non-fall event for ML training data collection.

    Body: { "features": {...}, "label": true/false }
    Or: { "device_id": "node-1", "label": true/false }  (auto-extract features from motion history)
    """
    label = body.get("label")
    if label is None:
        raise HTTPException(status_code=400, detail="'label' (true/false) is required")

    features = body.get("features")
    if features is None:
        # Auto-extract from motion history
        device_id = body.get("device_id")
        if device_id and device_id in runtime._motion_history:
            motion_hist = runtime._motion_history[device_id]
            if len(motion_hist) >= 4:
                features = extract_fall_features(motion_hist, runtime.csi_processor.SAMPLE_RATE)
            else:
                raise HTTPException(status_code=400, detail="Not enough motion history for feature extraction")
        else:
            raise HTTPException(status_code=400, detail="Provide 'features' dict or valid 'device_id'")

    runtime.fall_detector.record_event(features, bool(label))
    return {"status": "ok", "features": features, "label": bool(label)}


@app.post("/api/fall/train", dependencies=[Depends(verify_api_key)])
async def fall_train():
    """Trigger ML model training from collected fall detection data."""
    import asyncio
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, runtime.fall_detector.train)
    return result


@app.get("/api/fall/stats")
async def fall_stats():
    """Get fall detection training data statistics."""
    stats = runtime.fall_detector.get_training_stats()
    return stats


@app.get("/api/alerts/history")
async def alerts_history():
    """Return last 50 alerts."""
    return {"data": runtime.notifier.get_history()}


@app.get("/api/fall/cross-validation")
async def fall_cross_validation_history():
    """Return fall cross-validation history (camera+CSI)."""
    return {"data": runtime._fall_cross_validation_history}


@app.get("/api/mmwave/status")
async def mmwave_status():
    """Return mmWave bridge connection status."""
    if runtime.mmwave_bridge is None:
        return {
            "connected": False,
            "enabled": False,
            "message": "mmWave bridge not enabled (set RUVIEW_MMWAVE_PORT to enable)",
        }
    return runtime.mmwave_bridge.get_status()


@app.post("/api/csi/ingest", dependencies=[Depends(verify_api_key)])
async def ingest_csi(payload: dict):
    processed = runtime.csi_processor.process(payload)
    await runtime.handle_processed(processed)
    return {"processed": 1}
