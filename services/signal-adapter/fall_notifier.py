"""
낙상 감지 자동 알림 워크플로 — Phase 8-1.

낙상 이벤트를 수신하면:
  1. Webhook POST (FALL_WEBHOOK_URL env)
  2. 재시도 3회 (exponential backoff: 1s → 2s → 4s)
  3. 알림 이력 기록 (메모리 내 deque)
  4. 30분 내 동일 zone 중복 알림 억제 (rate limit)
"""

import asyncio
import json
import logging
import os
import time
import uuid
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger("ruview.fall_notifier")

# 환경 변수
FALL_WEBHOOK_URL: str = os.getenv("FALL_WEBHOOK_URL", "")
WEBHOOK_TIMEOUT_SEC: float = float(os.getenv("FALL_WEBHOOK_TIMEOUT", "10.0"))
RATE_LIMIT_WINDOW_SEC: int = int(os.getenv("FALL_RATE_LIMIT_SEC", "1800"))  # 30분
MAX_HISTORY: int = int(os.getenv("FALL_HISTORY_MAX", "200"))
MAX_RETRIES: int = 3
RETRY_BASE_SEC: float = 1.0


# ── 데이터 클래스 ─────────────────────────────────────────────────────────────

@dataclass
class FallNotification:
    """낙상 알림 단일 레코드."""
    notification_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_id: str = ""
    zone: str = ""
    zone_id: str = ""
    device_id: str = ""
    confidence: float = 0.0
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    webhook_sent: bool = False
    webhook_attempts: int = 0
    webhook_error: str | None = None
    suppressed: bool = False       # rate-limit으로 억제됨
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── 메인 클래스 ──────────────────────────────────────────────────────────────

class FallNotifier:
    """낙상 감지 → 담당자 자동 호출 워크플로."""

    def __init__(
        self,
        webhook_url: str | None = None,
        rate_limit_sec: int = RATE_LIMIT_WINDOW_SEC,
    ):
        self._webhook_url = webhook_url or FALL_WEBHOOK_URL
        self._rate_limit_sec = rate_limit_sec

        # zone_id → 마지막 알림 epoch(float)
        self._last_notified: dict[str, float] = {}
        # 알림 이력 (최신 MAX_HISTORY건)
        self._history: deque[FallNotification] = deque(maxlen=MAX_HISTORY)
        # 통계
        self._total_events = 0
        self._total_sent = 0
        self._total_suppressed = 0
        self._total_failed = 0

    # ── 공개 API ────────────────────────────────────────────────────────────

    async def on_fall_detected(self, event: dict[str, Any]) -> FallNotification:
        """낙상 이벤트 처리 진입점.

        Args:
            event: {
                "id"         : str,
                "type"       : "fall_confirmed" | "fall_suspected",
                "zone"       : str,     # 존 이름
                "zone_id"    : str,     # 존 ID (rate-limit 키)
                "device_id"  : str,
                "confidence" : float,
                "timestamp"  : str,
                ...
            }
        Returns:
            FallNotification — 처리 결과 레코드
        """
        self._total_events += 1

        notif = FallNotification(
            event_id=str(event.get("id", "")),
            zone=str(event.get("zone", "unknown")),
            zone_id=str(event.get("zone_id", event.get("zone", "unknown"))),
            device_id=str(event.get("deviceId", event.get("device_id", ""))),
            confidence=float(event.get("confidence", 0.0)),
            timestamp=str(event.get("timestamp", datetime.now(timezone.utc).isoformat())),
            metadata={k: v for k, v in event.items()
                      if k not in ("id", "zone", "zone_id", "deviceId", "device_id",
                                   "confidence", "timestamp", "type")},
        )

        # ── Rate-limit 체크 ──────────────────────────────────────────────
        if self._is_suppressed(notif.zone_id):
            notif.suppressed = True
            self._total_suppressed += 1
            self._history.append(notif)
            logger.info(
                "[FallNotifier] 억제됨 — zone=%s (rate-limit %ds 이내)",
                notif.zone,
                self._rate_limit_sec,
            )
            return notif

        # ── Webhook 전송 ────────────────────────────────────────────────
        if self._webhook_url:
            await self._send_with_retry(notif)
        else:
            logger.warning("[FallNotifier] FALL_WEBHOOK_URL 미설정 — webhook 스킵")
            notif.webhook_sent = False

        # ── 이력 기록 ────────────────────────────────────────────────────
        self._record_notified(notif.zone_id)
        self._history.append(notif)

        if notif.webhook_sent:
            self._total_sent += 1
        else:
            self._total_failed += 1

        return notif

    # ── Webhook 전송 (재시도) ────────────────────────────────────────────────

    async def _send_with_retry(self, notif: FallNotification) -> None:
        """Webhook POST with exponential backoff (최대 3회)."""
        payload = self._build_payload(notif)

        for attempt in range(1, MAX_RETRIES + 1):
            notif.webhook_attempts = attempt
            delay = RETRY_BASE_SEC * (2 ** (attempt - 1))  # 1s, 2s, 4s

            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        self._webhook_url,
                        json=payload,
                        timeout=WEBHOOK_TIMEOUT_SEC,
                        headers={
                            "Content-Type": "application/json",
                            "X-RuView-Event": "fall_detected",
                            "X-RuView-Confidence": str(notif.confidence),
                        },
                    )
                    resp.raise_for_status()

                notif.webhook_sent = True
                notif.webhook_error = None
                logger.info(
                    "[FallNotifier] Webhook 전송 성공 (시도 %d/%d) — zone=%s, conf=%.2f",
                    attempt, MAX_RETRIES, notif.zone, notif.confidence,
                )
                return

            except Exception as exc:
                notif.webhook_error = str(exc)
                if attempt < MAX_RETRIES:
                    logger.warning(
                        "[FallNotifier] Webhook 실패 (시도 %d/%d, %.1fs 후 재시도) — %s",
                        attempt, MAX_RETRIES, delay, exc,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "[FallNotifier] Webhook 최종 실패 (3회 모두 실패) — zone=%s, err=%s",
                        notif.zone, exc,
                    )

    # ── Rate-limit 헬퍼 ─────────────────────────────────────────────────────

    def _is_suppressed(self, zone_id: str) -> bool:
        last = self._last_notified.get(zone_id)
        if last is None:
            return False
        return (time.monotonic() - last) < self._rate_limit_sec

    def _record_notified(self, zone_id: str) -> None:
        self._last_notified[zone_id] = time.monotonic()

    # ── Payload 빌더 ────────────────────────────────────────────────────────

    def _build_payload(self, notif: FallNotification) -> dict[str, Any]:
        return {
            "notification_id": notif.notification_id,
            "event_id": notif.event_id,
            "alert_type": "fall_detected",
            "zone": notif.zone,
            "zone_id": notif.zone_id,
            "device_id": notif.device_id,
            "confidence": notif.confidence,
            "timestamp": notif.timestamp,
            "metadata": notif.metadata,
        }

    # ── 통계 / 이력 ─────────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_events": self._total_events,
            "total_sent": self._total_sent,
            "total_suppressed": self._total_suppressed,
            "total_failed": self._total_failed,
            "webhook_url_configured": bool(self._webhook_url),
            "rate_limit_sec": self._rate_limit_sec,
            "history_count": len(self._history),
        }

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """최근 알림 이력 반환 (최신 순)."""
        items = list(self._history)
        items.reverse()
        return [n.to_dict() for n in items[:limit]]

    def clear_rate_limit(self, zone_id: str | None = None) -> None:
        """테스트/긴급 해제용 — rate-limit 초기화."""
        if zone_id:
            self._last_notified.pop(zone_id, None)
        else:
            self._last_notified.clear()
        logger.info("[FallNotifier] Rate-limit 초기화 완료 (zone=%s)", zone_id or "ALL")
