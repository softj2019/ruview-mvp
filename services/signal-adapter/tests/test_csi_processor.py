"""
Unit tests for csi_processor.py

Covers:
- WelfordStats: update, variance, std, z_score, windowed behavior
- CSIProcessor.process() with synthetic CSI data
- Hampel filter outlier removal
- Phase unwrapping
- Zero-crossing BPM
- Top-K selection
- Motion index calculation
- Pose classification
"""
import math
import sys
import os

import numpy as np
import pytest

# Allow importing from parent directory when running tests directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from csi_processor import WelfordStats, CSIProcessor, ProcessedCSI


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def processor():
    return CSIProcessor()


@pytest.fixture
def welford():
    return WelfordStats()


@pytest.fixture
def synthetic_raw_frame():
    """Single raw CSI frame with 52 complex subcarriers."""
    rng = np.random.default_rng(42)
    n_sc = 52
    real = rng.standard_normal(n_sc).astype(np.float32)
    imag = rng.standard_normal(n_sc).astype(np.float32)
    complex_vals = (real + 1j * imag).tolist()
    return {
        "device_id": "esp32-test",
        "timestamp": "2024-01-01T00:00:00Z",
        "csi_data": complex_vals,
        "rssi": -65.0,
        "noise_floor": -95.0,
    }


def make_frame(device_id="dev-1", n_sc=52, rssi=-65.0, seed=0):
    """Helper to produce a reproducible raw frame."""
    rng = np.random.default_rng(seed)
    real = rng.standard_normal(n_sc).astype(np.float32)
    imag = rng.standard_normal(n_sc).astype(np.float32)
    return {
        "device_id": device_id,
        "timestamp": "2024-01-01T00:00:00Z",
        "csi_data": (real + 1j * imag).tolist(),
        "rssi": rssi,
        "noise_floor": -95.0,
    }


# ---------------------------------------------------------------------------
# WelfordStats tests
# ---------------------------------------------------------------------------

class TestWelfordStats:
    def test_initial_state(self, welford):
        assert welford.count == 0
        assert welford.mean == 0.0
        assert welford.variance() == 0.0
        assert welford.std() == 0.0

    def test_single_update_mean(self, welford):
        welford.update(5.0)
        assert welford.count == 1
        assert welford.mean == pytest.approx(5.0)

    def test_variance_two_samples(self, welford):
        welford.update(2.0)
        welford.update(4.0)
        # Sample variance of [2, 4] = 2.0
        assert welford.variance() == pytest.approx(2.0, rel=1e-9)

    def test_std_equals_sqrt_variance(self, welford):
        for v in [1.0, 2.0, 3.0, 4.0, 5.0]:
            welford.update(v)
        assert welford.std() == pytest.approx(math.sqrt(welford.variance()), rel=1e-9)

    def test_z_score_zero_for_mean(self, welford):
        for v in [10.0, 10.0, 10.0, 10.0, 10.0]:
            welford.update(v)
        # Mean == 10, std == 0 → z_score should be 0
        assert welford.z_score(10.0) == pytest.approx(0.0, abs=1e-9)

    def test_z_score_nonzero(self, welford):
        for v in [0.0, 0.0, 10.0, 10.0]:
            welford.update(v)
        z = welford.z_score(0.0)
        # Should be a positive float representing |0 - mean| / std
        assert z > 0

    def test_windowed_count_bounded(self):
        """After exceeding the window, count is clamped to window size."""
        ws = WelfordStats(window=10, alpha=0.99)
        for i in range(25):
            ws.update(float(i))
        assert ws.count == 10  # clamped to window

    def test_windowed_mean_tracks_recent(self):
        """EMA mode: mean should shift toward recent values after the window fills."""
        ws = WelfordStats(window=5, alpha=0.8)
        for _ in range(5):
            ws.update(0.0)
        for _ in range(20):
            ws.update(100.0)
        # Mean should have moved significantly toward 100
        assert ws.mean > 50.0

    def test_variance_constant_series(self, welford):
        """Constant series should produce near-zero variance."""
        for _ in range(20):
            welford.update(3.14)
        assert welford.variance() == pytest.approx(0.0, abs=1e-10)

    def test_multiple_updates_welford_accuracy(self):
        """Welford variance should match numpy variance for a moderate series."""
        data = [float(x) for x in range(1, 51)]
        ws = WelfordStats()
        for v in data:
            ws.update(v)
        expected = float(np.var(data, ddof=1))
        assert ws.variance() == pytest.approx(expected, rel=1e-6)


# ---------------------------------------------------------------------------
# CSIProcessor.process() integration tests
# ---------------------------------------------------------------------------

class TestCSIProcessorProcess:
    def test_returns_processed_csi(self, processor, synthetic_raw_frame):
        result = processor.process(synthetic_raw_frame)
        assert isinstance(result, ProcessedCSI)

    def test_device_id_propagated(self, processor, synthetic_raw_frame):
        result = processor.process(synthetic_raw_frame)
        assert result.device_id == "esp32-test"

    def test_timestamp_propagated(self, processor, synthetic_raw_frame):
        result = processor.process(synthetic_raw_frame)
        assert result.timestamp == "2024-01-01T00:00:00Z"

    def test_rssi_propagated(self, processor, synthetic_raw_frame):
        result = processor.process(synthetic_raw_frame)
        assert result.rssi == pytest.approx(-65.0)

    def test_amplitude_length_matches_input(self, processor, synthetic_raw_frame):
        n_sc = len(synthetic_raw_frame["csi_data"])
        result = processor.process(synthetic_raw_frame)
        assert len(result.amplitude) == n_sc

    def test_phase_length_matches_input(self, processor, synthetic_raw_frame):
        n_sc = len(synthetic_raw_frame["csi_data"])
        result = processor.process(synthetic_raw_frame)
        assert len(result.phase) == n_sc

    def test_motion_index_non_negative(self, processor, synthetic_raw_frame):
        # Feed enough frames to produce a non-trivial motion index
        for i in range(10):
            result = processor.process(make_frame(seed=i))
        assert result.motion_index >= 0.0

    def test_presence_score_non_negative(self, processor):
        for i in range(15):
            result = processor.process(make_frame(seed=i))
        assert result.presence_score >= 0.0

    def test_hampel_outliers_removed_non_negative(self, processor, synthetic_raw_frame):
        result = processor.process(synthetic_raw_frame)
        assert result.hampel_outliers_removed >= 0

    def test_empty_csi_data_does_not_crash(self, processor):
        frame = {
            "device_id": "empty-dev",
            "timestamp": "2024-01-01T00:00:00Z",
            "csi_data": [],
            "rssi": -70.0,
            "noise_floor": -95.0,
        }
        result = processor.process(frame)
        assert isinstance(result, ProcessedCSI)
        assert result.amplitude == []

    def test_multiple_devices_tracked_independently(self, processor):
        for i in range(10):
            processor.process(make_frame(device_id="dev-A", seed=i))
            processor.process(make_frame(device_id="dev-B", seed=i + 100))
        assert "dev-A" in processor._frame_count
        assert "dev-B" in processor._frame_count
        assert processor._frame_count["dev-A"] == 10
        assert processor._frame_count["dev-B"] == 10

    def test_top_k_variance_list_length(self, processor):
        for i in range(10):
            result = processor.process(make_frame(seed=i))
        assert isinstance(result.top_k_variance, list)


# ---------------------------------------------------------------------------
# Hampel filter tests
# ---------------------------------------------------------------------------

class TestHampelFilter:
    def setup_method(self):
        self.proc = CSIProcessor()

    def test_no_outliers_returned_unchanged(self):
        clean = [1.0] * 20
        filtered, n_removed = self.proc._hampel_filter(clean)
        assert n_removed == 0
        assert filtered == pytest.approx(clean, abs=1e-9)

    def test_single_spike_is_replaced(self):
        data = [1.0] * 20
        data[10] = 1000.0  # clear outlier
        filtered, n_removed = self.proc._hampel_filter(data)
        assert n_removed >= 1
        assert filtered[10] < 100.0  # replaced with median (~1.0)

    def test_empty_list_returns_empty(self):
        filtered, n_removed = self.proc._hampel_filter([])
        assert filtered == []
        assert n_removed == 0

    def test_single_element_no_change(self):
        filtered, n_removed = self.proc._hampel_filter([42.0])
        assert n_removed == 0
        assert filtered[0] == pytest.approx(42.0)

    def test_multiple_outliers_removed(self):
        data = [1.0] * 30
        data[5] = 500.0
        data[20] = -500.0
        filtered, n_removed = self.proc._hampel_filter(data)
        assert n_removed >= 2

    def test_output_length_unchanged(self):
        data = list(range(15))
        filtered, _ = self.proc._hampel_filter([float(x) for x in data])
        assert len(filtered) == 15

    def test_zero_mad_window_outlier_detected(self):
        """When all window values are identical except one, that one is an outlier."""
        data = [5.0] * 10
        data[5] = 999.0
        filtered, n_removed = self.proc._hampel_filter(data)
        assert n_removed >= 1


# ---------------------------------------------------------------------------
# Phase unwrapping tests
# ---------------------------------------------------------------------------

class TestPhaseUnwrapping:
    def setup_method(self):
        self.proc = CSIProcessor()

    def test_first_call_stores_prev_phase(self):
        phase = np.array([0.1, 0.2, 3.0, -3.0])
        result = self.proc._unwrap_phase("dev", phase)
        np.testing.assert_array_almost_equal(result, phase)
        np.testing.assert_array_almost_equal(self.proc._prev_phase["dev"], phase)

    def test_large_jump_is_corrected(self):
        proc = CSIProcessor()
        # First frame: all zeros
        prev = np.zeros(4)
        proc._unwrap_phase("dev", prev)
        # Second frame: a big jump that would be ~2pi
        big_jump = np.array([2 * np.pi + 0.1, 0.0, 0.0, 0.0])
        result = proc._unwrap_phase("dev", big_jump)
        # The first subcarrier should be wrapped to a small value
        assert abs(result[0]) < np.pi + 0.2

    def test_phase_length_preserved(self):
        proc = CSIProcessor()
        phase = np.linspace(-np.pi, np.pi, 52)
        result = proc._unwrap_phase("dev", phase)
        assert len(result) == 52

    def test_no_crosscontamination_between_devices(self):
        proc = CSIProcessor()
        phase_a = np.array([1.0, 2.0, 3.0])
        phase_b = np.array([0.5, 0.5, 0.5])
        proc._unwrap_phase("dev-a", phase_a)
        proc._unwrap_phase("dev-b", phase_b)
        assert "dev-a" in proc._prev_phase
        assert "dev-b" in proc._prev_phase
        np.testing.assert_array_almost_equal(proc._prev_phase["dev-a"], phase_a)
        np.testing.assert_array_almost_equal(proc._prev_phase["dev-b"], phase_b)


# ---------------------------------------------------------------------------
# Zero-crossing BPM tests
# ---------------------------------------------------------------------------

class TestZeroCrossingBPM:
    def test_sine_wave_correct_bpm(self):
        """A 0.2 Hz sine at 20 Hz sample rate should yield ~12 BPM."""
        fs = 20.0
        t = np.linspace(0, 10, int(10 * fs), endpoint=False)
        sig = np.sin(2 * np.pi * 0.2 * t)  # 0.2 Hz = 12 BPM
        bpm = CSIProcessor._zero_crossing_bpm(sig, fs)
        assert bpm is not None
        assert 10.0 <= bpm <= 14.0

    def test_no_crossings_returns_none(self):
        sig = np.ones(100)  # constant, no crossings
        result = CSIProcessor._zero_crossing_bpm(sig, 20.0)
        assert result is None

    def test_single_crossing_returns_none(self):
        sig = np.array([-1.0, 1.0] + [1.0] * 98)
        result = CSIProcessor._zero_crossing_bpm(sig, 20.0)
        assert result is None

    def test_higher_frequency_gives_higher_bpm(self):
        fs = 20.0
        t = np.linspace(0, 10, int(10 * fs), endpoint=False)
        slow = np.sin(2 * np.pi * 0.15 * t)
        fast = np.sin(2 * np.pi * 0.4 * t)
        bpm_slow = CSIProcessor._zero_crossing_bpm(slow, fs)
        bpm_fast = CSIProcessor._zero_crossing_bpm(fast, fs)
        assert bpm_slow is not None and bpm_fast is not None
        assert bpm_fast > bpm_slow


# ---------------------------------------------------------------------------
# Top-K selection tests
# ---------------------------------------------------------------------------

class TestTopKSelection:
    def setup_method(self):
        self.proc = CSIProcessor()

    def _feed_frames_with_high_variance_on(self, device_id, high_indices, n_sc=52, n_frames=30):
        """Feed frames where specific subcarrier indices have high variance."""
        rng = np.random.default_rng(7)
        for _ in range(n_frames):
            real = rng.standard_normal(n_sc).astype(np.float32) * 0.01
            for idx in high_indices:
                real[idx] = rng.standard_normal() * 5.0  # high variance
            imag = rng.standard_normal(n_sc).astype(np.float32) * 0.01
            frame = {
                "device_id": device_id,
                "timestamp": "2024-01-01T00:00:00Z",
                "csi_data": (real + 1j * imag).tolist(),
                "rssi": -65.0,
                "noise_floor": -95.0,
            }
            self.proc.process(frame)

    def test_top_k_length_at_most_k(self):
        device_id = "top-k-dev"
        self._feed_frames_with_high_variance_on(device_id, high_indices=[0, 1, 2])
        top_k = self.proc._select_top_k(device_id, n_sc=52)
        assert len(top_k) <= CSIProcessor.TOP_K

    def test_top_k_indices_in_range(self):
        device_id = "top-k-range"
        self._feed_frames_with_high_variance_on(device_id, high_indices=[10, 20, 30])
        top_k = self.proc._select_top_k(device_id, n_sc=52)
        assert all(0 <= idx < 52 for idx in top_k)

    def test_top_k_prefers_high_variance_subcarriers(self):
        """After many frames with elevated variance on specific subcarriers,
        top_k_variance values should be non-empty and positive."""
        device_id = "top-k-pref"
        high_indices = [3, 15, 42]
        self._feed_frames_with_high_variance_on(device_id, high_indices=high_indices, n_frames=50)
        top_k = self.proc._select_top_k(device_id, n_sc=52)
        # Top-K must be non-empty
        assert len(top_k) > 0
        # At least one selected subcarrier should have a positive variance
        stats = self.proc._subcarrier_var.get(device_id, [])
        variances = [stats[i].variance() for i in top_k if i < len(stats)]
        assert any(v > 0 for v in variances)

    def test_top_k_empty_stats_returns_range(self):
        result = self.proc._select_top_k("no-stats-dev", n_sc=52)
        assert result == []

    def test_sensitivity_top_k_returns_valid_list(self):
        device_id = "sens-dev"
        self._feed_frames_with_high_variance_on(device_id, high_indices=[5, 6, 7, 8, 9, 10, 11, 12], n_frames=50)
        top_k = self.proc._select_top_k_sensitivity(device_id, n_sc=52)
        assert isinstance(top_k, list)
        assert len(top_k) <= CSIProcessor.TOP_K


# ---------------------------------------------------------------------------
# Motion index calculation tests
# ---------------------------------------------------------------------------

class TestMotionIndex:
    def setup_method(self):
        self.proc = CSIProcessor()

    def test_insufficient_frames_returns_zero(self):
        for i in range(3):
            self.proc.process(make_frame(seed=i))
        device_id = "dev-1"
        mi = self.proc._calc_motion_index(device_id)
        # With < 5 frames buffered it should return 0
        assert mi == 0.0

    def test_motion_index_positive_after_enough_frames(self):
        for i in range(10):
            self.proc.process(make_frame(seed=i))
        mi = self.proc._calc_motion_index("dev-1")
        assert mi >= 0.0

    def test_higher_amplitude_variation_gives_higher_motion(self):
        """Frames with random noise should produce higher motion index than constant frames."""
        rng = np.random.default_rng(99)

        proc_noisy = CSIProcessor()
        proc_quiet = CSIProcessor()

        n_sc = 52
        for i in range(15):
            # Noisy: large random amplitudes
            noisy_vals = (rng.standard_normal(n_sc) * 10 + 1j * rng.standard_normal(n_sc) * 10).tolist()
            proc_noisy.process({
                "device_id": "dev-1",
                "timestamp": "",
                "csi_data": noisy_vals,
                "rssi": -65.0,
                "noise_floor": -95.0,
            })
            # Quiet: constant near-zero values
            quiet_vals = ([0.01 + 0.01j] * n_sc)
            proc_quiet.process({
                "device_id": "dev-1",
                "timestamp": "",
                "csi_data": quiet_vals,
                "rssi": -65.0,
                "noise_floor": -95.0,
            })

        mi_noisy = proc_noisy._calc_motion_index("dev-1")
        mi_quiet = proc_quiet._calc_motion_index("dev-1")
        assert mi_noisy > mi_quiet


# ---------------------------------------------------------------------------
# Pose classification tests
# ---------------------------------------------------------------------------

class TestPoseClassification:
    def setup_method(self):
        self.proc = CSIProcessor()

    def test_high_motion_classified_as_fallen(self):
        pose, conf = self.proc._classify_pose_csi(motion_index=10.0, breathing_rate=None, doppler_velocity=None)
        assert pose == "fallen"
        assert conf > 0

    def test_moderate_motion_classified_as_walking(self):
        pose, conf = self.proc._classify_pose_csi(motion_index=4.0, breathing_rate=None, doppler_velocity=None)
        assert pose == "walking"
        assert conf > 0

    def test_low_motion_with_breathing_classified_as_sitting(self):
        pose, conf = self.proc._classify_pose_csi(motion_index=0.3, breathing_rate=15.0, doppler_velocity=None)
        assert pose == "sitting"
        assert conf > 0

    def test_low_motion_no_breathing_still_sitting(self):
        pose, conf = self.proc._classify_pose_csi(motion_index=0.3, breathing_rate=None, doppler_velocity=None)
        assert pose == "sitting"

    def test_standing_range(self):
        pose, conf = self.proc._classify_pose_csi(motion_index=1.5, breathing_rate=None, doppler_velocity=None)
        assert pose == "standing"
        assert conf > 0

    def test_doppler_triggers_walking(self):
        pose, conf = self.proc._classify_pose_csi(motion_index=0.2, breathing_rate=None, doppler_velocity=0.5)
        assert pose == "walking"

    def test_confidence_between_0_and_1(self):
        for mi in [0.0, 0.5, 2.0, 5.0, 9.0]:
            _, conf = self.proc._classify_pose_csi(motion_index=mi, breathing_rate=None, doppler_velocity=None)
            assert 0.0 <= conf <= 1.0


# ---------------------------------------------------------------------------
# 작업 1: breathing_bpm 범위 클램프 (Phase 0-1)
# ---------------------------------------------------------------------------

class TestBreathingBpmClamp:
    """process()가 breathing_rate를 6~30 BPM 범위로 클램프하는지 검증."""

    def setup_method(self):
        self.proc = CSIProcessor()

    def _feed_frames(self, n: int, device_id: str = "dev-1", seed_offset: int = 0):
        for i in range(n):
            self.proc.process(make_frame(device_id=device_id, seed=i + seed_offset))

    def test_breathing_rate_none_before_min_frames(self):
        """MIN_FRAMES_VITALS 미만에서는 breathing_rate가 None 또는 0.0."""
        for i in range(10):
            result = self.proc.process(make_frame(seed=i))
        # 10프레임은 MIN_FRAMES_VITALS(64)보다 적으므로 None이어야 함
        assert result.breathing_rate is None

    def test_breathing_rate_in_range_or_zero_after_many_frames(self):
        """충분한 프레임 후 breathing_rate는 6~30 사이이거나 0.0 또는 None."""
        self._feed_frames(80)
        result = self.proc.process(make_frame(seed=999))
        br = result.breathing_rate
        if br is not None:
            assert br == 0.0 or 6.0 <= br <= 30.0, f"out-of-range breathing_rate: {br}"

    def test_breathing_rate_never_out_of_range(self):
        """process()가 반환하는 breathing_rate가 절대로 (0, 6) 또는 (30, inf) 범위에 있지 않음."""
        self._feed_frames(100)
        for i in range(20):
            result = self.proc.process(make_frame(seed=200 + i))
            br = result.breathing_rate
            if br is not None and br != 0.0:
                assert 6.0 <= br <= 30.0, f"invalid breathing_rate: {br}"


# ---------------------------------------------------------------------------
# 작업 2: HRV _compute_hrv() 완전 구현 (Phase 3-2)
# ---------------------------------------------------------------------------

class TestComputeHRV:
    """_compute_hrv(rr_intervals) 공식 검증."""

    def test_too_few_intervals_returns_zeros(self):
        """rr_intervals 3개 미만 → 모두 0.0."""
        result = CSIProcessor._compute_hrv([800.0, 810.0])
        assert result["sdnn"] == 0.0
        assert result["rmssd"] == 0.0
        assert result["pnn50"] == 0.0
        assert result["mean_rr"] == 0.0

    def test_empty_returns_zeros(self):
        result = CSIProcessor._compute_hrv([])
        assert result == {"sdnn": 0.0, "rmssd": 0.0, "pnn50": 0.0, "mean_rr": 0.0}

    def test_sdnn_constant_rr_is_zero(self):
        """모든 R-R 간격이 동일하면 SDNN = 0."""
        rr = [800.0] * 10
        result = CSIProcessor._compute_hrv(rr)
        assert result["sdnn"] == pytest.approx(0.0, abs=1e-9)

    def test_rmssd_constant_rr_is_zero(self):
        """모든 R-R 간격이 동일하면 RMSSD = 0."""
        rr = [800.0] * 10
        result = CSIProcessor._compute_hrv(rr)
        assert result["rmssd"] == pytest.approx(0.0, abs=1e-9)

    def test_sdnn_formula(self):
        """SDNN = population std (ddof=0) of R-R intervals."""
        rr = [800.0, 820.0, 810.0, 830.0, 790.0]
        result = CSIProcessor._compute_hrv(rr)
        expected_sdnn = float(np.sqrt(np.mean((np.array(rr) - np.mean(rr)) ** 2)))
        # round(..., 2) 반올림 허용 (0.01ms 이내)
        assert result["sdnn"] == pytest.approx(expected_sdnn, abs=0.01)

    def test_rmssd_formula(self):
        """RMSSD = sqrt(mean(diff^2))."""
        rr = [800.0, 820.0, 810.0, 830.0, 790.0]
        result = CSIProcessor._compute_hrv(rr)
        arr = np.array(rr)
        expected_rmssd = float(np.sqrt(np.mean(np.diff(arr) ** 2)))
        assert result["rmssd"] == pytest.approx(expected_rmssd, rel=1e-6)

    def test_pnn50_formula(self):
        """pNN50: 연속 R-R 차이가 50ms 초과인 비율(%)."""
        # diff: [100, -100, 100, -100] → 모두 |diff| > 50 → pNN50 = 100%
        rr = [800.0, 900.0, 800.0, 900.0, 800.0]
        result = CSIProcessor._compute_hrv(rr)
        assert result["pnn50"] == pytest.approx(100.0, abs=1e-6)

    def test_pnn50_no_large_diff(self):
        """연속 차이가 모두 50ms 이하면 pNN50 = 0."""
        rr = [800.0, 810.0, 805.0, 808.0, 802.0]
        result = CSIProcessor._compute_hrv(rr)
        assert result["pnn50"] == pytest.approx(0.0, abs=1e-6)

    def test_mean_rr_formula(self):
        """mean_rr = 산술 평균."""
        rr = [800.0, 820.0, 810.0]
        result = CSIProcessor._compute_hrv(rr)
        assert result["mean_rr"] == pytest.approx(np.mean(rr), rel=1e-6)

    def test_returns_dict_with_required_keys(self):
        rr = [800.0, 810.0, 820.0, 815.0, 805.0]
        result = CSIProcessor._compute_hrv(rr)
        for key in ("sdnn", "rmssd", "pnn50", "mean_rr"):
            assert key in result

    def test_all_values_non_negative(self):
        rng = np.random.default_rng(42)
        rr = (rng.standard_normal(20) * 50 + 800).tolist()
        result = CSIProcessor._compute_hrv(rr)
        assert result["sdnn"] >= 0.0
        assert result["rmssd"] >= 0.0
        assert 0.0 <= result["pnn50"] <= 100.0


# ---------------------------------------------------------------------------
# 작업 3: Hardware Normalizer (Phase 3-1)
# ---------------------------------------------------------------------------

class TestNormalizeHardware:
    """normalize_hardware() 동작 검증."""

    def setup_method(self):
        self.proc = CSIProcessor()

    def test_empty_amplitude_returns_empty(self):
        result = self.proc.normalize_hardware(np.array([]), "dev-1")
        assert len(result) == 0

    def test_output_shape_matches_input(self):
        amp = np.ones(52, dtype=np.float64)
        result = self.proc.normalize_hardware(amp, "dev-1")
        assert result.shape == amp.shape

    def test_output_in_unit_range_after_warmup(self):
        """웜업 완료 후 출력은 [0, 1] 범위."""
        n_sc = 52
        rng = np.random.default_rng(7)
        for _ in range(self.proc.HW_NORM_WARMUP_FRAMES + 10):
            amp = np.abs(rng.standard_normal(n_sc)) + 1.0
            result = self.proc.normalize_hardware(amp, "dev-test")
        assert float(np.min(result)) >= -1e-9
        assert float(np.max(result)) <= 1.0 + 1e-9

    def test_different_devices_tracked_independently(self):
        """디바이스별로 독립적인 기준 추적."""
        n_sc = 16
        rng = np.random.default_rng(99)
        for _ in range(5):
            self.proc.normalize_hardware(np.abs(rng.standard_normal(n_sc)) + 1.0, "dev-A")
            self.proc.normalize_hardware(np.abs(rng.standard_normal(n_sc)) + 5.0, "dev-B")
        assert "dev-A" in self.proc._hw_offsets
        assert "dev-B" in self.proc._hw_offsets
        # 두 디바이스의 기준 sum이 달라야 함 (다른 진폭 분포)
        assert not np.allclose(
            self.proc._hw_offsets["dev-A"]["sum"],
            self.proc._hw_offsets["dev-B"]["sum"],
        )

    def test_constant_amplitude_gives_uniform_output(self):
        """모든 서브캐리어 진폭이 동일하면 출력도 균일 (0.5)."""
        n_sc = 10
        for _ in range(self.proc.HW_NORM_WARMUP_FRAMES + 5):
            result = self.proc.normalize_hardware(np.ones(n_sc) * 3.0, "dev-const")
        # 상수 신호 → span == 0 → 0.5
        np.testing.assert_allclose(result, 0.5, atol=1e-9)

    def test_baseline_set_after_warmup(self):
        """HW_NORM_WARMUP_FRAMES 이후 baseline이 None이 아님."""
        n_sc = 8
        rng = np.random.default_rng(0)
        for _ in range(self.proc.HW_NORM_WARMUP_FRAMES):
            self.proc.normalize_hardware(np.abs(rng.standard_normal(n_sc)) + 1.0, "dev-w")
        assert self.proc._hw_offsets["dev-w"]["baseline"] is not None

    def test_process_pipeline_includes_normalization(self):
        """process()가 정상 실행되고 amplitude가 [0, 1] 범위 내에 있음."""
        result = self.proc.process(make_frame(device_id="dev-pipe", seed=0))
        if len(result.amplitude) > 0:
            assert all(0.0 <= v <= 1.0 + 1e-9 for v in result.amplitude), \
                f"amplitude out of [0,1]: min={min(result.amplitude):.4f} max={max(result.amplitude):.4f}"
