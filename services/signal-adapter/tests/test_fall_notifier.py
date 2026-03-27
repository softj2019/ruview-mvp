"""
Tests for fall_notifier.py — Phase 8-1
"""

import asyncio
import time
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fall_notifier import FallNotifier, FallNotification


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_event(
    event_id: str = "evt-001",
    zone: str = "Room 1001",
    zone_id: str = "zone-1001",
    device_id: str = "dev-001",
    confidence: float = 0.92,
    event_type: str = "fall_confirmed",
) -> dict:
    return {
        "id": event_id,
        "type": event_type,
        "zone": zone,
        "zone_id": zone_id,
        "deviceId": device_id,
        "confidence": confidence,
        "timestamp": "2026-03-27T12:00:00+00:00",
    }


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestFallNotifierBasic:
    def test_no_webhook_still_processes(self):
        notifier = FallNotifier(webhook_url="")
        event = make_event()
        result = run(notifier.on_fall_detected(event))
        assert isinstance(result, FallNotification)
        assert result.zone == "Room 1001"
        assert result.confidence == pytest.approx(0.92)
        assert result.webhook_sent is False
        assert result.suppressed is False

    def test_stats_increments(self):
        notifier = FallNotifier(webhook_url="")
        run(notifier.on_fall_detected(make_event()))
        stats = notifier.get_stats()
        assert stats["total_events"] == 1
        assert stats["total_failed"] == 1  # no webhook → failed

    def test_history_recorded(self):
        notifier = FallNotifier(webhook_url="")
        run(notifier.on_fall_detected(make_event()))
        history = notifier.get_history()
        assert len(history) == 1
        assert history[0]["zone"] == "Room 1001"

    def test_event_fields_mapped(self):
        notifier = FallNotifier(webhook_url="")
        event = make_event(zone_id="zone-1002", confidence=0.75)
        result = run(notifier.on_fall_detected(event))
        assert result.zone_id == "zone-1002"
        assert result.device_id == "dev-001"


class TestFallNotifierRateLimit:
    def test_second_event_same_zone_suppressed(self):
        notifier = FallNotifier(webhook_url="", rate_limit_sec=3600)
        run(notifier.on_fall_detected(make_event()))
        result2 = run(notifier.on_fall_detected(make_event(event_id="evt-002")))
        assert result2.suppressed is True

    def test_different_zones_not_suppressed(self):
        notifier = FallNotifier(webhook_url="", rate_limit_sec=3600)
        run(notifier.on_fall_detected(make_event(zone_id="zone-1001")))
        result2 = run(notifier.on_fall_detected(
            make_event(event_id="evt-002", zone="Room 1002", zone_id="zone-1002")
        ))
        assert result2.suppressed is False

    def test_clear_rate_limit_allows_resend(self):
        notifier = FallNotifier(webhook_url="", rate_limit_sec=3600)
        run(notifier.on_fall_detected(make_event()))
        notifier.clear_rate_limit("zone-1001")
        result = run(notifier.on_fall_detected(make_event(event_id="evt-003")))
        assert result.suppressed is False

    def test_rate_limit_expires(self):
        notifier = FallNotifier(webhook_url="", rate_limit_sec=0)
        run(notifier.on_fall_detected(make_event()))
        result2 = run(notifier.on_fall_detected(make_event(event_id="evt-002")))
        assert result2.suppressed is False

    def test_suppressed_increments_counter(self):
        notifier = FallNotifier(webhook_url="", rate_limit_sec=3600)
        run(notifier.on_fall_detected(make_event()))
        run(notifier.on_fall_detected(make_event(event_id="evt-002")))
        assert notifier.get_stats()["total_suppressed"] == 1


class TestFallNotifierWebhook:
    def test_webhook_success(self):
        """Webhook 전송 성공 시 webhook_sent=True."""
        notifier = FallNotifier(webhook_url="http://fake-webhook.test/alert")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("fall_notifier.httpx.AsyncClient", return_value=mock_client):
            result = run(notifier.on_fall_detected(make_event()))

        assert result.webhook_sent is True
        assert result.webhook_attempts == 1
        assert notifier.get_stats()["total_sent"] == 1

    def test_webhook_retry_on_failure(self):
        """3회 재시도 후 최종 실패 시 webhook_sent=False."""
        notifier = FallNotifier(webhook_url="http://fake-webhook.test/alert")

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=Exception("connection refused"))

        with patch("fall_notifier.httpx.AsyncClient", return_value=mock_client):
            with patch("fall_notifier.asyncio.sleep", new_callable=AsyncMock):
                result = run(notifier.on_fall_detected(make_event()))

        assert result.webhook_sent is False
        assert result.webhook_attempts == 3
        assert result.webhook_error is not None
        assert notifier.get_stats()["total_failed"] == 1

    def test_payload_contains_required_fields(self):
        """Webhook payload에 필수 필드가 포함되어야 함."""
        notifier = FallNotifier(webhook_url="http://fake-webhook.test/alert")
        captured: list[dict] = []

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        async def capture_post(url, json=None, **kwargs):
            captured.append(json or {})
            return mock_resp

        mock_client.post = capture_post

        with patch("fall_notifier.httpx.AsyncClient", return_value=mock_client):
            run(notifier.on_fall_detected(make_event()))

        assert len(captured) == 1
        payload = captured[0]
        required = {"alert_type", "zone", "zone_id", "confidence", "timestamp", "notification_id"}
        assert required.issubset(payload.keys())
        assert payload["alert_type"] == "fall_detected"


class TestFallNotifierHistory:
    def test_history_limit(self):
        notifier = FallNotifier(webhook_url="")
        history = notifier.get_history(limit=5)
        assert isinstance(history, list)
        assert len(history) == 0

    def test_history_newest_first(self):
        notifier = FallNotifier(webhook_url="", rate_limit_sec=0)
        for i in range(3):
            run(notifier.on_fall_detected(make_event(event_id=f"evt-{i}")))
        history = notifier.get_history()
        # 가장 마지막에 추가된 것이 history[0]
        assert history[0]["event_id"] == "evt-2"
