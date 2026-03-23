"""
CSI Processor — WiFi Channel State Information signal processing.

Extracts motion, breathing rate, and heart rate from ESP32 CSI data.

Algorithms ported from ruvnet/RuView:
  - Phase extraction & unwrapping (edge_processing.c:126-140)
  - Welford online statistics (edge_processing.c:146-165)
  - Top-K subcarrier selection (edge_processing.c:290-318)
  - Bandpass filtering (scipy Butterworth, equiv to Biquad IIR)
  - Zero-crossing BPM estimation (edge_processing.c:179-206)
  - FFT spectral peak detection (ruview_live.py)
"""
import math
from collections import deque
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy import signal as scipy_signal


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
    presence_score: float
    top_k_variance: list[float]
    estimated_persons: int = 0
    per_person_breathing: list[float] | None = None


class WelfordStats:
    """Welford online statistics — from ruvsense/field_model.rs."""

    __slots__ = ("count", "mean", "m2")

    def __init__(self):
        self.count = 0
        self.mean = 0.0
        self.m2 = 0.0

    def update(self, value: float):
        self.count += 1
        delta = value - self.mean
        self.mean += delta / self.count
        delta2 = value - self.mean
        self.m2 += delta * delta2

    def variance(self) -> float:
        return self.m2 / self.count if self.count > 1 else 0.0

    def std(self) -> float:
        return math.sqrt(self.variance())

    def z_score(self, value: float) -> float:
        s = self.std()
        return abs(value - self.mean) / s if s > 0 else 0.0


class CSIProcessor:
    """Process raw CSI data with vital signs extraction."""

    BUFFER_SIZE = 256       # Phase history depth (matching EDGE_PHASE_HISTORY_LEN)
    TOP_K = 8               # Top-K subcarriers to track
    SAMPLE_RATE = 20.0      # Approximate CSI frame rate (Hz)
    MIN_FRAMES_VITALS = 64  # Minimum frames before BPM estimation
    CORR_THRESHOLD = 0.7    # Correlation threshold for same-person clustering

    def __init__(self):
        # Per-device state
        self._amplitude_buffer: dict[str, deque] = {}
        self._phase_history: dict[str, deque] = {}  # deque of phase arrays
        self._prev_phase: dict[str, np.ndarray | None] = {}
        self._subcarrier_var: dict[str, list[WelfordStats]] = {}
        self._top_k: dict[str, list[int]] = {}
        self._frame_count: dict[str, int] = {}
        # Per-subcarrier phase histories for multi-person separation
        self._per_sc_phase: dict[str, dict[int, deque]] = {}

        # Butterworth filter coefficients (computed once)
        self._breath_sos = scipy_signal.butter(
            2, [0.1, 0.5], btype="band", fs=self.SAMPLE_RATE, output="sos"
        )
        self._heart_sos = scipy_signal.butter(
            2, [0.8, 2.0], btype="band", fs=self.SAMPLE_RATE, output="sos"
        )

    def process(self, raw: dict[str, Any]) -> ProcessedCSI:
        device_id = raw.get("device_id", "unknown")
        timestamp = raw.get("timestamp", "")
        csi_data = raw.get("csi_data", [])

        # Initialize per-device state
        if device_id not in self._frame_count:
            self._frame_count[device_id] = 0
            self._phase_history[device_id] = deque(maxlen=self.BUFFER_SIZE)
            self._prev_phase[device_id] = None
            self._amplitude_buffer[device_id] = deque(maxlen=50)

        self._frame_count[device_id] += 1

        # Extract amplitude and phase from complex CSI
        if isinstance(csi_data, list) and len(csi_data) > 0:
            csi_array = np.array(csi_data, dtype=np.complex64)
            amplitude = np.abs(csi_array).tolist()
            phase_raw = np.angle(csi_array)

            # Phase unwrapping (remove 2π discontinuities)
            phase = self._unwrap_phase(device_id, phase_raw)
        else:
            amplitude = []
            phase = np.array([])

        # Amplitude buffer for motion detection
        self._amplitude_buffer[device_id].append(amplitude)

        # Update per-subcarrier variance tracking
        n_sc = len(amplitude)
        self._update_subcarrier_variance(device_id, amplitude, n_sc)

        # Select top-K subcarriers
        top_k_indices = self._select_top_k(device_id, n_sc)
        self._top_k[device_id] = top_k_indices

        # Store phase history for top-K subcarriers
        if len(phase) > 0 and top_k_indices:
            avg_phase = float(np.mean([phase[i] for i in top_k_indices if i < len(phase)]))
            self._phase_history[device_id].append(avg_phase)

            # Store per-subcarrier phase for multi-person separation
            if device_id not in self._per_sc_phase:
                self._per_sc_phase[device_id] = {}
            for sc_idx in top_k_indices:
                if sc_idx < len(phase):
                    if sc_idx not in self._per_sc_phase[device_id]:
                        self._per_sc_phase[device_id][sc_idx] = deque(maxlen=self.BUFFER_SIZE)
                    self._per_sc_phase[device_id][sc_idx].append(float(phase[sc_idx]))

        # Motion index
        motion_index = self._calc_motion_index(device_id)

        # Presence score (based on top-K variance)
        top_k_var = self._get_top_k_variance(device_id)
        presence_score = float(np.mean(top_k_var)) if top_k_var else 0.0

        # Vital signs extraction
        breathing_rate = None
        heart_rate = None
        history = self._phase_history.get(device_id)
        if history and len(history) >= self.MIN_FRAMES_VITALS:
            phase_arr = np.array(list(history))
            breathing_rate = self._extract_breathing(phase_arr)
            heart_rate = self._extract_heart_rate(phase_arr)

        # Multi-person separation via subcarrier correlation clustering
        estimated_persons, per_person_breathing = self._estimate_persons(device_id)

        return ProcessedCSI(
            device_id=device_id,
            timestamp=timestamp,
            amplitude=amplitude,
            phase=phase.tolist() if isinstance(phase, np.ndarray) else [],
            rssi=raw.get("rssi", -100.0),
            noise_floor=raw.get("noise_floor", -95.0),
            motion_index=motion_index,
            breathing_rate=breathing_rate,
            heart_rate=heart_rate,
            presence_score=presence_score,
            top_k_variance=top_k_var,
            estimated_persons=estimated_persons,
            per_person_breathing=per_person_breathing,
        )

    def _estimate_persons(self, device_id: str) -> tuple[int, list[float] | None]:
        """Estimate person count via subcarrier correlation clustering.

        Algorithm (ref: ruvnet/RuView Dynamic Min-Cut):
        1. Build correlation matrix from Top-K subcarrier phase histories
        2. Cluster correlated subcarriers (correlation > threshold = same person)
        3. Extract per-cluster breathing rate independently
        4. Return (person_count, per_person_breathing_rates)
        """
        sc_phases = self._per_sc_phase.get(device_id, {})
        top_k = self._top_k.get(device_id, [])

        # Need at least 2 subcarriers with sufficient history
        active_scs = [sc for sc in top_k if sc in sc_phases and len(sc_phases[sc]) >= self.MIN_FRAMES_VITALS]
        if len(active_scs) < 2:
            return (0, None)

        # Align histories to the same length (use the shortest)
        min_len = min(len(sc_phases[sc]) for sc in active_scs)
        histories = np.array([list(sc_phases[sc])[-min_len:] for sc in active_scs])
        n_sc = len(active_scs)

        # Step 1: Build correlation matrix
        # Bandpass-filter each subcarrier in the breathing band before correlation
        filtered = np.zeros_like(histories)
        for i in range(n_sc):
            try:
                filtered[i] = scipy_signal.sosfiltfilt(self._breath_sos, histories[i])
            except Exception:
                filtered[i] = histories[i]

        corr_matrix = np.corrcoef(filtered)
        # Handle NaN from constant signals
        corr_matrix = np.nan_to_num(corr_matrix, nan=0.0)

        # Step 2: Threshold-based clustering (union-find)
        # Two subcarriers with correlation > threshold belong to the same person
        parent = list(range(n_sc))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for i in range(n_sc):
            for j in range(i + 1, n_sc):
                if abs(corr_matrix[i, j]) > self.CORR_THRESHOLD:
                    union(i, j)

        # Collect clusters
        clusters: dict[int, list[int]] = {}
        for i in range(n_sc):
            root = find(i)
            clusters.setdefault(root, []).append(i)

        # Step 3: Extract breathing rate per cluster
        per_person_breathing: list[float] = []
        for members in clusters.values():
            # Average the filtered signals within the cluster
            cluster_signal = np.mean(filtered[members], axis=0)
            bpm = self._extract_breathing(cluster_signal)
            if bpm is not None:
                per_person_breathing.append(bpm)

        # Person count = number of clusters that have a detectable breathing rate
        # If no breathing detected in any cluster, fall back to cluster count
        # only if overall presence_score suggests someone is there
        estimated_persons = len(per_person_breathing) if per_person_breathing else 0

        return (estimated_persons, per_person_breathing if per_person_breathing else None)

    def _unwrap_phase(self, device_id: str, phase_raw: np.ndarray) -> np.ndarray:
        """Phase unwrapping — remove 2π discontinuities.
        Ref: edge_processing.c:134-140"""
        prev = self._prev_phase.get(device_id)
        if prev is not None and len(prev) == len(phase_raw):
            diff = phase_raw - prev
            # Wrap to [-π, π]
            diff = (diff + np.pi) % (2 * np.pi) - np.pi
            phase_raw = prev + diff
        self._prev_phase[device_id] = phase_raw.copy()
        return phase_raw

    def _update_subcarrier_variance(self, device_id: str, amplitude: list[float], n_sc: int):
        """Per-subcarrier Welford variance tracking.
        Ref: edge_processing.c:146-165"""
        if device_id not in self._subcarrier_var:
            self._subcarrier_var[device_id] = [WelfordStats() for _ in range(max(n_sc, 1))]

        stats = self._subcarrier_var[device_id]
        # Resize if subcarrier count changes
        while len(stats) < n_sc:
            stats.append(WelfordStats())

        for i in range(min(n_sc, len(amplitude))):
            stats[i].update(amplitude[i])

    def _select_top_k(self, device_id: str, n_sc: int) -> list[int]:
        """Select top-K subcarriers by variance.
        Ref: edge_processing.c:290-318"""
        stats = self._subcarrier_var.get(device_id, [])
        if len(stats) < self.TOP_K:
            return list(range(min(len(stats), n_sc)))

        # Get variance for each subcarrier
        variances = [(i, stats[i].variance()) for i in range(min(n_sc, len(stats)))]
        variances.sort(key=lambda x: x[1], reverse=True)
        return [idx for idx, _ in variances[:self.TOP_K]]

    def _get_top_k_variance(self, device_id: str) -> list[float]:
        """Get variance values for top-K subcarriers."""
        indices = self._top_k.get(device_id, [])
        stats = self._subcarrier_var.get(device_id, [])
        return [stats[i].variance() for i in indices if i < len(stats)]

    def _calc_motion_index(self, device_id: str) -> float:
        buf = self._amplitude_buffer.get(device_id, [])
        if len(buf) < 5:
            return 0.0
        recent = buf[-10:]
        min_len = min(len(a) for a in recent)
        if min_len == 0:
            return 0.0
        arr = np.array([a[:min_len] for a in recent])
        return float(np.std(arr))

    def _extract_breathing(self, phase_arr: np.ndarray) -> float | None:
        """Extract breathing rate from phase history.
        Breathing: 0.1-0.5 Hz (6-30 BPM).
        Ref: edge_processing.c Biquad + zero-crossing"""
        try:
            # Apply bandpass filter
            filtered = scipy_signal.sosfiltfilt(self._breath_sos, phase_arr)

            # Method 1: Zero-crossing BPM
            bpm_zc = self._zero_crossing_bpm(filtered, self.SAMPLE_RATE)

            # Method 2: FFT peak detection
            bpm_fft = self._fft_peak_bpm(filtered, self.SAMPLE_RATE, f_lo=0.1, f_hi=0.5)

            # Use FFT result if available and reasonable, else zero-crossing
            if bpm_fft and 6 <= bpm_fft <= 30:
                return round(bpm_fft, 1)
            if bpm_zc and 6 <= bpm_zc <= 30:
                return round(bpm_zc, 1)
            return None
        except Exception:
            return None

    def _extract_heart_rate(self, phase_arr: np.ndarray) -> float | None:
        """Extract heart rate from phase history.
        Heart rate: 0.8-2.0 Hz (48-120 BPM).
        Ref: edge_processing.c Biquad + zero-crossing"""
        try:
            filtered = scipy_signal.sosfiltfilt(self._heart_sos, phase_arr)

            bpm_fft = self._fft_peak_bpm(filtered, self.SAMPLE_RATE, f_lo=0.8, f_hi=2.0)
            bpm_zc = self._zero_crossing_bpm(filtered, self.SAMPLE_RATE)

            if bpm_fft and 40 <= bpm_fft <= 180:
                return round(bpm_fft, 1)
            if bpm_zc and 40 <= bpm_zc <= 180:
                return round(bpm_zc, 1)
            return None
        except Exception:
            return None

    @staticmethod
    def _zero_crossing_bpm(filtered: np.ndarray, fs: float) -> float | None:
        """Count positive zero-crossings to estimate BPM.
        Ref: edge_processing.c:179-206"""
        crossings = []
        for i in range(1, len(filtered)):
            if filtered[i - 1] <= 0 < filtered[i]:
                crossings.append(i)

        if len(crossings) < 2:
            return None

        # Average period between crossings
        periods = [crossings[i + 1] - crossings[i] for i in range(len(crossings) - 1)]
        avg_period = sum(periods) / len(periods)
        if avg_period <= 0:
            return None

        freq = fs / avg_period
        return freq * 60.0  # Hz → BPM

    @staticmethod
    def _fft_peak_bpm(filtered: np.ndarray, fs: float, f_lo: float, f_hi: float) -> float | None:
        """FFT-based peak frequency detection.
        Ref: ruview_live.py spectral analysis"""
        n = len(filtered)
        if n < 16:
            return None

        # Welch PSD for robust spectral estimation
        freqs, psd = scipy_signal.welch(filtered, fs=fs, nperseg=min(n, 64), noverlap=min(n // 2, 32))

        # Find peak in target band
        mask = (freqs >= f_lo) & (freqs <= f_hi)
        if not np.any(mask):
            return None

        band_psd = psd[mask]
        band_freqs = freqs[mask]

        peak_idx = np.argmax(band_psd)
        peak_freq = band_freqs[peak_idx]
        peak_power = band_psd[peak_idx]

        # Reject if peak is too weak (noise)
        if peak_power < np.mean(band_psd) * 1.5:
            return None

        return float(peak_freq * 60.0)  # Hz → BPM
