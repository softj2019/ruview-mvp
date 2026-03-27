"""
Periodic service monitoring task — Phase 4-11.

5분마다 signal-adapter(8001), api-gateway 자체(8000) 상태를 확인합니다.
이상 감지 시 로그를 출력하고 경고 플래그를 설정합니다.
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger("ruview.monitoring")

# 설정
MONITOR_INTERVAL_SEC = int(os.getenv("MONITOR_INTERVAL_SEC", "300"))  # 5분
HTTP_TIMEOUT_SEC = float(os.getenv("MONITOR_HTTP_TIMEOUT", "5.0"))

# 감시 대상 서비스
DEFAULT_SERVICES: list[dict[str, str]] = [
    {"name": "signal-adapter", "url": os.getenv("SIGNAL_ADAPTER_URL", "http://localhost:8001") + "/health"},
    {"name": "api-gateway",    "url": os.getenv("API_GATEWAY_URL", "http://localhost:8000") + "/health"},
]


@dataclass
class ServiceStatus:
    """단일 서비스의 최신 상태."""
    name: str
    url: str
    healthy: bool = False
    last_check: datetime | None = None
    last_error: str | None = None
    consecutive_failures: int = 0
    latency_ms: float = 0.0
    check_count: int = 0
    failure_count: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "healthy": self.healthy,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "last_error": self.last_error,
            "consecutive_failures": self.consecutive_failures,
            "latency_ms": round(self.latency_ms, 2),
            "check_count": self.check_count,
            "failure_count": self.failure_count,
            "extra": self.extra,
        }


class MonitoringRunner:
    """서비스 헬스 체크 실행기."""

    def __init__(self, services: list[dict[str, str]] | None = None):
        self._service_defs = services or DEFAULT_SERVICES
        self.statuses: dict[str, ServiceStatus] = {
            svc["name"]: ServiceStatus(name=svc["name"], url=svc["url"])
            for svc in self._service_defs
        }
        self.run_count = 0
        self.last_run: datetime | None = None

    async def _check_service(self, svc: ServiceStatus, client: httpx.AsyncClient) -> None:
        """단일 서비스 헬스 체크."""
        t0 = time.monotonic()
        try:
            resp = await client.get(svc.url, timeout=HTTP_TIMEOUT_SEC)
            latency = (time.monotonic() - t0) * 1000

            svc.latency_ms = latency
            svc.check_count += 1
            svc.last_check = datetime.now(timezone.utc)

            if resp.status_code < 400:
                if not svc.healthy:
                    logger.info("[모니터링] %s 복구됨 (%.0fms)", svc.name, latency)
                svc.healthy = True
                svc.consecutive_failures = 0
                svc.last_error = None
                try:
                    svc.extra = resp.json()
                except Exception:
                    svc.extra = {}
            else:
                raise httpx.HTTPStatusError(
                    f"HTTP {resp.status_code}", request=resp.request, response=resp
                )

        except Exception as exc:
            latency = (time.monotonic() - t0) * 1000
            svc.latency_ms = latency
            svc.check_count += 1
            svc.failure_count += 1
            svc.consecutive_failures += 1
            svc.healthy = False
            svc.last_check = datetime.now(timezone.utc)
            svc.last_error = str(exc)

            # 연속 실패 시 로그 레벨 상향
            if svc.consecutive_failures == 1:
                logger.warning("[모니터링] %s 이상 감지: %s", svc.name, exc)
            elif svc.consecutive_failures % 3 == 0:
                logger.error(
                    "[모니터링] %s 연속 %d회 실패: %s",
                    svc.name,
                    svc.consecutive_failures,
                    exc,
                )

    async def run_once(self) -> dict[str, Any]:
        """모든 서비스를 1회 체크합니다."""
        start = datetime.now(timezone.utc)
        async with httpx.AsyncClient() as client:
            tasks = [
                self._check_service(status, client)
                for status in self.statuses.values()
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

        self.run_count += 1
        self.last_run = start

        all_healthy = all(s.healthy for s in self.statuses.values())
        if not all_healthy:
            unhealthy = [n for n, s in self.statuses.items() if not s.healthy]
            logger.warning("[모니터링] 비정상 서비스: %s", ", ".join(unhealthy))

        return {
            "checked_at": start.isoformat(),
            "all_healthy": all_healthy,
            "services": {n: s.to_dict() for n, s in self.statuses.items()},
        }

    def get_status(self) -> dict[str, Any]:
        """현재 상태 스냅샷 반환."""
        return {
            "run_count": self.run_count,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "services": {n: s.to_dict() for n, s in self.statuses.items()},
        }


async def schedule_monitoring(runner: MonitoringRunner | None = None) -> None:
    """5분마다 서비스 상태를 체크하는 루프 태스크.

    FastAPI lifespan에서 asyncio.create_task(schedule_monitoring())으로 사용.
    """
    if runner is None:
        runner = MonitoringRunner()

    logger.info(
        "모니터링 스케줄러 시작 (간격: %d초, 대상: %s)",
        MONITOR_INTERVAL_SEC,
        ", ".join(runner.statuses.keys()),
    )

    while True:
        try:
            await runner.run_once()
            await asyncio.sleep(MONITOR_INTERVAL_SEC)
        except asyncio.CancelledError:
            logger.info("모니터링 스케줄러 취소됨")
            break
        except Exception as exc:
            logger.error("모니터링 스케줄러 오류: %s", exc, exc_info=True)
            await asyncio.sleep(60)
