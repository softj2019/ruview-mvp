from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

from .csi_processor import ProcessedCSI


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

    def __init__(self):
        self._state: dict[str, str] = {}  # device_id -> last state

    def evaluate(self, csi: ProcessedCSI) -> list[DetectionEvent]:
        events: list[DetectionEvent] = []

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

        return events
