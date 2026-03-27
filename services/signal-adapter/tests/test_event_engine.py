"""
Unit tests for event_engine.py

Covers:
- EventEngine.evaluate() with different motion/rssi levels
- Signal weak detection
- Fall suspected detection
- Presence/stationary transitions
- State machine transitions
"""
import sys
import os

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from event_engine import EventEngine, DetectionEvent
from csi_processor import ProcessedCSI


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_csi(
    device_id="dev-1",
    rssi=-65.0,
    motion_index=0.0,
    presence_score=0.0,
    breathing_rate=None,
    heart_rate=None,
) -> ProcessedCSI:
    return ProcessedCSI(
        device_id=device_id,
        timestamp="2024-01-01T00:00:00Z",
        amplitude=[1.0] * 10,
        phase=[0.0] * 10,
        rssi=rssi,
        noise_floor=-95.0,
        motion_index=motion_index,
        breathing_rate=breathing_rate,
        heart_rate=heart_rate,
        presence_score=presence_score,
        top_k_variance=[0.1] * 8,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    return EventEngine()


# ---------------------------------------------------------------------------
# Basic event evaluation tests
# ---------------------------------------------------------------------------

class TestEventEngineEvaluate:
    def test_empty_room_no_events(self, engine):
        csi = make_csi(motion_index=0.0, rssi=-65.0)
        events = engine.evaluate(csi)
        assert events == []

    def test_returns_list(self, engine):
        csi = make_csi(motion_index=0.0)
        result = engine.evaluate(csi)
        assert isinstance(result, list)

    def test_event_has_required_fields(self, engine):
        csi = make_csi(motion_index=10.0)
        events = engine.evaluate(csi)
        assert len(events) >= 1
        event = events[0]
        assert isinstance(event, DetectionEvent)
        assert event.id
        assert event.type
        assert event.severity
        assert event.device_id == "dev-1"
        assert 0.0 <= event.confidence <= 1.0
        assert event.timestamp


# ---------------------------------------------------------------------------
# Signal weak detection
# ---------------------------------------------------------------------------

class TestSignalWeakDetection:
    def test_signal_weak_event_when_rssi_below_threshold(self, engine):
        csi = make_csi(rssi=-85.0, motion_index=0.0)
        events = engine.evaluate(csi)
        types = [e.type for e in events]
        assert "signal_weak" in types

    def test_no_signal_weak_event_with_good_rssi(self, engine):
        csi = make_csi(rssi=-65.0, motion_index=0.0)
        events = engine.evaluate(csi)
        types = [e.type for e in events]
        assert "signal_weak" not in types

    def test_signal_weak_event_exactly_at_threshold(self, engine):
        # Threshold is -80.0; exactly at threshold should NOT trigger (strict <)
        csi = make_csi(rssi=EventEngine.SIGNAL_WEAK_THRESHOLD, motion_index=0.0)
        events = engine.evaluate(csi)
        types = [e.type for e in events]
        assert "signal_weak" not in types

    def test_signal_weak_event_severity_is_warning(self, engine):
        csi = make_csi(rssi=-90.0, motion_index=0.0)
        events = engine.evaluate(csi)
        weak_events = [e for e in events if e.type == "signal_weak"]
        assert len(weak_events) == 1
        assert weak_events[0].severity == "warning"

    def test_signal_weak_metadata_contains_rssi(self, engine):
        csi = make_csi(rssi=-88.0, motion_index=0.0)
        events = engine.evaluate(csi)
        weak_events = [e for e in events if e.type == "signal_weak"]
        assert "rssi" in weak_events[0].metadata
        assert weak_events[0].metadata["rssi"] == pytest.approx(-88.0)


# ---------------------------------------------------------------------------
# Fall suspected detection
# ---------------------------------------------------------------------------

class TestFallSuspectedDetection:
    def test_fall_suspected_above_fall_threshold(self, engine):
        csi = make_csi(motion_index=EventEngine.FALL_THRESHOLD + 1.0)
        events = engine.evaluate(csi)
        types = [e.type for e in events]
        assert "fall_suspected" in types

    def test_fall_suspected_severity_is_critical(self, engine):
        csi = make_csi(motion_index=10.0)
        events = engine.evaluate(csi)
        fall_events = [e for e in events if e.type == "fall_suspected"]
        assert fall_events[0].severity == "critical"

    def test_fall_confidence_capped_at_095(self, engine):
        csi = make_csi(motion_index=1000.0)
        events = engine.evaluate(csi)
        fall_events = [e for e in events if e.type == "fall_suspected"]
        assert fall_events[0].confidence <= 0.95

    def test_fall_confidence_scales_with_motion(self, engine):
        engine_a = EventEngine()
        engine_b = EventEngine()
        events_a = engine_a.evaluate(make_csi(motion_index=9.0))
        events_b = engine_b.evaluate(make_csi(motion_index=12.0))
        fa = [e for e in events_a if e.type == "fall_suspected"]
        fb = [e for e in events_b if e.type == "fall_suspected"]
        assert fa and fb
        assert fb[0].confidence >= fa[0].confidence

    def test_fall_sets_device_state(self, engine):
        csi = make_csi(device_id="dev-fall", motion_index=10.0)
        engine.evaluate(csi)
        assert engine._state.get("dev-fall") == "fall"

    def test_no_fall_event_below_threshold(self, engine):
        csi = make_csi(motion_index=EventEngine.FALL_THRESHOLD - 1.0)
        events = engine.evaluate(csi)
        types = [e.type for e in events]
        assert "fall_suspected" not in types


# ---------------------------------------------------------------------------
# Presence / stationary transitions
# ---------------------------------------------------------------------------

class TestPresenceStationary:
    def test_presence_detected_event_first_time(self, engine):
        csi = make_csi(motion_index=EventEngine.PRESENCE_THRESHOLD + 0.1)
        events = engine.evaluate(csi)
        types = [e.type for e in events]
        assert "presence_detected" in types

    def test_presence_not_repeated_on_same_state(self, engine):
        csi = make_csi(motion_index=EventEngine.PRESENCE_THRESHOLD + 0.1)
        engine.evaluate(csi)  # first call — presence_detected fired
        events_second = engine.evaluate(csi)  # same state — should NOT re-fire
        types = [e.type for e in events_second]
        assert "presence_detected" not in types

    def test_motion_active_event_above_motion_threshold(self, engine):
        csi = make_csi(motion_index=EventEngine.MOTION_THRESHOLD + 0.5)
        events = engine.evaluate(csi)
        types = [e.type for e in events]
        assert "motion_active" in types

    def test_motion_active_not_repeated(self, engine):
        csi = make_csi(motion_index=EventEngine.MOTION_THRESHOLD + 0.5)
        engine.evaluate(csi)
        events_second = engine.evaluate(csi)
        types = [e.type for e in events_second]
        assert "motion_active" not in types

    def test_stationary_detected_after_motion(self, engine):
        # First, transition to motion state
        csi_motion = make_csi(motion_index=EventEngine.MOTION_THRESHOLD + 0.5)
        engine.evaluate(csi_motion)
        # Now drop to below presence threshold
        csi_empty = make_csi(motion_index=0.0)
        events = engine.evaluate(csi_empty)
        types = [e.type for e in events]
        assert "stationary_detected" in types

    def test_stationary_detected_after_presence(self, engine):
        # Transition to presence state
        csi_presence = make_csi(motion_index=EventEngine.PRESENCE_THRESHOLD + 0.1)
        engine.evaluate(csi_presence)
        # Drop to empty
        csi_empty = make_csi(motion_index=0.0)
        events = engine.evaluate(csi_empty)
        types = [e.type for e in events]
        assert "stationary_detected" in types

    def test_no_stationary_from_empty_state(self, engine):
        csi_empty = make_csi(motion_index=0.0)
        engine.evaluate(csi_empty)  # state starts as empty
        events_second = engine.evaluate(csi_empty)  # stays empty
        types = [e.type for e in events_second]
        assert "stationary_detected" not in types

    def test_multiple_devices_state_independent(self, engine):
        csi_a = make_csi(device_id="dev-a", motion_index=EventEngine.MOTION_THRESHOLD + 1.0)
        csi_b = make_csi(device_id="dev-b", motion_index=0.0)
        engine.evaluate(csi_a)
        engine.evaluate(csi_b)
        assert engine._state.get("dev-a") == "motion"
        assert engine._state.get("dev-b") == "empty"

    def test_detection_event_model_has_uuid_id(self, engine):
        csi = make_csi(motion_index=10.0)
        events = engine.evaluate(csi)
        assert len(events) >= 1
        # UUIDs are 36 characters with hyphens
        assert len(events[0].id) == 36

    def test_detection_event_default_zone(self, engine):
        csi = make_csi(motion_index=10.0)
        events = engine.evaluate(csi)
        assert events[0].zone == "default"


# ---------------------------------------------------------------------------
# High breathing rate detection
# ---------------------------------------------------------------------------

class TestHighBreathingRateDetection:
    def test_high_br_event_above_max(self, engine):
        csi = make_csi(breathing_rate=EventEngine.BREATHING_RATE_MAX + 1.0)
        events = engine.evaluate(csi)
        types = [e.type for e in events]
        assert "high_breathing_rate" in types

    def test_no_high_br_event_within_range(self, engine):
        csi = make_csi(breathing_rate=20.0)
        events = engine.evaluate(csi)
        types = [e.type for e in events]
        assert "high_breathing_rate" not in types

    def test_no_high_br_event_when_none(self, engine):
        csi = make_csi(breathing_rate=None)
        events = engine.evaluate(csi)
        types = [e.type for e in events]
        assert "high_breathing_rate" not in types

    def test_high_br_event_severity_is_warning(self, engine):
        csi = make_csi(breathing_rate=35.0)
        events = engine.evaluate(csi)
        br_events = [e for e in events if e.type == "high_breathing_rate"]
        assert len(br_events) == 1
        assert br_events[0].severity == "warning"

    def test_high_br_metadata_contains_breathing_rate(self, engine):
        csi = make_csi(breathing_rate=34.5)
        events = engine.evaluate(csi)
        br_events = [e for e in events if e.type == "high_breathing_rate"]
        assert "breathing_rate" in br_events[0].metadata
        assert br_events[0].metadata["breathing_rate"] == pytest.approx(34.5)

    def test_no_high_br_at_exact_threshold(self, engine):
        csi = make_csi(breathing_rate=EventEngine.BREATHING_RATE_MAX)
        events = engine.evaluate(csi)
        types = [e.type for e in events]
        assert "high_breathing_rate" not in types


# ---------------------------------------------------------------------------
# Low presence noise detection
# ---------------------------------------------------------------------------

class TestLowPresenceNoiseDetection:
    def test_low_presence_event_below_threshold(self, engine):
        csi = make_csi(presence_score=0.10)
        events = engine.evaluate(csi)
        types = [e.type for e in events]
        assert "low_presence_noise" in types

    def test_no_low_presence_event_above_threshold(self, engine):
        csi = make_csi(presence_score=EventEngine.LOW_PRESENCE_THRESHOLD + 0.1)
        events = engine.evaluate(csi)
        types = [e.type for e in events]
        assert "low_presence_noise" not in types

    def test_low_presence_event_severity_is_info(self, engine):
        csi = make_csi(presence_score=0.05)
        events = engine.evaluate(csi)
        lp_events = [e for e in events if e.type == "low_presence_noise"]
        assert len(lp_events) == 1
        assert lp_events[0].severity == "info"

    def test_low_presence_metadata_contains_score(self, engine):
        csi = make_csi(presence_score=0.111)
        events = engine.evaluate(csi)
        lp_events = [e for e in events if e.type == "low_presence_noise"]
        assert "presence_score" in lp_events[0].metadata
        assert lp_events[0].metadata["presence_score"] == pytest.approx(0.111)

    def test_no_low_presence_at_exact_threshold(self, engine):
        csi = make_csi(presence_score=EventEngine.LOW_PRESENCE_THRESHOLD)
        events = engine.evaluate(csi)
        types = [e.type for e in events]
        assert "low_presence_noise" not in types

    def test_no_low_presence_when_score_is_zero(self, engine):
        # presence_score=0.0 means empty room / no signal — should NOT fire
        csi = make_csi(presence_score=0.0)
        events = engine.evaluate(csi)
        types = [e.type for e in events]
        assert "low_presence_noise" not in types
