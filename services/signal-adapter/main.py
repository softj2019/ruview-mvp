import asyncio
import json
import math
import os
import struct
import time as _time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

try:
    from .ws_manager import ConnectionManager
    from .csi_processor import CSIProcessor, ProcessedCSI, WelfordStats
    from .event_engine import EventEngine
    from .supabase_client import get_supabase
except ImportError:
    from ws_manager import ConnectionManager
    from csi_processor import CSIProcessor, ProcessedCSI, WelfordStats
    from event_engine import EventEngine
    from supabase_client import get_supabase


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
        # Broadcast throttling: max once per 200ms
        self._last_broadcast_time = 0.0
        self._broadcast_interval = 0.2  # seconds
        # Lazy-init state (P3-13 fix)
        self._presence_welford: dict = {}
        self._motion_baseline: dict = {}
        self._motion_baseline_samples: dict = {}
        self._baseline_ready = False

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
        if not hasattr(self, "_presence_welford"):
            self._presence_welford = {}

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

        # Also count nodes with server-extracted breathing in valid range
        nodes_breathing = 0
        for dev in self.devices.values():
            if dev.get("status") != "online":
                continue
            csi_br = dev.get("csi_breathing_bpm")
            csi_hr = dev.get("csi_heart_rate")
            # Valid breathing AND heart rate = strong presence signal
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

        total = max(camera, fused, nodes_with_presence, nodes_breathing, csi_person_max)

        # --- Per-zone presence counts ---
        self._recompute_zone_presence()

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
                "firmwareVersion": "RuView operational",
            }
        return self.devices[device_id]

    async def broadcast(self, message_type: str, payload: dict[str, Any]) -> None:
        await self.manager.broadcast(
            json.dumps(
                {
                    "type": message_type,
                    "payload": payload,
                    "timestamp": iso_now(),
                }
            )
        )

    async def check_offline_devices(self) -> None:
        """Mark devices as offline if no data received for 30 seconds."""
        now = datetime.now(timezone.utc)
        changed = False
        for dev in self.devices.values():
            last = datetime.fromisoformat(dev["lastSeen"])
            delta = (now - last).total_seconds()
            new_status = "online" if delta < 30 else "offline"
            if dev["status"] != new_status:
                dev["status"] = new_status
                changed = True
                if new_status == "offline":
                    for key in ("breathing_bpm", "heart_rate", "csi_breathing_bpm",
                                "csi_heart_rate", "motion_energy", "presence_score",
                                "n_persons", "csi_estimated_persons"):
                        dev[key] = 0
        if changed:
            await self.broadcast_devices()
            self._recompute_presence_count()
            await self.broadcast_zones()

    async def broadcast_devices(self) -> None:
        await self.broadcast("device_update", {"devices": list(self.devices.values())})

    async def broadcast_zones(self) -> None:
        await self.broadcast("zone_update", {"zones": self.zones})

    async def handle_processed(self, processed: ProcessedCSI) -> None:
        events = self.event_engine.evaluate(processed)

        # Include breathing and heart rate in signal payload for chart
        dev = self.devices.get(processed.device_id, {})
        signal_payload = {
            "device_id": processed.device_id,
            "time": processed.timestamp[11:19] if len(processed.timestamp) >= 19 else processed.timestamp,
            "rssi": round(processed.rssi, 1),
            "snr": round(processed.rssi - processed.noise_floor, 1),
            "csi_amplitude": round(avg(processed.amplitude), 2),
            "motion_index": round(processed.motion_index, 3),
            "breathing_rate": round(dev.get("breathing_bpm", 0) or 0, 1),
            "heart_rate": round(dev.get("heart_rate", 0) or 0, 1),
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

        pairs = min(n_subcarriers, len(iq_bytes) // 2)
        csi_data = [
            complex(
                struct.unpack_from("<b", iq_bytes, index * 2)[0],
                struct.unpack_from("<b", iq_bytes, index * 2 + 1)[0],
            )
            for index in range(pairs)
        ]

        processed = self.csi_processor.process(
            {
                "device_id": device["id"],
                "timestamp": iso_now(),
                "csi_data": csi_data,
                "rssi": float(rssi),
                "noise_floor": float(noise_floor),
            }
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

        # Throttled broadcast: max once per 200ms to prevent event loop saturation
        now = _time.monotonic()
        if now - self._last_broadcast_time >= self._broadcast_interval:
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
        heart_rate = struct.unpack_from("<f", data, 8)[0]
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
        if self._active_tasks >= 8:
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: UDPProtocol(loop),
        local_addr=(UDP_HOST, UDP_PORT),
    )
    runtime.transport = transport
    offline_task = asyncio.create_task(_offline_check_loop())
    print(f"[signal-adapter] Starting up on UDP {UDP_HOST}:{UDP_PORT}...")
    yield
    print("[signal-adapter] Shutting down...")
    offline_task.cancel()
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


@app.get("/api/devices")
async def list_devices():
    return {"data": list(runtime.devices.values())}


@app.put("/api/devices/{device_id}/position")
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


@app.post("/api/camera/detections")
async def camera_detections(body: dict):
    """Receive detection results from camera-service for CSI+camera fusion."""
    person_count = body.get("person_count", 0)
    detections = body.get("detections", [])

    # Store camera data for fusion
    runtime.zones[0]["camera_person_count"] = person_count
    runtime.zones[0]["camera_detections"] = detections

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
    await runtime.broadcast_zones()

    return {"status": "ok", "fused_count": runtime.zones[0]["presenceCount"]}


@app.get("/api/zones")
async def list_zones():
    return {"data": runtime.zones}


@app.put("/api/zones/presence")
async def set_presence_count(body: dict):
    """Manually set presenceCount (overrides sensor fusion)."""
    count = body.get("count")
    if count is None or not isinstance(count, int) or count < 0:
        raise HTTPException(status_code=400, detail="'count' must be a non-negative integer")
    runtime.zones[0]["presenceCount"] = count
    runtime.zones[0]["_manual_override"] = True
    await runtime.broadcast_zones()
    return {"presenceCount": count, "mode": "manual"}


@app.delete("/api/zones/presence")
async def clear_presence_override():
    """Clear manual override, return to sensor fusion mode."""
    runtime.zones[0].pop("_manual_override", None)
    runtime.zones[0]["presenceCount"] = runtime._recompute_presence_count()
    await runtime.broadcast_zones()
    return {"presenceCount": runtime.zones[0]["presenceCount"], "mode": "fusion"}


@app.get("/api/scenario")
async def get_scenario():
    return {"scenario": "hardware-live", "mode": "hardware", "supported": False}


@app.post("/api/scenario/{scenario}")
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


@app.post("/api/csi/ingest")
async def ingest_csi(payload: dict):
    processed = runtime.csi_processor.process(payload)
    await runtime.handle_processed(processed)
    return {"processed": 1}
