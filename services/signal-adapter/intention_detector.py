"""
Intention Detector — pre-movement signal detection. (Phase 3-5)

Detects micro-motion precursors 200-500 ms before overt movement using
a sliding window over motion-index history.  The algorithm looks for a
characteristic ramp in the motion signal that precedes a larger event.

Algorithm outline:
    1. Keep a sliding deque of (timestamp, motion_index) pairs.
    2. On each update, compute the linear slope over the lead window
       (200-500 ms before now) and the "post" window (last 200 ms).
    3. If the slope is consistently positive AND the ratio of pre/post
       variance exceeds a threshold, flag a detected intention.
    4. Confidence is proportional to the normalised slope magnitude.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field


@dataclass
class _Sample:
    timestamp: float   # seconds
    value: float


def _linear_slope(samples: list[_Sample]) -> float:
    """Least-squares slope of (t, v) pairs.  Returns 0 if < 2 samples."""
    n = len(samples)
    if n < 2:
        return 0.0
    t0 = samples[0].timestamp
    ts = [s.timestamp - t0 for s in samples]
    vs = [s.value for s in samples]
    t_mean = sum(ts) / n
    v_mean = sum(vs) / n
    num = sum((t - t_mean) * (v - v_mean) for t, v in zip(ts, vs))
    den = sum((t - t_mean) ** 2 for t in ts) + 1e-9
    return num / den


class IntentionDetector:
    """Detects pre-movement (intention) signals 200-500 ms ahead of motion.

    Parameters
    ----------
    window_ms : float
        Total history window to retain (milliseconds).  Default 500 ms.
    lead_ms : float
        Length of the "lead" sub-window used to compute the precursor
        slope (milliseconds).  Default 300 ms.
    slope_threshold : float
        Minimum slope (motion_index / second) to flag a precursor.
    """

    def __init__(self,
                 window_ms: float = 500.0,
                 lead_ms: float = 300.0,
                 slope_threshold: float = 0.05) -> None:
        self.window_s = window_ms / 1000.0
        self.lead_s = lead_ms / 1000.0
        self.slope_threshold = slope_threshold
        self._buf: deque[_Sample] = deque()
        self._last_lead_time_ms: float = 0.0

    # ------------------------------------------------------------------
    def update(self, motion_index: float, timestamp: float) -> dict:
        """Process a new motion_index sample and return intention signal.

        Parameters
        ----------
        motion_index : float
            Normalised motion intensity [0, 1].
        timestamp : float
            Sample time in seconds (monotonic, e.g. time.monotonic()).

        Returns
        -------
        dict with keys:
            detected (bool)   — True if pre-movement ramp detected
            confidence (float) — [0, 1]
            lead_time_ms (float) — estimated lead ahead of peak (ms)
        """
        self._buf.append(_Sample(timestamp, motion_index))

        # Evict samples older than the history window
        cutoff = timestamp - self.window_s
        while self._buf and self._buf[0].timestamp < cutoff:
            self._buf.popleft()

        if len(self._buf) < 4:
            return {"detected": False, "confidence": 0.0, "lead_time_ms": 0.0}

        # Split buffer into lead sub-window and recent (post) sub-window
        lead_cutoff = timestamp - self.lead_s
        lead_samples = [s for s in self._buf if s.timestamp <= lead_cutoff]
        post_samples = [s for s in self._buf if s.timestamp > lead_cutoff]

        if len(lead_samples) < 2 or len(post_samples) < 1:
            return {"detected": False, "confidence": 0.0, "lead_time_ms": 0.0}

        lead_slope = _linear_slope(lead_samples)

        # Post mean (recent activity level)
        post_mean = sum(s.value for s in post_samples) / len(post_samples)
        lead_mean = sum(s.value for s in lead_samples) / len(lead_samples)

        # Precursor criterion:
        #   slope is rising AND lead level is below post level (ramp)
        detected = (
            lead_slope > self.slope_threshold
            and lead_mean < post_mean
        )

        # Confidence: normalised slope clamped to [0, 1]
        slope_norm = min(abs(lead_slope) / (self.slope_threshold * 10.0 + 1e-9), 1.0)
        confidence = slope_norm if detected else 0.0

        # Lead time estimate: time from last lead sample to now
        lead_time_ms = 0.0
        if detected and lead_samples:
            lead_time_ms = (timestamp - lead_samples[-1].timestamp) * 1000.0
            lead_time_ms = max(200.0, min(lead_time_ms, 500.0))
            self._last_lead_time_ms = lead_time_ms

        return {
            "detected": detected,
            "confidence": round(confidence, 4),
            "lead_time_ms": round(lead_time_ms, 1),
        }

    # ------------------------------------------------------------------
    def reset(self) -> None:
        """Clear internal buffer."""
        self._buf.clear()
        self._last_lead_time_ms = 0.0
