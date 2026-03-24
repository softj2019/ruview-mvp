"""
Alert notification system (Phase 3-5).

Pluggable notification backends with rate limiting.
Backends:
  - Console log (always active)
  - WebSocket broadcast (always active — broadcasts "alert" type message)
  - Webhook (POST to configurable URL, env: RUVIEW_WEBHOOK_URL)
"""
import asyncio
import json
import os
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Any, Protocol

import httpx


@dataclass
class Alert:
    """Single alert record."""
    id: str
    event_type: str
    message: str
    severity: str  # "info" | "warning" | "critical"
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class NotifierBackend(Protocol):
    """Protocol for notification backends."""

    async def send(self, alert: Alert) -> None: ...


class ConsoleBackend:
    """Always-active console log backend."""

    async def send(self, alert: Alert) -> None:
        severity_tag = alert.severity.upper()
        print(
            f"[ALERT][{severity_tag}] {alert.event_type}: {alert.message} "
            f"(id={alert.id})"
        )


class WebSocketBackend:
    """Always-active WebSocket broadcast backend.

    Requires a broadcast coroutine (from SignalAdapterRuntime).
    """

    def __init__(self, broadcast_fn):
        """
        Args:
            broadcast_fn: async callable(message_type: str, payload: dict)
        """
        self._broadcast = broadcast_fn

    async def send(self, alert: Alert) -> None:
        await self._broadcast("alert", alert.to_dict())


class WebhookBackend:
    """POST alerts to a configurable webhook URL.

    URL is read from env RUVIEW_WEBHOOK_URL. If not set, this backend
    is effectively a no-op.
    """

    def __init__(self, url: str | None = None):
        self._url = url or os.getenv("RUVIEW_WEBHOOK_URL")

    async def send(self, alert: Alert) -> None:
        if not self._url:
            return
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    self._url,
                    json=alert.to_dict(),
                    headers={"Content-Type": "application/json"},
                )
        except Exception as exc:
            print(f"[ALERT][webhook] Failed to POST to {self._url}: {exc}")


class Notifier:
    """Central alert notifier with pluggable backends and rate limiting.

    Rate limiting: max 1 alert per event_type per 60 seconds.
    Alert history: keeps the last 50 alerts.
    """

    RATE_LIMIT_SECONDS = 60
    HISTORY_MAX = 50

    def __init__(self) -> None:
        self._backends: list[NotifierBackend] = []
        self._last_alert_time: dict[str, float] = {}
        self._history: deque[Alert] = deque(maxlen=self.HISTORY_MAX)
        self._alert_counter = 0

    def add_backend(self, backend: NotifierBackend) -> None:
        self._backends.append(backend)

    async def notify(
        self,
        event_type: str,
        message: str,
        severity: str = "info",
        metadata: dict[str, Any] | None = None,
    ) -> Alert | None:
        """Send an alert through all backends.

        Returns the Alert if sent, None if rate-limited.
        """
        now = time.monotonic()
        last = self._last_alert_time.get(event_type, 0.0)
        if now - last < self.RATE_LIMIT_SECONDS:
            return None  # rate limited

        self._last_alert_time[event_type] = now
        self._alert_counter += 1

        from datetime import datetime, timezone

        alert = Alert(
            id=f"alert-{self._alert_counter}-{int(time.time() * 1000)}",
            event_type=event_type,
            message=message,
            severity=severity,
            metadata=metadata or {},
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        self._history.appendleft(alert)

        for backend in self._backends:
            try:
                await backend.send(alert)
            except Exception as exc:
                print(f"[ALERT] Backend {type(backend).__name__} failed: {exc}")

        return alert

    def get_history(self) -> list[dict[str, Any]]:
        """Return last 50 alerts as dicts."""
        return [a.to_dict() for a in self._history]
