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

SOTA signal processing (ported from ruvnet/RuView Rust crates):
  - Hampel filter (wifi-densepose-signal/hampel.rs) — MAD-based outlier removal
  - CSI Ratio / conjugate multiplication (wifi-densepose-signal/csi_ratio.rs) — phase offset cancellation
  - Fresnel zone breathing model (wifi-densepose-signal/fresnel.rs) — physics-based confidence weighting
"""
import math
from collections import deque
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy import signal as scipy_signal
from scipy.interpolate import CubicSpline

try:
    from sensing import PresenceClassifier, RssiFeatureExtractor, RssiCollector
    _SENSING_AVAILABLE = True
except ImportError:
    _SENSING_AVAILABLE = False


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
    fresnel_confidence: float = 0.0
    hampel_outliers_removed: int = 0
    estimated_persons: int = 0
    per_person_breathing: list[float] | None = None
    doppler_velocity: float | None = None
    velocity_profile: list[float] | None = None
    max_velocity: float | None = None
    csi_pose: str | None = None
    csi_pose_confidence: float = 0.0
    hrv: dict | None = None
    gesture: str | None = None
    gesture_confidence: float = 0.0
    through_wall: bool = False
    # Phase 3-9/3-10: sensing 패키지 분류 결과
    presence_motion_level: str | None = None   # "absent" | "present_still" | "active"
    presence_confidence: float = 0.0


class WelfordStats:
    """Windowed Welford online statistics with EMA decay.

    Uses exponential moving average approach: after the window fills,
    each update applies a decay factor so recent data is weighted more
    heavily and variance stays sensitive to environmental changes.
    """

    __slots__ = ("count", "mean", "m2", "_window", "_alpha")

    WINDOW = 2000       # effective window size
    ALPHA = 0.998       # decay factor per sample (≈ 2000-sample half-life)

    def __init__(self, window: int = WINDOW, alpha: float = ALPHA):
        self.count = 0
        self.mean = 0.0
        self.m2 = 0.0
        self._window = window
        self._alpha = alpha

    def update(self, value: float):
        self.count += 1
        if self.count <= self._window:
            # Standard Welford accumulation during warmup
            delta = value - self.mean
            self.mean += delta / self.count
            delta2 = value - self.mean
            self.m2 += delta * delta2
        else:
            # EMA decay: blend new sample, forget old proportionally
            self.m2 *= self._alpha
            delta = value - self.mean
            self.mean += (1 - self._alpha) * delta
            delta2 = value - self.mean
            self.m2 += delta * delta2
            # Keep effective count bounded to window size
            self.count = self._window

    def variance(self) -> float:
        return self.m2 / (self.count - 1) if self.count > 1 else 0.0

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

    # Hampel filter config (ported from wifi-densepose-signal/hampel.rs)
    HAMPEL_HALF_WINDOW = 3  # Half-window size (total = 2*3+1 = 7 samples)
    HAMPEL_THRESHOLD = 3.0  # Outlier threshold in units of estimated sigma
    MAD_SCALE = 1.4826      # MAD-to-sigma scale for Gaussian: sigma = 1.4826 * MAD

    # Fresnel zone model config (ported from wifi-densepose-signal/fresnel.rs)
    SPEED_OF_LIGHT = 2.998e8            # m/s
    DEFAULT_FREQUENCY = 5.8e9           # 5.8 GHz WiFi (Hz)
    DEFAULT_D_TX_BODY = 3.0             # TX to body (meters)
    DEFAULT_D_BODY_RX = 2.0             # Body to RX (meters)
    FRESNEL_MIN_DISPLACEMENT = 0.003    # Min breathing displacement (m)
    FRESNEL_MAX_DISPLACEMENT = 0.015    # Max breathing displacement (m)

    # HRV computation interval (compute every N frames)
    HRV_INTERVAL_FRAMES = 20  # ~1 second at 20 Hz
    HRV_HR_HISTORY_SIZE = 60  # last 60 HR values

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
        # Per-device heart rate history for HRV (last 60 values)
        self._hr_history: dict[str, deque] = {}
        # Cached HRV result per device
        self._last_hrv: dict[str, dict | None] = {}
        # Per-device motion_index history for gesture recognition (last 60 = 3s at 20Hz)
        self._gesture_history: dict[str, deque] = {}
        self._gesture_history_size = 60

        # Hardware normalizer state (작업 3: Phase 3-1)
        # _hw_offsets[device_id] = {'sum': np.ndarray, 'count': int, 'baseline': np.ndarray | None}
        self._hw_offsets: dict[str, dict] = {}
        self.HW_NORM_WARMUP_FRAMES = 100  # 기준 설정에 필요한 최소 프레임 수

        # Butterworth filter coefficients (computed once)
        self._breath_sos = scipy_signal.butter(
            2, [0.1, 0.5], btype="band", fs=self.SAMPLE_RATE, output="sos"
        )
        self._heart_sos = scipy_signal.butter(
            2, [0.8, 2.0], btype="band", fs=self.SAMPLE_RATE, output="sos"
        )

        # Phase 3-9/3-10: sensing 패키지 통합
        if _SENSING_AVAILABLE:
            self._rssi_collector = RssiCollector(window_size=500)
            self._rssi_feature_extractor = RssiFeatureExtractor(
                sample_rate_hz=self.SAMPLE_RATE,
                cusum_threshold=3.0,
                cusum_drift=0.5,
            )
            self._presence_classifier = PresenceClassifier(
                presence_variance_threshold=0.5,
                motion_energy_threshold=0.1,
                history_size=5,
                hysteresis_ratio=0.6,
            )
        else:
            self._rssi_collector = None
            self._rssi_feature_extractor = None
            self._presence_classifier = None

    def process(self, raw: dict[str, Any]) -> ProcessedCSI:
        """Process raw CSI frame through the full signal pipeline.

        Pipeline order:
          1. CSI Ratio (conjugate multiplication) — phase offset cancellation
          2. Hampel filter — robust MAD-based outlier removal on amplitude
          3. Phase unwrapping — remove 2pi discontinuities
          4. Variance tracking / top-K selection / vitals extraction
          5. Fresnel zone model — physics-based confidence weighting
        """
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

        hampel_outliers_removed = 0

        # Extract amplitude and phase from complex CSI
        if isinstance(csi_data, list) and len(csi_data) > 0:
            csi_array = np.array(csi_data, dtype=np.complex64)

            # --- Step 1: CSI Ratio — phase offset cancellation ---
            # Apply conjugate multiplication against reference subcarrier
            # to cancel common hardware phase offsets (CFO, SFO, PDD).
            # Ported from wifi-densepose-signal/csi_ratio.rs
            csi_array = self._apply_csi_ratio(csi_array)

            amplitude = np.abs(csi_array).tolist()
            phase_raw = np.angle(csi_array)

            # --- Step 2: Hampel filter — outlier removal on amplitude ---
            # Replace z-score outlier detection with MAD-based Hampel filter.
            # More robust: resists up to 50% contamination unlike z-score.
            # Ported from wifi-densepose-signal/hampel.rs
            amplitude, hampel_outliers_removed = self._hampel_filter(amplitude)

            # --- Step 2b: Hardware normalizer — cross-device amplitude 정규화 ---
            # 다른 ESP32 보드 간 CSI 진폭 편차 보정 (Phase 3-1)
            amplitude = self.normalize_hardware(np.array(amplitude, dtype=np.float64), device_id).tolist()

            # --- Step 3: Phase unwrapping (remove 2pi discontinuities) ---
            phase = self._unwrap_phase(device_id, phase_raw)
        else:
            amplitude = []
            phase = np.array([])

        # Amplitude buffer for motion detection
        self._amplitude_buffer[device_id].append(amplitude)

        # --- Step 4: Existing variance/vitals extraction ---
        # Update per-subcarrier variance tracking
        n_sc = len(amplitude)
        self._update_subcarrier_variance(device_id, amplitude, n_sc)

        # Select top-K subcarriers (sensitivity-based filtering)
        top_k_indices = self._select_top_k_sensitivity(device_id, n_sc)
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
            _br_raw = self._extract_breathing(phase_arr)
            # 범위 클램프: 정상 호흡 6~30 BPM 외 값은 0.0 반환 (신뢰 불가 신호)
            if _br_raw is not None and 6.0 <= _br_raw <= 30.0:
                breathing_rate = _br_raw
            else:
                breathing_rate = 0.0 if _br_raw is not None else None
            heart_rate = self._extract_heart_rate(phase_arr)

        # --- Step 5: Fresnel zone confidence weighting ---
        # Validate breathing detection against physics-based Fresnel model.
        # Ported from wifi-densepose-signal/fresnel.rs
        fresnel_confidence = 0.0
        if breathing_rate is not None and len(amplitude) > 0:
            fresnel_confidence = self._fresnel_breathing_confidence(amplitude)

        # --- Step 6: Spectrogram (STFT) — Doppler velocity extraction ---
        # Compute time-frequency decomposition of phase history to extract
        # dominant Doppler frequency for motion classification.
        # Ported concept from wifi-densepose-signal/spectrogram.rs
        doppler_velocity = None
        if history and len(history) >= self.MIN_FRAMES_VITALS:
            phase_arr_doppler = np.array(list(history))
            _spectrogram, doppler_velocity = self._compute_spectrogram(phase_arr_doppler)

        # --- Step 6b: Body Velocity Profile (BVP) — Widar 3.0 concept ---
        velocity_profile = None
        max_velocity = None
        if history and len(history) >= self.MIN_FRAMES_VITALS:
            phase_arr_bvp = np.array(list(history))
            velocity_profile, max_velocity = self._compute_bvp(phase_arr_bvp)

        # Multi-person separation via subcarrier correlation clustering
        estimated_persons, per_person_breathing = self._estimate_persons(device_id)

        # --- Step 7: CSI-based pose classification ---
        csi_pose, csi_pose_confidence = self._classify_pose_csi(
            motion_index, breathing_rate, doppler_velocity
        )

        # --- Step 8: HRV analysis (Phase Additional C) ---
        hrv = self._update_hrv(device_id, heart_rate)

        # --- Step 9: Gesture recognition via DTW (Additional B) ---
        gesture, gesture_confidence = self._detect_gesture(device_id, motion_index)

        # --- Step 10: Through-wall detection (Additional E) ---
        through_wall = self._estimate_wall_attenuation(
            rssi=raw.get("rssi", -100.0),
            presence_score=presence_score,
            motion_index=motion_index,
        )

        # --- Step 11: RSSI 기반 재실 분류 (Phase 3-9/3-10) ---
        presence_motion_level: str | None = None
        presence_confidence: float = 0.0
        rssi_val = raw.get("rssi", -100.0)
        if _SENSING_AVAILABLE and self._rssi_collector is not None:
            self._rssi_collector.push(device_id, rssi_val)
            rssi_arr = self._rssi_collector.get_rssi_array(device_id)
            if len(rssi_arr) >= 4:
                features = self._rssi_feature_extractor.extract_from_array(rssi_arr)
                sensing_result = self._presence_classifier.classify(
                    features, device_id=device_id
                )
                presence_motion_level = sensing_result.motion_level.value
                presence_confidence = sensing_result.confidence
                # CUSUM 변화점 → event_engine 연동을 위해 로그 기록
                if sensing_result.n_change_points > 0:
                    import logging as _log
                    _log.getLogger(__name__).debug(
                        "CUSUM 변화점 감지 [%s]: %d개 (motion=%s, confidence=%.2f)",
                        device_id,
                        sensing_result.n_change_points,
                        presence_motion_level,
                        presence_confidence,
                    )

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
            fresnel_confidence=fresnel_confidence,
            hampel_outliers_removed=hampel_outliers_removed,
            estimated_persons=estimated_persons,
            per_person_breathing=per_person_breathing,
            doppler_velocity=doppler_velocity,
            velocity_profile=velocity_profile,
            max_velocity=max_velocity,
            csi_pose=csi_pose,
            csi_pose_confidence=csi_pose_confidence,
            hrv=hrv,
            gesture=gesture,
            gesture_confidence=gesture_confidence,
            through_wall=through_wall,
            presence_motion_level=presence_motion_level,
            presence_confidence=presence_confidence,
        )

    # ------------------------------------------------------------------
    # HRV analysis (Phase Additional C)
    # ------------------------------------------------------------------

    def _update_hrv(self, device_id: str, heart_rate: float | None) -> dict | None:
        """Track heart rate and periodically compute HRV.

        Stores last 60 HR values per device. Recomputes HRV every
        HRV_INTERVAL_FRAMES frames.

        Returns:
            HRV dict or cached result, None if insufficient data.
        """
        if heart_rate is not None and 40.0 <= heart_rate <= 180.0:
            if device_id not in self._hr_history:
                self._hr_history[device_id] = deque(maxlen=self.HRV_HR_HISTORY_SIZE)
            self._hr_history[device_id].append(heart_rate)

        frame_count = self._frame_count.get(device_id, 0)

        # Compute HRV periodically
        if frame_count % self.HRV_INTERVAL_FRAMES == 0:
            hr_hist = self._hr_history.get(device_id)
            if hr_hist and len(hr_hist) >= 10:
                hrv = self._compute_hrv_full(list(hr_hist))
                self._last_hrv[device_id] = hrv
                return hrv

        # Return cached result between computations
        return self._last_hrv.get(device_id)

    @staticmethod
    def _compute_hrv(rr_intervals: list[float]) -> dict:
        """HRV 메트릭 계산 (Phase 3-2 완전 구현).

        Args:
            rr_intervals: R-R 간격 목록 (ms 단위), 3개 미만이면 모두 0.0 반환.

        Returns:
            {
                'sdnn': float,    # 표준편차 (ms) — 전체 HRV
                'rmssd': float,   # 연속 차이 RMS (ms) — 단기 HRV
                'pnn50': float,   # 50ms 초과 비율 (%) — 부교감신경 지표
                'mean_rr': float  # 평균 R-R 간격 (ms)
            }
        """
        # 3개 미만이면 모두 0.0 반환
        if len(rr_intervals) < 3:
            return {"sdnn": 0.0, "rmssd": 0.0, "pnn50": 0.0, "mean_rr": 0.0}

        rr = np.array(rr_intervals, dtype=np.float64)

        # SDNN: sqrt(mean((RR_i - mean_RR)^2))  — 전체 HRV (population std)
        sdnn = float(np.sqrt(np.mean((rr - np.mean(rr)) ** 2)))

        # RMSSD: sqrt(mean((RR_i+1 - RR_i)^2))  — 단기 HRV
        rr_diff = np.diff(rr)
        rmssd = float(np.sqrt(np.mean(rr_diff ** 2))) if len(rr_diff) > 0 else 0.0

        # pNN50: 100 * count(|RR_i+1 - RR_i| > 50) / (n-1)
        nn50 = int(np.sum(np.abs(rr_diff) > 50.0))
        pnn50 = (nn50 / len(rr_diff)) * 100.0 if len(rr_diff) > 0 else 0.0

        mean_rr = float(np.mean(rr))

        return {
            "sdnn": round(sdnn, 2),
            "rmssd": round(rmssd, 2),
            "pnn50": round(pnn50, 2),
            "mean_rr": round(mean_rr, 2),
        }

    @staticmethod
    def _compute_hrv_full(heart_rate_history: list[float]) -> dict | None:
        """Compute full HRV metrics including LF/HF ratio from HR history.

        Args:
            heart_rate_history: List of HR values (BPM), at least 10 values.

        Returns:
            Dict with SDNN, RMSSD, PNN50, LF/HF ratio, stress level.
            None if insufficient valid data.
        """
        hr_arr = np.array(heart_rate_history, dtype=np.float64)

        # Filter out invalid values
        valid = hr_arr[(hr_arr >= 40) & (hr_arr <= 180)]
        if len(valid) < 10:
            return None

        # Convert HR (BPM) to R-R intervals (ms): rr = 60000 / hr
        rr = 60000.0 / valid

        # --- SDNN: standard deviation of R-R intervals ---
        sdnn = float(np.std(rr, ddof=1))

        # --- RMSSD: root mean square of successive differences ---
        rr_diff = np.diff(rr)
        rmssd = float(np.sqrt(np.mean(rr_diff ** 2)))

        # --- PNN50: percentage of successive differences > 50ms ---
        nn50 = int(np.sum(np.abs(rr_diff) > 50.0))
        pnn50 = (nn50 / len(rr_diff)) * 100.0 if len(rr_diff) > 0 else 0.0

        # --- LF/HF ratio via FFT ---
        # Interpolate R-R intervals to uniform 4 Hz sampling for spectral analysis
        n = len(rr)
        # Cumulative time axis from R-R intervals (seconds)
        t_rr = np.cumsum(rr) / 1000.0  # ms -> s
        t_rr = t_rr - t_rr[0]  # start at 0

        lf_hf_ratio = None
        if n >= 16 and t_rr[-1] > 0:
            # Interpolate to uniform 4 Hz
            fs_interp = 4.0
            t_uniform = np.arange(0, t_rr[-1], 1.0 / fs_interp)
            if len(t_uniform) >= 16:
                rr_interp = np.interp(t_uniform, t_rr, rr)
                # Remove mean (detrend)
                rr_interp = rr_interp - np.mean(rr_interp)

                # FFT
                n_fft = len(rr_interp)
                fft_vals = np.fft.rfft(rr_interp)
                psd = (np.abs(fft_vals) ** 2) / n_fft
                freqs = np.fft.rfftfreq(n_fft, d=1.0 / fs_interp)

                # LF band: 0.04-0.15 Hz
                lf_mask = (freqs >= 0.04) & (freqs <= 0.15)
                lf_power = float(np.sum(psd[lf_mask])) if np.any(lf_mask) else 0.0

                # HF band: 0.15-0.4 Hz
                hf_mask = (freqs > 0.15) & (freqs <= 0.4)
                hf_power = float(np.sum(psd[hf_mask])) if np.any(hf_mask) else 0.0

                if hf_power > 1e-10:
                    lf_hf_ratio = round(lf_power / hf_power, 3)

        # --- Stress level ---
        if lf_hf_ratio is not None:
            if lf_hf_ratio < 1.5:
                stress_level = "low"
            elif lf_hf_ratio < 2.5:
                stress_level = "moderate"
            else:
                stress_level = "high"
        else:
            # Fallback: use RMSSD-based stress estimate
            # High RMSSD (>40ms) = relaxed, Low RMSSD (<20ms) = stressed
            if rmssd > 40:
                stress_level = "low"
            elif rmssd > 20:
                stress_level = "moderate"
            else:
                stress_level = "high"

        return {
            "sdnn": round(sdnn, 2),
            "rmssd": round(rmssd, 2),
            "pnn50": round(pnn50, 2),
            "lf_hf_ratio": lf_hf_ratio,
            "stress_level": stress_level,
            "n_samples": len(valid),
            "mean_rr": round(float(np.mean(rr)), 2),
            "mean_hr": round(float(np.mean(valid)), 1),
        }

    # ------------------------------------------------------------------
    # CSI-based pose classification
    # ------------------------------------------------------------------

    def _classify_pose_csi(
        self,
        motion_index: float,
        breathing_rate: float | None,
        doppler_velocity: float | None,
    ) -> tuple[str | None, float]:
        """Classify pose from CSI motion and Doppler features.

        Returns (pose_string, confidence).
        """
        doppler = doppler_velocity if doppler_velocity is not None else 0.0

        # Sudden motion spike -> possible fall
        if motion_index > 8.0:
            return ("fallen", 0.5)

        # Walking: high motion or significant Doppler velocity
        if motion_index > 3.0 or doppler > 0.3:
            return ("walking", 0.7)

        # Standing: moderate motion
        if 0.5 <= motion_index <= 3.0:
            return ("standing", 0.6)

        # Sitting: low motion with normal breathing
        if motion_index < 0.5:
            breathing_normal = (
                breathing_rate is not None and 8.0 <= breathing_rate <= 25.0
            )
            if breathing_normal:
                return ("sitting", 0.8)
            # Low motion but no breathing detected — might still be sitting/standing
            return ("sitting", 0.5)

        return (None, 0.0)

    # ------------------------------------------------------------------
    # Gesture recognition via Dynamic Time Warping (Additional B)
    # ------------------------------------------------------------------

    # Gesture templates: normalized motion_index patterns.
    # Values represent relative motion intensity (0.0 = low, 1.0 = peak).
    # Each template has a name, expected duration, and pattern sequence.
    GESTURE_TEMPLATES: dict[str, list[float]] = {
        # "wave": oscillating high-low pattern ~1.5s (30 samples at 20Hz)
        "wave": [0.1, 0.8, 0.1, 0.8, 0.1],
        # "circle": gradual rise, peak, gradual fall ~2s (40 samples at 20Hz)
        "circle": [0.1, 0.3, 0.6, 1.0, 0.8, 0.5, 0.2],
        # "swipe": sharp rise then sharp fall ~0.5s (10 samples at 20Hz)
        "swipe": [0.1, 0.9, 0.1],
    }
    GESTURE_DTW_THRESHOLD = 0.3  # Max normalized DTW distance for a match

    @staticmethod
    def _dtw_distance(seq_a: np.ndarray, seq_b: np.ndarray) -> float:
        """Compute Dynamic Time Warping distance between two 1-D sequences.

        Returns normalized distance (divided by path length).
        """
        n, m = len(seq_a), len(seq_b)
        if n == 0 or m == 0:
            return float("inf")

        # Cost matrix (n+1 x m+1), init to inf
        dtw = np.full((n + 1, m + 1), np.inf)
        dtw[0, 0] = 0.0

        for i in range(1, n + 1):
            for j in range(1, m + 1):
                cost = abs(seq_a[i - 1] - seq_b[j - 1])
                dtw[i, j] = cost + min(dtw[i - 1, j], dtw[i, j - 1], dtw[i - 1, j - 1])

        # Normalize by path length (n + m)
        return dtw[n, m] / (n + m)

    def _detect_gesture(self, device_id: str, motion_index: float) -> tuple[str | None, float]:
        """Detect gesture from recent motion_index history using DTW.

        Tracks per-device motion_index history (last 60 samples = 3 seconds).
        Compares the tail of the history against each gesture template.

        Returns (gesture_name, confidence) or (None, 0.0) if no match.
        """
        # Update history
        if device_id not in self._gesture_history:
            self._gesture_history[device_id] = deque(maxlen=self._gesture_history_size)
        self._gesture_history[device_id].append(motion_index)

        history = self._gesture_history[device_id]
        if len(history) < 10:
            return (None, 0.0)

        # Normalize the history to [0, 1] range
        hist_arr = np.array(list(history), dtype=np.float64)
        h_min, h_max = hist_arr.min(), hist_arr.max()
        if h_max - h_min < 1e-6:
            return (None, 0.0)  # flat signal — no gesture
        hist_norm = (hist_arr - h_min) / (h_max - h_min)

        best_gesture: str | None = None
        best_distance = float("inf")

        for gesture_name, template in self.GESTURE_TEMPLATES.items():
            template_arr = np.array(template, dtype=np.float64)

            # Compare against the most recent N samples where N scales
            # with the template length (template at 20Hz equivalent).
            # wave: ~30 samples, circle: ~40 samples, swipe: ~10 samples
            # We use len(template) * 6 as approximate window (each template
            # point represents ~6 real samples at 20Hz).
            window_size = min(len(template) * 8, len(hist_norm))
            segment = hist_norm[-window_size:]

            dist = self._dtw_distance(segment, template_arr)
            if dist < best_distance:
                best_distance = dist
                best_gesture = gesture_name

        if best_distance < self.GESTURE_DTW_THRESHOLD and best_gesture is not None:
            # Confidence: inverse of distance, clamped to [0, 1]
            confidence = max(0.0, min(1.0, 1.0 - best_distance / self.GESTURE_DTW_THRESHOLD))
            return (best_gesture, round(confidence, 3))

        return (None, 0.0)

    # ------------------------------------------------------------------
    # Through-wall detection heuristic (Additional E)
    # ------------------------------------------------------------------

    # Through-wall detection thresholds
    THROUGH_WALL_RSSI_THRESHOLD = -80.0       # dBm — weak signal suggests wall
    THROUGH_WALL_ATTENUATION_DB = 10.0        # dB — RSSI difference indicating wall
    THROUGH_WALL_DISTANCE_THRESHOLD = 3.0     # meters — far distance with weak RSSI

    def _estimate_wall_attenuation(
        self,
        rssi: float,
        presence_score: float,
        motion_index: float,
    ) -> bool:
        """Estimate whether detection is through a wall.

        Through-wall detection heuristic (Additional E):
        - Based on RSSI difference between nodes on opposite sides of a wall.
        - If attenuation > 10dB, flag as "through_wall" detection.
        - Simple heuristic: if presence detected but RSSI < -80 and
          the signal characteristics suggest a distant target, mark as through_wall.

        A more accurate implementation would compare RSSI between paired
        nodes on opposite sides of a known wall. This heuristic approximates
        that by detecting the signature of wall-attenuated signals:
        low RSSI + presence detected + low motion (wall dampens motion energy).

        Args:
            rssi: Received signal strength in dBm.
            presence_score: CSI-derived presence score.
            motion_index: CSI-derived motion index.

        Returns:
            True if detection appears to be through a wall.
        """
        # No presence = no through-wall concern
        if presence_score <= 0.1:
            return False

        # Core heuristic: presence detected but RSSI is very weak
        # and motion is dampened (wall attenuates high-frequency motion)
        if rssi < self.THROUGH_WALL_RSSI_THRESHOLD:
            # Estimate effective "distance" from RSSI using free-space path loss
            # FSPL(dB) = 20*log10(d) + 20*log10(f) + 20*log10(4*pi/c)
            # At 5.8 GHz, FSPL at 1m ~ -47.4 dBm (with 0 dBm TX power)
            # So d_est ~ 10^((|RSSI| - 47.4) / 20)
            fspl_1m = 47.4  # dB at 5.8 GHz, 1 meter
            path_loss = abs(rssi) - fspl_1m
            if path_loss > 0:
                estimated_distance = 10.0 ** (path_loss / 20.0)
            else:
                estimated_distance = 1.0

            # Through-wall: weak RSSI + presence + estimated distance > 3m
            if estimated_distance > self.THROUGH_WALL_DISTANCE_THRESHOLD:
                return True

            # Alternative: very weak RSSI with dampened motion (wall absorbs)
            # Normal in-room motion_index > 0.5 for a present person,
            # through-wall typically < 0.3 due to wall attenuation
            if rssi < -85.0 and presence_score > 0.3 and motion_index < 0.3:
                return True

        return False

    # ------------------------------------------------------------------
    # SOTA algorithms ported from ruvnet/RuView Rust crates
    # ------------------------------------------------------------------

    def _apply_csi_ratio(self, csi_array: np.ndarray) -> np.ndarray:
        """CSI Ratio via conjugate multiplication — cancel phase offsets.

        Ported from wifi-densepose-signal/csi_ratio.rs::conjugate_multiply().

        Computes ratio[i] = CSI[i] * conj(CSI[ref]) for each subcarrier,
        where ref is the subcarrier with the lowest amplitude variance
        (most stable). This cancels common-mode phase offsets from WiFi
        hardware (CFO, SFO, packet detection delay), preserving only
        environment-induced phase changes.

        For single-antenna ESP32 data, this acts as inter-subcarrier
        ratio rather than inter-antenna ratio.
        """
        if csi_array.ndim != 1 or len(csi_array) < 2:
            return csi_array

        # Select reference subcarrier: lowest amplitude variance across
        # recent frames would be ideal, but for a single frame we use
        # the subcarrier with amplitude closest to the median (most stable).
        amplitudes = np.abs(csi_array)
        median_amp = np.median(amplitudes)
        ref_idx = int(np.argmin(np.abs(amplitudes - median_amp)))

        # Conjugate multiply: ratio[i] = CSI[i] * conj(CSI[ref])
        ref_conj = np.conj(csi_array[ref_idx])
        ratio = csi_array * ref_conj

        # Normalize by |CSI[ref]|^2 to preserve amplitude scale
        ref_power = np.abs(csi_array[ref_idx]) ** 2
        if ref_power > 1e-15:
            ratio = ratio / ref_power

        return ratio

    def _hampel_filter(self, amplitude: list[float]) -> tuple[list[float], int]:
        """Hampel filter — MAD-based outlier detection and replacement.

        Ported from wifi-densepose-signal/hampel.rs::hampel_filter().

        For each sample, computes the median and MAD (Median Absolute
        Deviation) of the surrounding window. If the sample deviates from
        the median by more than threshold * sigma_est, it is replaced with
        the median. More robust than z-score: resists up to 50% contamination.

        Returns (filtered_amplitude, num_outliers_removed).
        """
        n = len(amplitude)
        if n == 0:
            return amplitude, 0

        signal = np.array(amplitude, dtype=np.float64)
        filtered = signal.copy()
        outlier_count = 0
        half_w = self.HAMPEL_HALF_WINDOW
        threshold = self.HAMPEL_THRESHOLD

        for i in range(n):
            start = max(0, i - half_w)
            end = min(n, i + half_w + 1)
            window = signal[start:end]

            med = float(np.median(window))
            # MAD = median(|x_i - median|)
            mad = float(np.median(np.abs(window - med)))
            # Convert MAD to estimated sigma (for Gaussian: sigma = 1.4826 * MAD)
            sigma = self.MAD_SCALE * mad

            deviation = abs(signal[i] - med)

            if sigma > 1e-15:
                # Normal case: compare deviation to threshold * sigma
                is_outlier = deviation > threshold * sigma
            else:
                # Zero-MAD: all window values identical except possibly this one.
                # Any non-zero deviation is an outlier.
                is_outlier = deviation > 1e-15

            if is_outlier:
                filtered[i] = med
                outlier_count += 1

        return filtered.tolist(), outlier_count

    def _fresnel_breathing_confidence(self, amplitude: list[float]) -> float:
        """Fresnel zone breathing confidence — physics-based validation.

        Ported from wifi-densepose-signal/fresnel.rs::FresnelBreathingEstimator.

        Models the TX-RX Fresnel zone geometry to predict expected amplitude
        variation from chest displacement during breathing. Compares observed
        amplitude variation against the Fresnel model prediction to produce
        a confidence score (0.0-1.0).

        Breathing causes chest displacement of ~3-15mm, producing phase shift
        proportional to 2*pi*2*displacement/wavelength. At 5.8 GHz (lambda=52mm),
        this is a significant fraction of a wavelength.
        """
        if len(amplitude) < 2:
            return 0.0

        # Compute wavelength
        wavelength = self.SPEED_OF_LIGHT / self.DEFAULT_FREQUENCY

        # Expected amplitude variation for min/max breathing displacement
        # Phase change: delta_phi = 2*pi * 2*displacement / wavelength
        # Amplitude variation: |sin(delta_phi / 2)|
        def expected_amp_var(displacement_m: float) -> float:
            delta_phi = 2.0 * math.pi * 2.0 * displacement_m / wavelength
            return abs(math.sin(delta_phi / 2.0))

        min_expected = expected_amp_var(self.FRESNEL_MIN_DISPLACEMENT)
        max_expected = expected_amp_var(self.FRESNEL_MAX_DISPLACEMENT)

        # Ensure low <= high
        low, high = (min_expected, max_expected) if min_expected < max_expected else (max_expected, min_expected)

        # Observed amplitude variation (peak-to-peak, normalized)
        amp_arr = np.array(amplitude, dtype=np.float64)
        # Remove DC and compute peak-to-peak
        amp_centered = amp_arr - np.mean(amp_arr)
        observed = float(np.max(amp_centered) - np.min(amp_centered))

        # Normalize by mean amplitude to get relative variation
        mean_amp = float(np.mean(amp_arr))
        if mean_amp > 1e-15:
            observed = observed / mean_amp

        # Compute confidence based on match with Fresnel prediction
        if low <= observed <= high:
            # Within expected breathing range: high confidence
            confidence = 1.0
        elif observed < low:
            # Below range: linearly scale
            confidence = (observed / low) if low > 1e-15 else 0.0
            confidence = max(0.0, min(1.0, confidence))
        else:
            # Above range: could be larger motion, lower breathing confidence
            confidence = (high / observed) if observed > 1e-15 else 0.0
            confidence = max(0.0, min(1.0, confidence))

        return confidence

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

    def _compute_spectrogram(self, phase_history: np.ndarray) -> tuple[np.ndarray, float | None]:
        """Compute STFT spectrogram of phase history for Doppler extraction.

        Ported concept from wifi-densepose-signal/spectrogram.rs.

        Uses Short-Time Fourier Transform (STFT) on the phase history buffer
        to produce a time-frequency matrix. The dominant frequency in the
        motion band (0.5-5 Hz) is converted to Doppler velocity using the
        WiFi wavelength at 5.8 GHz.

        Args:
            phase_history: 1-D array of unwrapped phase values (up to 256 samples
                           at SAMPLE_RATE Hz).

        Returns:
            (spectrogram, doppler_velocity) where spectrogram is a 2-D array
            of shape (n_freqs, n_time_bins) and doppler_velocity is the estimated
            radial velocity in m/s (None if no dominant motion frequency found).
        """
        n = len(phase_history)
        if n < 32:
            return np.empty((0, 0)), None

        # STFT parameters — 64-sample window (~3.2s at 20 Hz), 75% overlap
        nperseg = min(64, n)
        noverlap = nperseg * 3 // 4

        try:
            freqs, times, zxx = scipy_signal.stft(
                phase_history,
                fs=self.SAMPLE_RATE,
                window="hann",
                nperseg=nperseg,
                noverlap=noverlap,
            )
        except Exception:
            return np.empty((0, 0)), None

        # Magnitude spectrogram (freqs x time_bins)
        spectrogram = np.abs(zxx)

        # Extract dominant Doppler frequency in motion band (0.5-5 Hz)
        # Below 0.5 Hz is breathing/static; above 5 Hz is noise at 20 Hz Nyquist
        motion_lo = 0.5
        motion_hi = min(5.0, self.SAMPLE_RATE / 2.0 - 0.1)
        motion_mask = (freqs >= motion_lo) & (freqs <= motion_hi)

        if not np.any(motion_mask):
            return spectrogram, None

        # Average power across all time bins for each frequency
        avg_power = np.mean(spectrogram[motion_mask, :], axis=1)
        motion_freqs = freqs[motion_mask]

        peak_idx = int(np.argmax(avg_power))
        peak_power = avg_power[peak_idx]
        mean_power = float(np.mean(avg_power))

        # Reject weak peaks (SNR check)
        if mean_power > 0 and peak_power < mean_power * 2.0:
            return spectrogram, None

        dominant_freq = float(motion_freqs[peak_idx])

        # Convert Doppler frequency to velocity:
        #   v = f_doppler * wavelength / 2
        # Factor of 2 accounts for round-trip (TX -> body -> RX reflection)
        wavelength = self.SPEED_OF_LIGHT / self.DEFAULT_FREQUENCY  # ~0.0517 m at 5.8 GHz
        doppler_velocity = dominant_freq * wavelength / 2.0

        return spectrogram, round(doppler_velocity, 4)

    def _compute_bvp(self, phase_history: np.ndarray) -> tuple[list[float] | None, float | None]:
        """Compute Body Velocity Profile (BVP) — ported from Widar 3.0 concept.

        Uses the STFT spectrogram of the phase history to build a velocity-time
        matrix.  For each time window the dominant Doppler frequency is converted
        to a radial velocity using:
            velocity = freq * wavelength / 2
        where wavelength = c / 5.8 GHz ~ 0.0517 m.

        Args:
            phase_history: 1-D array of unwrapped phase values (up to 256
                           samples at SAMPLE_RATE Hz).

        Returns:
            (velocity_profile, max_velocity) where velocity_profile is a list
            of dominant velocities (m/s) at each STFT time step, and
            max_velocity is the peak value across the profile.  Returns
            (None, None) when the input is too short.
        """
        n = len(phase_history)
        if n < 32:
            return None, None

        # Step 1: Compute STFT spectrogram (reuse same windowing as _compute_spectrogram)
        nperseg = min(64, n)
        noverlap = nperseg * 3 // 4

        try:
            freqs, times, zxx = scipy_signal.stft(
                phase_history,
                fs=self.SAMPLE_RATE,
                window="hann",
                nperseg=nperseg,
                noverlap=noverlap,
            )
        except Exception:
            return None, None

        spectrogram = np.abs(zxx)  # shape: (n_freqs, n_time_bins)
        wavelength = self.SPEED_OF_LIGHT / self.DEFAULT_FREQUENCY  # ~0.0517 m

        # Step 2-3: Build velocity-time matrix and detect dominant velocity
        # Map each frequency bin to a velocity: v = f * lambda / 2
        velocities = freqs * wavelength / 2.0  # velocity per frequency bin

        # Only consider positive frequencies in the motion band (> 0.1 Hz)
        motion_mask = freqs > 0.1
        if not np.any(motion_mask):
            return None, None

        motion_spectrogram = spectrogram[motion_mask, :]
        motion_velocities = velocities[motion_mask]

        # Step 4: For each time step, find the dominant velocity
        n_time_bins = motion_spectrogram.shape[1]
        velocity_profile: list[float] = []
        for t_idx in range(n_time_bins):
            col = motion_spectrogram[:, t_idx]
            peak_idx = int(np.argmax(col))
            peak_power = col[peak_idx]
            mean_power = float(np.mean(col))

            if mean_power > 0 and peak_power > mean_power * 1.5:
                # Significant peak — record its velocity
                velocity_profile.append(round(float(motion_velocities[peak_idx]), 4))
            else:
                # No clear dominant motion — velocity ~ 0
                velocity_profile.append(0.0)

        # Step 5: Max velocity across the profile
        max_velocity = round(float(max(velocity_profile)), 4) if velocity_profile else None

        return velocity_profile, max_velocity

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

    SENSITIVITY_RATIO_THRESHOLD = 2.0  # Variance ratio threshold for "sensitive" subcarrier

    def _select_top_k_sensitivity(self, device_id: str, n_sc: int) -> list[int]:
        """Select top-K subcarriers using sensitivity-based filtering.

        Ref: WiDance subcarrier_selection.rs — variance ratio method.

        Instead of raw variance, computes variance ratio:
            ratio = var(subcarrier) / median(all_variances)
        Subcarriers with ratio > 2.0 are "sensitive" — their variance is
        driven by human presence rather than background noise.  Among the
        sensitive set, the top-K by variance are returned.

        Falls back to plain top-K when fewer than TOP_K subcarriers are
        sensitive (early frames / empty room).
        """
        stats = self._subcarrier_var.get(device_id, [])
        count = min(n_sc, len(stats))
        if count < self.TOP_K:
            return list(range(count))

        # Compute per-subcarrier variance
        variances = [(i, stats[i].variance()) for i in range(count)]
        all_vars = [v for _, v in variances]

        # Median of all variances (guard against zero)
        median_var = float(np.median(all_vars)) if all_vars else 0.0

        if median_var > 1e-15:
            # Filter to "sensitive" subcarriers: ratio > threshold
            sensitive = [
                (i, v) for i, v in variances
                if (v / median_var) > self.SENSITIVITY_RATIO_THRESHOLD
            ]
        else:
            # All variances near zero — no meaningful filtering possible
            sensitive = list(variances)

        # If enough sensitive subcarriers, pick top-K among them by variance
        if len(sensitive) >= self.TOP_K:
            sensitive.sort(key=lambda x: x[1], reverse=True)
            return [idx for idx, _ in sensitive[:self.TOP_K]]

        # Fallback: not enough sensitive subcarriers, use plain top-K
        variances.sort(key=lambda x: x[1], reverse=True)
        return [idx for idx, _ in variances[:self.TOP_K]]

    def _get_top_k_variance(self, device_id: str) -> list[float]:
        """Get variance values for top-K subcarriers."""
        indices = self._top_k.get(device_id, [])
        stats = self._subcarrier_var.get(device_id, [])
        return [stats[i].variance() for i in indices if i < len(stats)]

    def _calc_motion_index(self, device_id: str) -> float:
        buf = self._amplitude_buffer.get(device_id)
        if buf is None or len(buf) < 5:
            return 0.0
        recent = list(buf)[-10:]
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

    # ------------------------------------------------------------------
    # Hardware Normalizer (Phase 3-1)
    # ------------------------------------------------------------------

    def normalize_hardware(self, amplitude: np.ndarray, device_id: str) -> np.ndarray:
        """하드웨어 간 CSI 진폭 정규화 (Catmull-Rom 보간 기반).

        다른 ESP32 보드 간 캘리브레이션 편차를 보정한다.

        알고리즘:
          1. 첫 HW_NORM_WARMUP_FRAMES 프레임의 평균으로 device별 기준 진폭 벡터 설정.
          2. 기준 설정 후 입력 amplitude에서 기준 오프셋을 차감해 편차를 제거.
          3. CubicSpline(not-a-knot) 보간으로 빈/잡음 서브캐리어를 평활화.
          4. 전체 진폭을 [0, 1] 범위로 Min-Max 정규화.

        Args:
            amplitude: 서브캐리어 진폭 벡터 (float64 ndarray), shape (n_sc,).
            device_id:  ESP32 보드 식별자.

        Returns:
            정규화된 진폭 ndarray, shape (n_sc,). 입력이 비어 있으면 그대로 반환.
        """
        n = len(amplitude)
        if n == 0:
            return amplitude

        # 디바이스 상태 초기화
        if device_id not in self._hw_offsets:
            self._hw_offsets[device_id] = {
                "sum": np.zeros(n, dtype=np.float64),
                "count": 0,
                "baseline": None,
            }

        state = self._hw_offsets[device_id]

        # 벡터 크기가 바뀐 경우 리셋 (채널 수 변경 대응)
        if state["sum"].shape[0] != n:
            state["sum"] = np.zeros(n, dtype=np.float64)
            state["count"] = 0
            state["baseline"] = None

        # --- Step 1: 웜업 — 첫 100프레임 평균으로 기준 설정 ---
        if state["count"] < self.HW_NORM_WARMUP_FRAMES:
            state["sum"] += amplitude
            state["count"] += 1
            if state["count"] == self.HW_NORM_WARMUP_FRAMES:
                state["baseline"] = state["sum"] / self.HW_NORM_WARMUP_FRAMES
            # 웜업 중에는 원본 그대로 (정규화만 적용)
            result = amplitude.copy()
        else:
            # --- Step 2: 기준 오프셋 차감 ---
            baseline = state["baseline"]
            result = amplitude - baseline  # type: ignore[operator]

        # --- Step 3: Catmull-Rom(not-a-knot CubicSpline) 보간으로 평활화 ---
        # 제로 또는 NaN 서브캐리어를 스킵하고 유효 인덱스만으로 스플라인 피팅
        x_all = np.arange(n, dtype=np.float64)
        valid_mask = np.isfinite(result) & (np.abs(result) > 1e-15)
        n_valid = int(np.sum(valid_mask))

        if n_valid >= 4:  # CubicSpline은 최소 2점 필요하나 4점부터 의미 있음
            x_valid = x_all[valid_mask]
            y_valid = result[valid_mask]
            try:
                cs = CubicSpline(x_valid, y_valid, bc_type="not-a-knot")
                result = cs(x_all)
            except Exception:
                pass  # 보간 실패 시 원본 유지

        # --- Step 4: [0, 1] Min-Max 정규화 ---
        r_min = float(np.min(result))
        r_max = float(np.max(result))
        span = r_max - r_min
        if span > 1e-15:
            result = (result - r_min) / span
        else:
            # 모든 값이 동일 → 중간값 0.5로 설정
            result = np.full(n, 0.5, dtype=np.float64)

        return result
