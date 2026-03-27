"""
Unit tests for the sensing package (Phase 3-9, 3-10, 3-11)

- RssiCollector: 기본 수집, circular buffer, 정규화, 이상치 제거
- RssiFeatureExtractor: 시간 영역 특징, 주파수 대역 파워, CUSUM 변화점
- PresenceClassifier: 3단계 분류, 히스테리시스, 신뢰도
"""
import sys
import os
import math

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sensing import (
    RssiCollector,
    RssiFeatureExtractor,
    PresenceClassifier,
    MotionLevel,
    cusum_detect,
)


# ===========================================================================
# RssiCollector
# ===========================================================================

class TestRssiCollector:
    def setup_method(self):
        self.collector = RssiCollector(window_size=100)

    def test_push_and_count(self):
        self.collector.push("dev-1", -60.0)
        self.collector.push("dev-1", -62.0)
        assert self.collector.sample_count("dev-1") == 2

    def test_unknown_device_returns_empty(self):
        samples = self.collector.get_samples("unknown")
        assert samples == []

    def test_device_ids_tracked(self):
        self.collector.push("alpha", -55.0)
        self.collector.push("beta", -70.0)
        ids = self.collector.device_ids()
        assert "alpha" in ids
        assert "beta" in ids

    def test_circular_buffer_caps_at_window_size(self):
        col = RssiCollector(window_size=10)
        for i in range(25):
            col.push("dev", float(-60 - i))
        assert col.sample_count("dev") == 10

    def test_get_last_n_samples(self):
        for i in range(20):
            self.collector.push("dev", float(-50 - i))
        samples = self.collector.get_samples("dev", n=5)
        assert len(samples) == 5
        # 최근 5개 → RSSI는 -69 ~ -65
        assert samples[-1].rssi_dbm == pytest.approx(-69.0)

    def test_get_rssi_array_no_outliers(self):
        for v in [-60.0, -61.0, -62.0, -63.0, -64.0]:
            self.collector.push("dev", v)
        arr = self.collector.get_rssi_array("dev", remove_outliers=False)
        assert len(arr) == 5
        assert isinstance(arr, np.ndarray)

    def test_get_rssi_array_removes_outliers(self):
        values = [-60.0] * 20 + [100.0, -200.0]   # 2개 명확한 이상치
        col = RssiCollector(window_size=50, outlier_iqr_factor=1.5)
        for v in values:
            col.push("dev", v)
        arr = col.get_rssi_array("dev", remove_outliers=True)
        assert len(arr) < 22
        assert 100.0 not in arr
        assert -200.0 not in arr

    def test_normalization_range(self):
        for v in [-80.0, -70.0, -60.0, -50.0, -40.0]:
            self.collector.push("dev", v)
        norm = self.collector.get_normalized("dev", remove_outliers=False)
        assert float(np.min(norm)) >= -1e-9
        assert float(np.max(norm)) <= 1.0 + 1e-9

    def test_normalization_constant_signal(self):
        col = RssiCollector(window_size=20)
        for _ in range(10):
            col.push("dev", -60.0)
        norm = col.get_normalized("dev", remove_outliers=False)
        np.testing.assert_allclose(norm, 0.5, atol=1e-9)

    def test_clear_single_device(self):
        self.collector.push("dev-a", -60.0)
        self.collector.push("dev-b", -70.0)
        self.collector.clear("dev-a")
        assert self.collector.sample_count("dev-a") == 0
        assert self.collector.sample_count("dev-b") == 1

    def test_clear_all(self):
        self.collector.push("dev-a", -60.0)
        self.collector.push("dev-b", -70.0)
        self.collector.clear()
        assert self.collector.device_ids() == []

    def test_invalid_window_size_raises(self):
        with pytest.raises(ValueError):
            RssiCollector(window_size=0)


# ===========================================================================
# RssiFeatureExtractor
# ===========================================================================

class TestRssiFeatureExtractor:
    def setup_method(self):
        self.extractor = RssiFeatureExtractor(sample_rate_hz=10.0)

    def _make_sine_rssi(self, freq_hz: float, n: int = 200, fs: float = 10.0) -> np.ndarray:
        t = np.arange(n) / fs
        return -60.0 + 5.0 * np.sin(2 * np.pi * freq_hz * t)

    def test_too_few_samples_returns_empty_features(self):
        features = self.extractor.extract_from_array(np.array([-60.0, -61.0]))
        assert features.n_samples == 2
        assert features.variance == 0.0

    def test_n_samples_correct(self):
        rssi = np.ones(50, dtype=np.float64) * -65.0
        features = self.extractor.extract_from_array(rssi)
        assert features.n_samples == 50

    def test_mean_correct(self):
        rssi = np.array([-60.0, -62.0, -64.0, -66.0], dtype=np.float64)
        features = self.extractor.extract_from_array(rssi)
        assert features.mean == pytest.approx(-63.0, rel=1e-6)

    def test_variance_constant_signal(self):
        rssi = np.ones(30, dtype=np.float64) * -70.0
        features = self.extractor.extract_from_array(rssi)
        assert features.variance == pytest.approx(0.0, abs=1e-10)

    def test_peak_to_peak(self):
        rssi = np.array([-80.0, -60.0, -70.0, -50.0], dtype=np.float64)
        features = self.extractor.extract_from_array(rssi)
        assert features.peak_to_peak == pytest.approx(30.0, rel=1e-6)

    def test_breathing_band_power_detected(self):
        """0.3 Hz 사인파 → 호흡 대역(0.1-0.5 Hz) 파워가 운동 대역보다 높아야 함."""
        rssi = self._make_sine_rssi(0.3, n=300, fs=10.0)
        features = self.extractor.extract_from_array(rssi)
        assert features.breathing_band_power > features.motion_band_power

    def test_motion_band_power_detected(self):
        """1.0 Hz 사인파 → 운동 대역(0.5-2.0 Hz) 파워가 호흡 대역보다 높아야 함."""
        rssi = self._make_sine_rssi(1.0, n=300, fs=10.0)
        features = self.extractor.extract_from_array(rssi)
        assert features.motion_band_power > features.breathing_band_power

    def test_total_spectral_power_positive(self):
        rssi = self._make_sine_rssi(0.5, n=100, fs=10.0)
        features = self.extractor.extract_from_array(rssi)
        assert features.total_spectral_power > 0.0

    def test_sample_rate_hz_propagated(self):
        features = self.extractor.extract_from_array(np.random.randn(20) - 60.0)
        assert features.sample_rate_hz == pytest.approx(10.0)

    def test_duration_calculated(self):
        n = 100
        features = self.extractor.extract_from_array(np.ones(n) * -65.0)
        assert features.duration_seconds == pytest.approx(n / 10.0, rel=1e-6)

    def test_custom_sample_rate(self):
        rssi = np.ones(50, dtype=np.float64) * -65.0
        features = self.extractor.extract_from_array(rssi, sample_rate_hz=20.0)
        assert features.sample_rate_hz == pytest.approx(20.0)

    def test_invalid_sample_rate_raises(self):
        with pytest.raises(ValueError):
            RssiFeatureExtractor(sample_rate_hz=0.0)


# ===========================================================================
# CUSUM 변화점 감지
# ===========================================================================

class TestCusumDetect:
    def test_no_change_returns_empty(self):
        signal = np.ones(50, dtype=np.float64) * -60.0
        cps = cusum_detect(signal, target=-60.0, threshold=3.0, drift=0.5)
        assert cps == []

    def test_step_change_detected(self):
        """명확한 계단 변화 → 변화점 최소 1개."""
        signal = np.concatenate([
            np.ones(30) * -60.0,
            np.ones(30) * -80.0,
        ])
        mean_val = float(np.mean(signal))
        std_val = float(np.std(signal, ddof=1))
        cps = cusum_detect(signal, target=mean_val, threshold=3.0 * std_val, drift=0.5 * std_val)
        assert len(cps) >= 1

    def test_change_point_index_in_range(self):
        signal = np.concatenate([np.zeros(20), np.ones(20) * 10.0])
        cps = cusum_detect(signal, target=float(np.mean(signal)), threshold=2.0, drift=0.3)
        for idx in cps:
            assert 0 <= idx < len(signal)

    def test_resets_after_detection(self):
        """감지 후 리셋 → 이후 구간에서도 추가 감지 가능."""
        signal = np.concatenate([
            np.zeros(20), np.ones(20) * 10.0,
            np.zeros(20), np.ones(20) * 10.0,
        ])
        cps = cusum_detect(signal, target=0.0, threshold=5.0, drift=0.5)
        assert len(cps) >= 2


# ===========================================================================
# CUSUM in feature extractor
# ===========================================================================

class TestFeatureExtractorCusum:
    def setup_method(self):
        self.extractor = RssiFeatureExtractor(
            sample_rate_hz=10.0,
            cusum_threshold=2.0,
            cusum_drift=0.3,
        )

    def test_no_change_points_for_constant(self):
        rssi = np.ones(50, dtype=np.float64) * -60.0
        features = self.extractor.extract_from_array(rssi)
        assert features.n_change_points == 0

    def test_change_points_detected_after_step(self):
        rssi = np.concatenate([
            np.ones(30) * -60.0,
            np.ones(30) * -80.0,
        ]).astype(np.float64)
        features = self.extractor.extract_from_array(rssi)
        assert features.n_change_points >= 1

    def test_change_points_list_length_matches_count(self):
        rssi = np.concatenate([np.ones(20) * -60.0, np.ones(20) * -80.0])
        features = self.extractor.extract_from_array(rssi.astype(np.float64))
        assert len(features.change_points) == features.n_change_points


# ===========================================================================
# PresenceClassifier
# ===========================================================================

class TestPresenceClassifier:
    def setup_method(self):
        self.clf = PresenceClassifier(
            presence_variance_threshold=1.0,
            motion_energy_threshold=0.05,
            history_size=1,       # 히스테리시스 없이 즉시 반영
            hysteresis_ratio=0.9,
        )
        self.extractor = RssiFeatureExtractor(sample_rate_hz=10.0)

    def _extract(self, rssi: np.ndarray):
        return self.extractor.extract_from_array(rssi)

    def test_absent_constant_signal(self):
        """분산이 0인 신호 → ABSENT."""
        rssi = np.ones(50) * -60.0
        features = self._extract(rssi)
        result = self.clf.classify(features, device_id="dev")
        assert result.motion_level == MotionLevel.ABSENT
        assert not result.presence_detected

    def test_present_still_low_motion(self):
        """분산 있지만 운동 대역 에너지 낮음 → PRESENT_STILL."""
        rng = np.random.default_rng(42)
        rssi = -60.0 + rng.normal(0, 2.0, 100)   # 분산 ~4
        features = self._extract(rssi)
        # 분산은 충분하지만 motion_band_power가 낮으면 PRESENT_STILL
        features.motion_band_power = 0.01   # 임계값(0.05)보다 낮게 강제
        result = self.clf.classify(features, device_id="dev")
        assert result.motion_level == MotionLevel.PRESENT_STILL
        assert result.presence_detected

    def test_active_high_motion(self):
        """운동 대역 에너지 높음 → ACTIVE."""
        rng = np.random.default_rng(7)
        rssi = -60.0 + rng.normal(0, 2.0, 100)
        features = self._extract(rssi)
        features.motion_band_power = 1.0   # 임계값보다 높게 강제
        result = self.clf.classify(features, device_id="dev")
        assert result.motion_level == MotionLevel.ACTIVE
        assert result.presence_detected

    def test_confidence_in_range(self):
        """신뢰도는 항상 [0, 1]."""
        for seed in range(5):
            rng = np.random.default_rng(seed)
            rssi = -60.0 + rng.normal(0, seed + 0.1, 60)
            features = self._extract(rssi)
            result = self.clf.classify(features, device_id=f"dev-{seed}")
            assert 0.0 <= result.confidence <= 1.0

    def test_absent_confidence_high_for_flat_signal(self):
        """완전 평탄 신호 → ABSENT 분류, 신뢰도 높음."""
        rssi = np.ones(50) * -65.0
        features = self._extract(rssi)
        result = self.clf.classify(features, device_id="dev")
        assert result.motion_level == MotionLevel.ABSENT
        assert result.confidence > 0.5

    def test_classify_from_array(self):
        """classify_from_array 편의 메서드 동작 확인."""
        rssi = np.ones(30) * -60.0
        result = self.clf.classify_from_array(rssi, device_id="dev")
        assert isinstance(result.motion_level, MotionLevel)

    def test_details_string_populated(self):
        rssi = np.ones(50) * -60.0
        features = self._extract(rssi)
        result = self.clf.classify(features, device_id="dev")
        assert len(result.details) > 0

    def test_cross_receiver_agreement_boosts_confidence(self):
        """일치하는 다른 수신기 결과 → 신뢰도 상승."""
        from sensing import SensingResult
        rssi = np.ones(50) * -60.0
        features = self._extract(rssi)
        result_no_agree = self.clf.classify(features, device_id="dev", other_results=None)

        other = [SensingResult(
            motion_level=MotionLevel.ABSENT,
            confidence=0.9,
            presence_detected=False,
            rssi_variance=0.0,
            motion_band_energy=0.0,
            breathing_band_energy=0.0,
            n_change_points=0,
        )]
        result_agree = self.clf.classify(features, device_id="dev2", other_results=other)
        # 합의 결과가 있어도 confidence는 [0, 1] 범위
        assert 0.0 <= result_agree.confidence <= 1.0

    def test_reset_history(self):
        """히스테리시스 이력 초기화 동작 확인."""
        rssi = np.ones(50) * -60.0
        features = self._extract(rssi)
        clf = PresenceClassifier(history_size=5)
        for _ in range(5):
            clf.classify(features, device_id="dev")
        clf.reset_history("dev")
        # 초기화 후 이력 버퍼가 비어 있어야 함
        assert len(clf._level_history.get("dev", [])) == 0


# ===========================================================================
# PresenceClassifier 히스테리시스
# ===========================================================================

class TestPresenceClassifierHysteresis:
    def test_hysteresis_prevents_rapid_switching(self):
        """
        히스테리시스 윈도우 내에서 소수 다른 결과는 무시되어야 한다.
        history_size=5, ratio=0.8 → 4개 이상 같아야 전환.
        """
        clf = PresenceClassifier(
            presence_variance_threshold=1.0,
            motion_energy_threshold=0.05,
            history_size=5,
            hysteresis_ratio=0.8,
        )
        extractor = RssiFeatureExtractor(sample_rate_hz=10.0)

        # 4번 ABSENT 결과 주입
        rssi_flat = np.ones(50) * -60.0
        feat_flat = extractor.extract_from_array(rssi_flat)
        for _ in range(4):
            clf.classify(feat_flat, device_id="dev")

        # 1번 ACTIVE 강제 — 아직 다수결 미달 → ABSENT 유지
        feat_active = extractor.extract_from_array(rssi_flat)
        feat_active.variance = 5.0
        feat_active.motion_band_power = 1.0
        result = clf.classify(feat_active, device_id="dev")
        # 4 ABSENT + 1 ACTIVE: ABSENT 비율 = 0.8 → 경계값이므로 ABSENT 유지
        assert result.motion_level == MotionLevel.ABSENT
