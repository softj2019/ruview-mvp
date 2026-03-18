from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class ProcessedCSI:
    device_id: str
    timestamp: str
    amplitude: list[float]
    phase: list[float]
    rssi: float
    noise_floor: float
    motion_index: float
    breathing_rate: float | None
    heart_rate: float | None


class CSIProcessor:
    """Process raw CSI data from RuView sensing server."""

    def __init__(self):
        self._amplitude_buffer: dict[str, list[list[float]]] = {}
        self._buffer_size = 50

    def process(self, raw: dict[str, Any]) -> ProcessedCSI:
        device_id = raw.get("device_id", "unknown")
        timestamp = raw.get("timestamp", "")
        csi_data = raw.get("csi_data", [])

        # Extract amplitude and phase from complex CSI
        if isinstance(csi_data, list) and len(csi_data) > 0:
            csi_array = np.array(csi_data, dtype=np.complex64)
            amplitude = np.abs(csi_array).tolist()
            phase = np.angle(csi_array).tolist()
        else:
            amplitude = []
            phase = []

        # Buffer for motion detection
        if device_id not in self._amplitude_buffer:
            self._amplitude_buffer[device_id] = []
        self._amplitude_buffer[device_id].append(amplitude)
        if len(self._amplitude_buffer[device_id]) > self._buffer_size:
            self._amplitude_buffer[device_id].pop(0)

        # Calculate motion index (variance of amplitude over time)
        motion_index = self._calc_motion_index(device_id)

        # Extract vitals (placeholder - requires more sophisticated DSP)
        breathing_rate = None
        heart_rate = None

        return ProcessedCSI(
            device_id=device_id,
            timestamp=timestamp,
            amplitude=amplitude,
            phase=phase,
            rssi=raw.get("rssi", -100.0),
            noise_floor=raw.get("noise_floor", -95.0),
            motion_index=motion_index,
            breathing_rate=breathing_rate,
            heart_rate=heart_rate,
        )

    def _calc_motion_index(self, device_id: str) -> float:
        buf = self._amplitude_buffer.get(device_id, [])
        if len(buf) < 5:
            return 0.0
        arr = np.array(buf[-10:])
        return float(np.std(arr))
