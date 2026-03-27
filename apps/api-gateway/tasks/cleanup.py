"""
Periodic cleanup task — Phase 4-11.

30일 이상 오래된 CSI 레코드를 매일 자정에 삭제합니다.
asyncio 기반, FastAPI lifespan에서 백그라운드 태스크로 실행.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select

logger = logging.getLogger("ruview.cleanup")

# 설정
CSI_RETENTION_DAYS = int(os.getenv("CSI_RETENTION_DAYS", "30"))
EVENT_RETENTION_DAYS = int(os.getenv("EVENT_RETENTION_DAYS", "90"))
CLEANUP_BATCH_SIZE = int(os.getenv("CLEANUP_BATCH_SIZE", "500"))


class CleanupRunner:
    """CSI 레코드 및 이벤트 클린업 실행기."""

    def __init__(self):
        self.run_count = 0
        self.total_deleted = 0
        self.last_run: datetime | None = None
        self.running = False

    # ── 개별 정리 작업 ──────────────────────────────────────────────────────

    async def _delete_old_csi(self, session) -> int:
        """30일+ CSI 레코드 배치 삭제."""
        if CSI_RETENTION_DAYS <= 0:
            return 0

        from database.models import CSIRecord

        cutoff = datetime.now(timezone.utc) - timedelta(days=CSI_RETENTION_DAYS)
        total = 0

        while True:
            # 삭제 대상 ID 조회 (배치)
            id_q = (
                select(CSIRecord.id)
                .where(CSIRecord.captured_at < cutoff)
                .limit(CLEANUP_BATCH_SIZE)
            )
            result = await session.execute(id_q)
            ids = [row[0] for row in result.fetchall()]
            if not ids:
                break

            await session.execute(delete(CSIRecord).where(CSIRecord.id.in_(ids)))
            await session.commit()
            total += len(ids)
            logger.debug("CSI 레코드 %d건 삭제 (누적: %d)", len(ids), total)

            # DB 부하 분산
            await asyncio.sleep(0.05)

        return total

    async def _delete_old_events(self, session) -> int:
        """90일+ 이벤트 레코드 삭제."""
        if EVENT_RETENTION_DAYS <= 0:
            return 0

        from database.models import DetectionEvent

        cutoff = datetime.now(timezone.utc) - timedelta(days=EVENT_RETENTION_DAYS)
        total = 0

        while True:
            id_q = (
                select(DetectionEvent.id)
                .where(DetectionEvent.created_at < cutoff)
                .limit(CLEANUP_BATCH_SIZE)
            )
            result = await session.execute(id_q)
            ids = [row[0] for row in result.fetchall()]
            if not ids:
                break

            await session.execute(
                delete(DetectionEvent).where(DetectionEvent.id.in_(ids))
            )
            await session.commit()
            total += len(ids)
            logger.debug("이벤트 레코드 %d건 삭제 (누적: %d)", len(ids), total)
            await asyncio.sleep(0.05)

        return total

    # ── 전체 실행 ────────────────────────────────────────────────────────────

    async def run_once(self) -> dict:
        """모든 정리 작업을 1회 실행하고 결과를 반환합니다."""
        if self.running:
            return {"status": "already_running"}

        self.running = True
        start = datetime.now(timezone.utc)
        result: dict = {
            "status": "ok",
            "started_at": start.isoformat(),
            "csi_deleted": 0,
            "events_deleted": 0,
        }

        try:
            from database import get_db

            async with get_db() as session:
                result["csi_deleted"] = await self._delete_old_csi(session)
                result["events_deleted"] = await self._delete_old_events(session)

            total = result["csi_deleted"] + result["events_deleted"]
            self.total_deleted += total
            self.run_count += 1
            self.last_run = start
            logger.info(
                "정리 완료 — CSI %d건, 이벤트 %d건 삭제 (소요: %.2fs)",
                result["csi_deleted"],
                result["events_deleted"],
                (datetime.now(timezone.utc) - start).total_seconds(),
            )

        except Exception as exc:
            result["status"] = "error"
            result["error"] = str(exc)
            logger.error("정리 작업 실패: %s", exc, exc_info=True)
        finally:
            self.running = False

        return result

    def stats(self) -> dict:
        return {
            "run_count": self.run_count,
            "total_deleted": self.total_deleted,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "csi_retention_days": CSI_RETENTION_DAYS,
            "event_retention_days": EVENT_RETENTION_DAYS,
        }


def _seconds_until_midnight() -> float:
    """다음 자정까지 남은 초를 반환합니다."""
    now = datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return (tomorrow - now).total_seconds()


async def schedule_cleanup(runner: CleanupRunner | None = None) -> None:
    """매일 자정에 cleanup을 실행하는 루프 태스크.

    FastAPI lifespan에서 asyncio.create_task(schedule_cleanup())으로 사용:

        async with asyncio.TaskGroup() as tg:
            tg.create_task(schedule_cleanup())
    """
    if runner is None:
        runner = CleanupRunner()

    logger.info("Cleanup 스케줄러 시작 (매일 자정 실행)")

    while True:
        wait_sec = _seconds_until_midnight()
        logger.info("다음 정리 실행까지 %.0f초", wait_sec)
        try:
            await asyncio.sleep(wait_sec)
            await runner.run_once()
        except asyncio.CancelledError:
            logger.info("Cleanup 스케줄러 취소됨")
            break
        except Exception as exc:
            logger.error("Cleanup 스케줄러 오류: %s", exc, exc_info=True)
            # 오류 후 1시간 대기
            await asyncio.sleep(3600)
