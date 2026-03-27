"""
Unit tests for notifier.py

Covers:
- Alert creation (id, type, severity, timestamp)
- Rate limiting (same event_type within 60s returns None)
- ConsoleBackend.send() prints output
- get_history() returns up to last 50 alerts
- WebSocketBackend.send() calls broadcast_fn
- WebhookBackend.send() skips when no URL
"""
import asyncio
import sys
import os
import time
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from notifier import Alert, Notifier, ConsoleBackend, WebSocketBackend, WebhookBackend


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(coro):
    """Run a coroutine synchronously (Python 3.10+ compatible)."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Alert model tests
# ---------------------------------------------------------------------------

class TestAlertModel:
    def test_alert_to_dict_has_all_fields(self):
        alert = Alert(
            id="alert-1",
            event_type="fall_suspected",
            message="Fall detected",
            severity="critical",
            metadata={"motion_index": 9.5},
            timestamp="2024-01-01T00:00:00+00:00",
        )
        d = alert.to_dict()
        assert d["id"] == "alert-1"
        assert d["event_type"] == "fall_suspected"
        assert d["message"] == "Fall detected"
        assert d["severity"] == "critical"
        assert d["metadata"]["motion_index"] == 9.5
        assert d["timestamp"] == "2024-01-01T00:00:00+00:00"

    def test_alert_default_metadata_is_empty_dict(self):
        alert = Alert(id="x", event_type="test", message="m", severity="info")
        assert alert.metadata == {}

    def test_alert_default_timestamp_is_empty_string(self):
        alert = Alert(id="x", event_type="test", message="m", severity="info")
        assert alert.timestamp == ""


# ---------------------------------------------------------------------------
# Notifier creation and alert tests
# ---------------------------------------------------------------------------

class TestNotifierAlertCreation:
    def test_notify_returns_alert(self):
        n = Notifier()
        alert = run(n.notify("motion", "Motion detected", severity="info"))
        assert isinstance(alert, Alert)

    def test_alert_id_contains_counter(self):
        n = Notifier()
        alert = run(n.notify("motion", "Motion detected"))
        assert "alert-1" in alert.id

    def test_alert_event_type_set(self):
        n = Notifier()
        alert = run(n.notify("fall_suspected", "Fall detected", severity="critical"))
        assert alert.event_type == "fall_suspected"

    def test_alert_severity_set(self):
        n = Notifier()
        alert = run(n.notify("signal_weak", "Weak signal", severity="warning"))
        assert alert.severity == "warning"

    def test_alert_timestamp_is_iso_format(self):
        n = Notifier()
        alert = run(n.notify("test_event", "Test", severity="info"))
        # ISO format contains 'T' and timezone info
        assert "T" in alert.timestamp

    def test_alert_metadata_passed_through(self):
        n = Notifier()
        meta = {"rssi": -88.0, "device_id": "dev-1"}
        alert = run(n.notify("signal_weak", "Weak", metadata=meta))
        assert alert.metadata["rssi"] == pytest.approx(-88.0)

    def test_alert_counter_increments(self):
        n = Notifier()
        a1 = run(n.notify("type_a", "m1"))
        time.sleep(0.001)
        # Type B is different, so not rate-limited
        a2 = run(n.notify("type_b", "m2"))
        assert a1 is not None
        assert a2 is not None
        # Counter should have incremented
        assert "alert-2" in a2.id


# ---------------------------------------------------------------------------
# Rate limiting tests
# ---------------------------------------------------------------------------

class TestRateLimiting:
    def test_second_call_same_type_returns_none(self):
        n = Notifier()
        run(n.notify("fall_suspected", "First"))
        second = run(n.notify("fall_suspected", "Second"))
        assert second is None

    def test_different_types_not_rate_limited(self):
        n = Notifier()
        a1 = run(n.notify("fall_suspected", "Fall"))
        a2 = run(n.notify("signal_weak", "Signal"))
        assert a1 is not None
        assert a2 is not None

    def test_rate_limit_expires_after_period(self):
        n = Notifier()
        run(n.notify("motion", "First"))
        # Manually reset the last alert time to simulate expiry
        n._last_alert_time["motion"] = time.monotonic() - (Notifier.RATE_LIMIT_SECONDS + 1)
        second = run(n.notify("motion", "Second (after expiry)"))
        assert second is not None

    def test_rate_limited_alert_not_added_to_history(self):
        n = Notifier()
        run(n.notify("test_type", "First"))
        run(n.notify("test_type", "Rate limited"))
        history = n.get_history()
        count = sum(1 for h in history if h["event_type"] == "test_type")
        assert count == 1


# ---------------------------------------------------------------------------
# ConsoleBackend tests
# ---------------------------------------------------------------------------

class TestConsoleBackend:
    def test_send_prints_alert_info(self, capsys):
        backend = ConsoleBackend()
        alert = Alert(
            id="alert-test",
            event_type="fall_suspected",
            message="Fall detected",
            severity="critical",
        )
        run(backend.send(alert))
        captured = capsys.readouterr()
        assert "CRITICAL" in captured.out
        assert "fall_suspected" in captured.out
        assert "Fall detected" in captured.out

    def test_send_includes_alert_id(self, capsys):
        backend = ConsoleBackend()
        alert = Alert(id="my-id-123", event_type="motion", message="Motion", severity="info")
        run(backend.send(alert))
        captured = capsys.readouterr()
        assert "my-id-123" in captured.out

    def test_console_backend_is_awaitable(self):
        backend = ConsoleBackend()
        alert = Alert(id="x", event_type="test", message="t", severity="info")
        # Should not raise
        run(backend.send(alert))


# ---------------------------------------------------------------------------
# get_history() tests
# ---------------------------------------------------------------------------

class TestGetHistory:
    def test_history_initially_empty(self):
        n = Notifier()
        assert n.get_history() == []

    def test_history_stores_sent_alerts(self):
        n = Notifier()
        run(n.notify("motion", "M1", severity="info"))
        history = n.get_history()
        assert len(history) == 1
        assert history[0]["event_type"] == "motion"

    def test_history_returns_dicts(self):
        n = Notifier()
        run(n.notify("motion", "test"))
        history = n.get_history()
        assert isinstance(history[0], dict)

    def test_history_capped_at_50(self):
        n = Notifier()
        # Send 60 distinct event types to bypass rate limiting
        for i in range(60):
            run(n.notify(f"event_{i}", f"msg {i}"))
        history = n.get_history()
        assert len(history) <= Notifier.HISTORY_MAX

    def test_history_most_recent_first(self):
        n = Notifier()
        run(n.notify("type_alpha", "First event"))
        run(n.notify("type_beta", "Second event"))
        history = n.get_history()
        # Most recent (type_beta) should be first
        assert history[0]["event_type"] == "type_beta"


# ---------------------------------------------------------------------------
# WebSocketBackend tests
# ---------------------------------------------------------------------------

class TestWebSocketBackend:
    def test_send_calls_broadcast_fn(self):
        broadcast_fn = AsyncMock()
        backend = WebSocketBackend(broadcast_fn)
        alert = Alert(id="ws-1", event_type="fall", message="Fall", severity="critical")
        run(backend.send(alert))
        broadcast_fn.assert_called_once()

    def test_send_passes_alert_as_dict(self):
        broadcast_fn = AsyncMock()
        backend = WebSocketBackend(broadcast_fn)
        alert = Alert(id="ws-2", event_type="motion", message="Motion", severity="info")
        run(backend.send(alert))
        args = broadcast_fn.call_args
        msg_type, payload = args[0]
        assert msg_type == "alert"
        assert payload["id"] == "ws-2"
        assert payload["event_type"] == "motion"


# ---------------------------------------------------------------------------
# WebhookBackend tests
# ---------------------------------------------------------------------------

class TestWebhookBackend:
    def test_send_no_url_is_noop(self):
        backend = WebhookBackend(url=None)
        # Remove env var if set
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RUVIEW_WEBHOOK_URL", None)
            alert = Alert(id="wh-1", event_type="test", message="test", severity="info")
            # Should not raise
            run(backend.send(alert))

    def test_send_posts_to_url(self):
        import httpx
        alert = Alert(
            id="wh-2",
            event_type="fall",
            message="Fall",
            severity="critical",
            metadata={"key": "val"},
        )
        mock_response = MagicMock()
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            backend = WebhookBackend(url="http://test.local/webhook")
            run(backend.send(alert))
            mock_client.post.assert_called_once()
            call_kwargs = mock_client.post.call_args
            assert call_kwargs[0][0] == "http://test.local/webhook"

    def test_webhook_backend_reads_env_url(self):
        with patch.dict(os.environ, {"RUVIEW_WEBHOOK_URL": "http://env.local/hook"}):
            backend = WebhookBackend()
            assert backend._url == "http://env.local/hook"

    def test_webhook_backend_explicit_url_overrides_env(self):
        with patch.dict(os.environ, {"RUVIEW_WEBHOOK_URL": "http://env.local/hook"}):
            backend = WebhookBackend(url="http://override.local/hook")
            assert backend._url == "http://override.local/hook"

    def test_backend_failure_does_not_propagate(self):
        """A failed backend should not crash the Notifier."""
        class BadBackend:
            async def send(self, alert):
                raise RuntimeError("backend failure")

        n = Notifier()
        n.add_backend(BadBackend())
        # Should not raise
        result = run(n.notify("test_fail", "Should not crash"))
        assert result is not None
