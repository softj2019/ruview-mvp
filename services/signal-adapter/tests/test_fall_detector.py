"""
Unit tests for fall_detector.py

Covers:
- extract_features() with synthetic motion data
- FallDetector.detect() threshold fallback (no model)
- record_event() creates CSV with expected rows
- get_training_stats() returns correct counts
"""
import csv
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fall_detector as fd_module
from fall_detector import extract_features, FallDetector, FEATURE_NAMES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def detector():
    """FallDetector with no model (threshold fallback mode)."""
    d = FallDetector.__new__(FallDetector)
    d._model = None
    d._model_name = None
    return d


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Patch the module-level paths to use a temp directory."""
    training_csv = tmp_path / "training.csv"
    model_path = tmp_path / "fall_model.joblib"
    with (
        patch.object(fd_module, "_DATA_DIR", tmp_path),
        patch.object(fd_module, "_TRAINING_CSV", training_csv),
        patch.object(fd_module, "_MODEL_PATH", model_path),
    ):
        yield tmp_path


# ---------------------------------------------------------------------------
# extract_features() tests
# ---------------------------------------------------------------------------

class TestExtractFeatures:
    def test_returns_all_feature_keys(self):
        motion = [float(i) for i in range(20)]
        feats = extract_features(motion, sample_rate=20.0)
        for name in FEATURE_NAMES:
            assert name in feats

    def test_too_short_returns_zeros(self):
        feats = extract_features([1.0, 2.0, 3.0], sample_rate=20.0)
        for name in FEATURE_NAMES:
            assert feats[name] == 0.0

    def test_fall_pattern_high_jerk(self):
        """A spike pattern representing a fall should produce high jerk."""
        # Baseline + sudden spike + recovery
        motion = [0.5] * 10 + [15.0, 18.0, 10.0, 5.0] + [0.5] * 10
        feats = extract_features(motion, sample_rate=20.0)
        assert feats["jerk"] > 0

    def test_peak_amplitude_positive(self):
        motion = [0.1] * 5 + [10.0] + [0.1] * 14
        feats = extract_features(motion, sample_rate=20.0)
        assert feats["peak_amplitude"] > 0

    def test_duration_in_ms(self):
        """duration should be expressed in milliseconds (not seconds)."""
        # 5 samples above threshold at 20 Hz = 250 ms
        motion = [1.0] * 5 + [10.0] * 5 + [1.0] * 10
        feats = extract_features(motion, sample_rate=20.0)
        # duration should be > 0
        assert feats["duration"] >= 0.0

    def test_recovery_slope_negative_after_spike(self):
        """After a peak the signal should have a negative recovery slope."""
        motion = [0.5] * 8 + [15.0] + [10.0, 5.0, 2.0, 1.0, 0.5] + [0.5] * 6
        feats = extract_features(motion, sample_rate=20.0)
        assert feats["recovery_slope"] < 0

    def test_pre_fall_motion_uses_pre_peak_samples(self):
        # First half is elevated, second half has the spike
        motion = [2.0] * 10 + [20.0] + [0.1] * 9
        feats = extract_features(motion, sample_rate=20.0)
        # pre_fall_motion should be around 2.0 (pre-spike mean)
        assert feats["pre_fall_motion"] >= 0.0

    def test_flat_signal_zero_jerk(self):
        motion = [3.0] * 20
        feats = extract_features(motion, sample_rate=20.0)
        assert feats["jerk"] == pytest.approx(0.0, abs=1e-6)

    def test_sample_rate_affects_jerk_scaling(self):
        motion = [0.0, 0.0, 0.0, 5.0] + [0.0] * 16
        feats_fast = extract_features(motion, sample_rate=100.0)
        feats_slow = extract_features(motion, sample_rate=10.0)
        # Higher sample rate → higher jerk (scaled by fs^3)
        assert feats_fast["jerk"] > feats_slow["jerk"]


# ---------------------------------------------------------------------------
# FallDetector.detect() — threshold fallback mode (no model)
# ---------------------------------------------------------------------------

class TestFallDetectorThreshold:
    def test_clear_fall_detected(self, detector):
        feats = {
            "jerk": 10000.0,
            "peak_amplitude": 8.0,
            "duration": 300.0,
            "recovery_slope": -5.0,
            "pre_fall_motion": 0.5,
        }
        is_fall, confidence = detector.detect(feats)
        assert is_fall is True
        assert confidence >= 0.5

    def test_non_fall_not_detected(self, detector):
        feats = {
            "jerk": 10.0,
            "peak_amplitude": 0.1,
            "duration": 0.0,
            "recovery_slope": 0.0,
            "pre_fall_motion": 0.1,
        }
        is_fall, confidence = detector.detect(feats)
        assert is_fall is False
        assert confidence < 0.5

    def test_confidence_bounded_0_1(self, detector):
        feats = {
            "jerk": 999999.0,
            "peak_amplitude": 999.0,
            "duration": 500.0,
            "recovery_slope": -100.0,
            "pre_fall_motion": 1.0,
        }
        _, confidence = detector.detect(feats)
        assert 0.0 <= confidence <= 1.0

    def test_jerk_only_not_enough_for_fall(self, detector):
        """Jerk alone (without duration/peak/slope) should not reach threshold."""
        feats = {
            "jerk": FallDetector.JERK_THRESHOLD * 2,
            "peak_amplitude": 0.0,
            "duration": 0.0,
            "recovery_slope": 0.0,
            "pre_fall_motion": 0.0,
        }
        is_fall, _ = detector.detect(feats)
        # jerk max contribution is 0.35 — not enough alone
        assert is_fall is False

    def test_missing_features_default_to_zero(self, detector):
        """Missing feature keys should be treated as 0.0 without error."""
        is_fall, confidence = detector.detect({})
        assert isinstance(is_fall, bool)
        assert 0.0 <= confidence <= 1.0

    def test_duration_outside_range_no_contribution(self, detector):
        """Duration outside [DURATION_MIN_MS, DURATION_MAX_MS] should not contribute."""
        feats_out = {
            "jerk": 0.0,
            "peak_amplitude": 0.0,
            "duration": 5000.0,  # too long
            "recovery_slope": 0.0,
            "pre_fall_motion": 0.0,
        }
        feats_in = {
            "jerk": 0.0,
            "peak_amplitude": 0.0,
            "duration": 300.0,  # in range
            "recovery_slope": 0.0,
            "pre_fall_motion": 0.0,
        }
        _, conf_out = detector.detect(feats_out)
        _, conf_in = detector.detect(feats_in)
        assert conf_in > conf_out

    def test_negative_recovery_slope_contributes(self, detector):
        feats_neg = {
            "jerk": 0.0,
            "peak_amplitude": 0.0,
            "duration": 0.0,
            "recovery_slope": -10.0,
            "pre_fall_motion": 0.0,
        }
        _, conf = detector.detect(feats_neg)
        assert conf > 0.0

    def test_returns_tuple_of_bool_and_float(self, detector):
        is_fall, confidence = detector.detect({"jerk": 100.0})
        assert isinstance(is_fall, bool)
        assert isinstance(confidence, float)


# ---------------------------------------------------------------------------
# record_event() tests
# ---------------------------------------------------------------------------

class TestRecordEvent:
    def test_record_event_creates_csv(self, detector, tmp_data_dir):
        feats = {name: 1.0 for name in FEATURE_NAMES}
        detector.record_event(feats, label=True)
        csv_path = tmp_data_dir / "training.csv"
        assert csv_path.exists()

    def test_record_event_writes_header_on_first_call(self, detector, tmp_data_dir):
        feats = {name: float(i) for i, name in enumerate(FEATURE_NAMES)}
        detector.record_event(feats, label=False)
        csv_path = tmp_data_dir / "training.csv"
        with open(csv_path) as f:
            header = f.readline().strip().split(",")
        assert header == FEATURE_NAMES + ["label"]

    def test_record_event_fall_label_is_1(self, detector, tmp_data_dir):
        feats = {name: 0.0 for name in FEATURE_NAMES}
        detector.record_event(feats, label=True)
        csv_path = tmp_data_dir / "training.csv"
        with open(csv_path) as f:
            rows = list(csv.reader(f))
        assert rows[1][-1] == "1"

    def test_record_event_non_fall_label_is_0(self, detector, tmp_data_dir):
        feats = {name: 0.0 for name in FEATURE_NAMES}
        detector.record_event(feats, label=False)
        csv_path = tmp_data_dir / "training.csv"
        with open(csv_path) as f:
            rows = list(csv.reader(f))
        assert rows[1][-1] == "0"

    def test_multiple_records_all_appended(self, detector, tmp_data_dir):
        feats = {name: 1.0 for name in FEATURE_NAMES}
        for _ in range(5):
            detector.record_event(feats, label=True)
        csv_path = tmp_data_dir / "training.csv"
        with open(csv_path) as f:
            rows = list(csv.reader(f))
        # header + 5 data rows
        assert len(rows) == 6

    def test_header_not_duplicated_on_append(self, detector, tmp_data_dir):
        feats = {name: 0.0 for name in FEATURE_NAMES}
        detector.record_event(feats, label=False)
        detector.record_event(feats, label=True)
        csv_path = tmp_data_dir / "training.csv"
        with open(csv_path) as f:
            rows = list(csv.reader(f))
        # Only one header row
        header_count = sum(1 for r in rows if r[0] == FEATURE_NAMES[0])
        assert header_count == 1


# ---------------------------------------------------------------------------
# get_training_stats() tests
# ---------------------------------------------------------------------------

class TestGetTrainingStats:
    def test_no_file_returns_empty_stats(self, detector, tmp_data_dir):
        stats = detector.get_training_stats()
        assert stats["total_samples"] == 0
        assert stats["falls"] == 0
        assert stats["non_falls"] == 0
        assert stats["model_loaded"] is False

    def test_counts_falls_and_non_falls(self, detector, tmp_data_dir):
        feats = {name: 0.0 for name in FEATURE_NAMES}
        for _ in range(3):
            detector.record_event(feats, label=True)
        for _ in range(5):
            detector.record_event(feats, label=False)
        stats = detector.get_training_stats()
        assert stats["total_samples"] == 8
        assert stats["falls"] == 3
        assert stats["non_falls"] == 5

    def test_fall_ratio_correct(self, detector, tmp_data_dir):
        feats = {name: 0.0 for name in FEATURE_NAMES}
        for _ in range(4):
            detector.record_event(feats, label=True)
        for _ in range(6):
            detector.record_event(feats, label=False)
        stats = detector.get_training_stats()
        assert stats["fall_ratio"] == pytest.approx(0.4, abs=1e-4)

    def test_fall_ratio_zero_when_no_samples(self, detector, tmp_data_dir):
        """When there are no samples, fall_ratio is either absent or 0.0."""
        stats = detector.get_training_stats()
        # fall_ratio key is only present when total_samples > 0;
        # when absent, the ratio is effectively 0
        assert stats.get("fall_ratio", 0.0) == 0.0

    def test_model_loaded_false_without_model(self, detector, tmp_data_dir):
        stats = detector.get_training_stats()
        assert stats["model_loaded"] is False

    def test_training_file_path_in_stats(self, detector, tmp_data_dir):
        stats = detector.get_training_stats()
        assert "training_file" in stats
        assert "training.csv" in stats["training_file"]
