"""
Gesture Classifier — DTW-based gesture recognition from Doppler sequences. (Phase 3-6)

Classifies short Doppler velocity sequences into one of the five predefined
gesture labels using Dynamic Time Warping (DTW) nearest-neighbour matching
against built-in prototype templates.

Reference:
    Sakoe & Chiba (1978) "Dynamic programming algorithm optimization for
    spoken word recognition"
"""
from __future__ import annotations

import math
import numpy as np

GESTURES = ['wave', 'clap', 'raise_hand', 'sit_down', 'stand_up']


# ---------------------------------------------------------------------------
# Prototype templates (1-D Doppler signature, normalised amplitude)
# Each template is a 1-D array representing a stylised Doppler envelope.
# ---------------------------------------------------------------------------
def _make_templates() -> dict[str, np.ndarray]:
    t = np.linspace(0, 1, 20)
    templates: dict[str, np.ndarray] = {}

    # wave: oscillating mid-freq pattern
    templates['wave'] = 0.6 * np.abs(np.sin(t * math.pi * 3))

    # clap: two sharp impulses close together
    clap = np.zeros(20)
    clap[5] = 1.0
    clap[6] = 0.8
    clap[13] = 1.0
    clap[14] = 0.8
    templates['clap'] = clap

    # raise_hand: slow steady rise then plateau
    templates['raise_hand'] = np.clip(t * 2.5, 0, 1.0)

    # sit_down: fast drop then stabilise
    templates['sit_down'] = np.clip(1.0 - t * 2.5, 0, 1.0)

    # stand_up: slow rise then fast spike
    stand = np.zeros(20)
    stand[:10] = np.linspace(0, 0.5, 10)
    stand[10:] = np.linspace(0.5, 1.0, 10) ** 0.5
    templates['stand_up'] = stand

    return templates


_TEMPLATES = _make_templates()


# ---------------------------------------------------------------------------
class GestureClassifier:
    """DTW nearest-neighbour gesture classifier.

    Parameters
    ----------
    sakoe_chiba_band : int
        Sakoe-Chiba warping path band width (in samples).  Limits the
        DTW search diagonal; 0 = unconstrained.
    """

    def __init__(self, sakoe_chiba_band: int = 5) -> None:
        self.band = sakoe_chiba_band
        self._templates = _TEMPLATES

    # ------------------------------------------------------------------
    def classify(self, doppler_sequence: list[np.ndarray]) -> tuple[str, float]:
        """Classify a Doppler sequence into a gesture label.

        Parameters
        ----------
        doppler_sequence : list of ndarray
            Time-ordered list of Doppler spectrum frames.  Each frame
            may be a 1-D velocity spectrum or a scalar velocity index.

        Returns
        -------
        (gesture_name, confidence)
        """
        if not doppler_sequence:
            return ('wave', 0.0)

        # Collapse each frame to a scalar energy / dominant velocity
        seq = np.array([
            float(np.linalg.norm(np.asarray(frame, dtype=np.float64)))
            for frame in doppler_sequence
        ], dtype=np.float64)

        # Normalise to [0, 1]
        seq_min, seq_max = seq.min(), seq.max()
        rng = seq_max - seq_min
        if rng > 1e-9:
            seq = (seq - seq_min) / rng
        else:
            seq = np.zeros_like(seq)

        best_label = 'wave'
        best_dist = float('inf')

        for label, proto in self._templates.items():
            dist = self._dtw_distance(seq, proto)
            if dist < best_dist:
                best_dist = dist
                best_label = label

        # Convert DTW distance to confidence: exponential decay
        # distance == 0 → confidence 1.0; larger → approaches 0
        confidence = float(math.exp(-best_dist))
        confidence = round(min(max(confidence, 0.0), 1.0), 4)

        return (best_label, confidence)

    # ------------------------------------------------------------------
    def _dtw_distance(self, s1: np.ndarray, s2: np.ndarray) -> float:
        """Compute Sakoe-Chiba band-constrained DTW distance between s1 and s2.

        Parameters
        ----------
        s1, s2 : 1-D ndarray
            Input sequences (may differ in length).

        Returns
        -------
        float — DTW distance (lower = more similar).
        """
        n, m = len(s1), len(s2)
        INF = float('inf')
        # DTW cost matrix
        dtw = np.full((n + 1, m + 1), INF, dtype=np.float64)
        dtw[0, 0] = 0.0

        band = self.band if self.band > 0 else max(n, m)

        for i in range(1, n + 1):
            j_lo = max(1, i - band)
            j_hi = min(m, i + band)
            for j in range(j_lo, j_hi + 1):
                cost = abs(float(s1[i - 1]) - float(s2[j - 1]))
                prev = min(dtw[i - 1, j], dtw[i, j - 1], dtw[i - 1, j - 1])
                dtw[i, j] = cost + prev

        raw = dtw[n, m]
        # Normalise by path length approximation
        return raw / (n + m)
