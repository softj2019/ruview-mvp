import time as _time
from collections import deque
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

try:
    from .csi_processor import ProcessedCSI
except ImportError:
    from csi_processor import ProcessedCSI


class DetectionEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: str
    severity: str
    zone: str = "default"
    device_id: str
    confidence: float
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: dict = Field(default_factory=dict)


class EventEngine:
    """Rule-based event detection from processed CSI data."""

    MOTION_THRESHOLD = 2.0
    PRESENCE_THRESHOLD = 0.5
    FALL_THRESHOLD = 8.0
    SIGNAL_WEAK_THRESHOLD = -80.0
    BREATHING_RATE_MAX = 30.0       # bpm — adult normal upper limit
    LOW_PRESENCE_THRESHOLD = 0.15  # presence_score below this = noise level
    LOITERING_THRESHOLD_SECONDS = 300  # 기본 배회 감지 임계값 (초)
    PANIC_MOTION_THRESHOLD = 2.0    # panic 판정용 이전 5초 평균 임계값
    PANIC_MOTION_PEAK = 2.0         # panic 판정용 순간 피크 임계값

    def __init__(self):
        self._state: dict[str, str] = {}  # device_id -> last state
        self._zone_presence_start: dict[str, float] = {}  # zone_id -> first presence timestamp
        self._motion_recent: dict[str, deque] = {}  # device_id -> recent motion_index (5s window)
        self._restricted_zone_ids: set[str] = set()  # zone_ids with restricted=True

    def update_zone_config(self, zone_id: str, restricted: bool = False, loitering_threshold_seconds: int | None = None) -> None:
        """존 설정 동기화 — /api/zones/{zone_id}/config PUT 호출 시 갱신."""
        if restricted:
            self._restricted_zone_ids.add(zone_id)
        else:
            self._restricted_zone_ids.discard(zone_id)

    def evaluate(self, csi: ProcessedCSI) -> list[DetectionEvent]:
        events: list[DetectionEvent] = []

        # High breathing rate check
        if csi.breathing_rate is not None and csi.breathing_rate > self.BREATHING_RATE_MAX:
            events.append(
                DetectionEvent(
                    type="high_breathing_rate",
                    severity="warning",
                    device_id=csi.device_id,
                    confidence=0.8,
                    metadata={"breathing_rate": csi.breathing_rate},
                )
            )

        # Low presence (noise level) check — excludes true-zero (no signal / empty room)
        if 0 < csi.presence_score < self.LOW_PRESENCE_THRESHOLD:
            events.append(
                DetectionEvent(
                    type="low_presence_noise",
                    severity="info",
                    device_id=csi.device_id,
                    confidence=0.7,
                    metadata={"presence_score": csi.presence_score},
                )
            )

        # Signal weak check
        if csi.rssi < self.SIGNAL_WEAK_THRESHOLD:
            events.append(
                DetectionEvent(
                    type="signal_weak",
                    severity="warning",
                    device_id=csi.device_id,
                    confidence=0.9,
                    metadata={"rssi": csi.rssi},
                )
            )

        # Motion / Presence detection
        prev_state = self._state.get(csi.device_id, "empty")

        if csi.motion_index > self.FALL_THRESHOLD:
            events.append(
                DetectionEvent(
                    type="fall_suspected",
                    severity="critical",
                    device_id=csi.device_id,
                    confidence=min(csi.motion_index / 15.0, 0.95),
                    metadata={"motion_index": csi.motion_index},
                )
            )
            self._state[csi.device_id] = "fall"

        elif csi.motion_index > self.MOTION_THRESHOLD:
            if prev_state != "motion":
                events.append(
                    DetectionEvent(
                        type="motion_active",
                        severity="info",
                        device_id=csi.device_id,
                        confidence=min(csi.motion_index / 5.0, 0.9),
                        metadata={"motion_index": csi.motion_index},
                    )
                )
            self._state[csi.device_id] = "motion"

        elif csi.motion_index > self.PRESENCE_THRESHOLD:
            if prev_state not in ("presence", "stationary"):
                events.append(
                    DetectionEvent(
                        type="presence_detected",
                        severity="info",
                        device_id=csi.device_id,
                        confidence=0.7,
                        metadata={"motion_index": csi.motion_index},
                    )
                )
            self._state[csi.device_id] = "presence"

        else:
            if prev_state in ("motion", "presence"):
                events.append(
                    DetectionEvent(
                        type="stationary_detected",
                        severity="info",
                        device_id=csi.device_id,
                        confidence=0.6,
                    )
                )
            self._state[csi.device_id] = "empty"

        # --- A) 수면 무호흡 이벤트 ---
        if csi.apnea_event and csi.apnea_duration >= 10.0:
            events.append(
                DetectionEvent(
                    type="apnea_detected",
                    severity="critical",
                    device_id=csi.device_id,
                    confidence=0.85,
                    metadata={
                        "apnea_duration": csi.apnea_duration,
                        "sleep_stage": csi.sleep_stage,
                    },
                )
            )

        # --- B) 부정맥 이벤트 ---
        if csi.arrhythmia_flag:
            events.append(
                DetectionEvent(
                    type="arrhythmia_detected",
                    severity="warning",
                    device_id=csi.device_id,
                    confidence=0.75,
                    metadata={
                        "pnn50": csi.pnn50,
                        "sdnn": csi.sdnn,
                        "rmssd": csi.rmssd,
                    },
                )
            )

        # --- C) 배회 감지 (Loitering) ---
        # zone_id를 device_id 기반으로 추적 (존 정보는 외부에서 설정 가능)
        zone_id = getattr(csi, "zone_id", csi.device_id)
        if csi.presence_score > self.PRESENCE_THRESHOLD:
            now_ts = _time.time()
            if zone_id not in self._zone_presence_start:
                self._zone_presence_start[zone_id] = now_ts
            else:
                elapsed = now_ts - self._zone_presence_start[zone_id]
                loitering_threshold = self.LOITERING_THRESHOLD_SECONDS
                if elapsed > loitering_threshold:
                    events.append(
                        DetectionEvent(
                            type="loitering_detected",
                            severity="warning",
                            device_id=csi.device_id,
                            confidence=0.7,
                            zone=zone_id,
                            metadata={
                                "elapsed_seconds": round(elapsed, 1),
                                "threshold_seconds": loitering_threshold,
                            },
                        )
                    )
        else:
            # presence 없으면 타이머 리셋
            self._zone_presence_start.pop(zone_id, None)

        # --- D) 긴급 동작 (Panic Motion) ---
        did = csi.device_id
        if did not in self._motion_recent:
            self._motion_recent[did] = deque(maxlen=50)  # ~5초 분량 (10Hz 기준)
        self._motion_recent[did].append(csi.motion_index)
        if csi.motion_index > self.PANIC_MOTION_PEAK:
            recent_vals = list(self._motion_recent[did])
            if len(recent_vals) >= 2:
                avg_recent = sum(recent_vals) / len(recent_vals)
                if avg_recent > self.PANIC_MOTION_THRESHOLD:
                    events.append(
                        DetectionEvent(
                            type="panic_motion",
                            severity="high",
                            device_id=csi.device_id,
                            confidence=min(csi.motion_index / 5.0, 0.95),
                            metadata={
                                "motion_index": csi.motion_index,
                                "avg_recent_motion": round(avg_recent, 3),
                            },
                        )
                    )

        # --- E) 제한구역 침입 ---
        # zone의 restricted 플래그는 외부에서 zone_restricted_ids set으로 관리
        if getattr(self, "_restricted_zone_ids", None) and csi.presence_score > self.PRESENCE_THRESHOLD:
            if zone_id in self._restricted_zone_ids:
                events.append(
                    DetectionEvent(
                        type="restricted_zone_entry",
                        severity="high",
                        device_id=csi.device_id,
                        confidence=0.8,
                        zone=zone_id,
                        metadata={"zone_id": zone_id},
                    )
                )

        return events
