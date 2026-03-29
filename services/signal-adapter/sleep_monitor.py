"""
Sleep Monitor — 호흡 신호 기반 수면 단계 분류 및 무호흡 감지.

수면 단계 분류 기준 (규칙 기반):
  - Wake:  motion_index > 0.3
  - REM:   motion_index < 0.05, breathing_rate 불규칙 (BRV > 3)
  - Deep:  motion_index < 0.05, breathing_rate 안정 (BRV < 1.5), rate 8-15 BPM
  - Light: 나머지

무호흡 감지:
  - 호흡 진폭 envelope이 10초 이상 임계값(0.02) 이하로 유지될 때
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import time

import numpy as np


@dataclass
class ApneaEvent:
    start_time: str
    end_time: str
    duration_seconds: float


@dataclass
class StageEntry:
    stage: str
    start_time: str
    end_time: Optional[str] = None


@dataclass
class SleepSession:
    start_time: str
    stages: list[StageEntry] = field(default_factory=list)
    apnea_events: list[ApneaEvent] = field(default_factory=list)
    current_stage: str = "Wake"
    current_apnea_start: Optional[float] = None  # monotonic time of apnea onset


class SleepMonitor:
    """호흡 신호 기반 수면 단계 분류 및 무호흡 감지 모듈.

    디바이스별 독립 세션을 유지하며, ProcessedCSI에서 추출된
    breathing_rate, breathing_amplitude, motion_index를 입력으로 받습니다.
    """

    # BRV 계산에 사용할 최근 호흡률 샘플 수
    BRV_WINDOW = 10

    def __init__(
        self,
        apnea_threshold: float = 0.02,
        apnea_min_duration: float = 10.0,
    ) -> None:
        """
        Args:
            apnea_threshold: 무호흡 판단 호흡 진폭 임계값 (default 0.02).
            apnea_min_duration: 무호흡 최소 지속 시간(초) (default 10.0).
        """
        self.apnea_threshold = apnea_threshold
        self.apnea_min_duration = apnea_min_duration

        self._sessions: dict[str, SleepSession] = {}
        self._last_update: dict[str, float] = {}  # monotonic timestamps
        # 디바이스별 최근 호흡률 이력 (BRV 계산용)
        self._br_history: dict[str, deque[float]] = {}

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------

    def _ensure_session(self, device_id: str) -> SleepSession:
        if device_id not in self._sessions:
            now_iso = datetime.now(timezone.utc).isoformat()
            session = SleepSession(start_time=now_iso)
            # 초기 단계 항목 삽입
            session.stages.append(StageEntry(stage="Wake", start_time=now_iso))
            self._sessions[device_id] = session
            self._br_history[device_id] = deque(maxlen=self.BRV_WINDOW)
        return self._sessions[device_id]

    def _calc_brv(self, device_id: str) -> float:
        """최근 호흡률 샘플의 표준편차(BRV)를 반환합니다."""
        history = self._br_history.get(device_id)
        if history is None or len(history) < 2:
            return 0.0
        return float(np.std(list(history)))

    def _classify_stage(
        self,
        motion_index: float,
        breathing_rate: float,
        brv: float,
    ) -> str:
        """수면 단계 분류 규칙 적용."""
        if motion_index > 0.3:
            return "Wake"
        if motion_index < 0.05:
            if brv > 3.0:
                return "REM"
            if brv < 1.5 and 8.0 <= breathing_rate <= 15.0:
                return "Deep"
        return "Light"

    def _check_apnea(
        self,
        session: SleepSession,
        breathing_amplitude: float,
        now_mono: float,
        now_iso: str,
    ) -> Optional[dict]:
        """무호흡 상태 추적. 이벤트 감지 시 dict 반환, 아니면 None."""
        below_threshold = breathing_amplitude < self.apnea_threshold

        if below_threshold:
            if session.current_apnea_start is None:
                session.current_apnea_start = now_mono
            else:
                duration = now_mono - session.current_apnea_start
                if duration >= self.apnea_min_duration:
                    # 무호흡 이벤트 확정 (이미 리스트에 추가된 이벤트 중 미종료 항목 업데이트)
                    if (
                        session.apnea_events
                        and session.apnea_events[-1].end_time == ""
                    ):
                        session.apnea_events[-1].end_time = now_iso
                        session.apnea_events[-1].duration_seconds = round(duration, 2)
                    else:
                        evt = ApneaEvent(
                            start_time=datetime.fromtimestamp(
                                now_mono - duration, tz=timezone.utc
                            ).isoformat(),
                            end_time=now_iso,
                            duration_seconds=round(duration, 2),
                        )
                        session.apnea_events.append(evt)
                        return {
                            "apnea_detected": True,
                            "duration_seconds": evt.duration_seconds,
                            "start_time": evt.start_time,
                            "end_time": evt.end_time,
                        }
        else:
            session.current_apnea_start = None

        return None

    # ------------------------------------------------------------------
    # 공개 API
    # ------------------------------------------------------------------

    def update(
        self,
        device_id: str,
        breathing_rate: float,
        breathing_amplitude: float,
        motion_index: float,
        timestamp: str,
    ) -> dict:
        """수면 단계 업데이트 및 무호흡 체크.

        Args:
            device_id: 디바이스 식별자.
            breathing_rate: 현재 호흡률 (BPM).
            breathing_amplitude: 호흡 신호 진폭 (무호흡 감지용).
            motion_index: 모션 지수 (CSI 기반).
            timestamp: ISO8601 타임스탬프 문자열.

        Returns:
            현재 단계·무호흡 여부를 포함하는 dict.
        """
        try:
            now_mono = time.monotonic()
            session = self._ensure_session(device_id)

            # 호흡률 이력 갱신
            self._br_history[device_id].append(breathing_rate)
            brv = self._calc_brv(device_id)

            # 수면 단계 분류
            new_stage = self._classify_stage(motion_index, breathing_rate, brv)

            # 단계 전환 기록
            if new_stage != session.current_stage:
                if session.stages:
                    session.stages[-1].end_time = timestamp
                session.stages.append(StageEntry(stage=new_stage, start_time=timestamp))
                session.current_stage = new_stage

            # 무호흡 체크
            apnea_event = self._check_apnea(session, breathing_amplitude, now_mono, timestamp)

            self._last_update[device_id] = now_mono

            result: dict = {
                "device_id": device_id,
                "timestamp": timestamp,
                "stage": session.current_stage,
                "brv": round(brv, 3),
                "breathing_rate": round(breathing_rate, 2),
                "motion_index": round(motion_index, 4),
                "apnea_active": session.current_apnea_start is not None,
                "apnea_event": apnea_event,
            }
            return result

        except Exception as exc:
            return {
                "device_id": device_id,
                "timestamp": timestamp,
                "error": str(exc),
                "stage": "Unknown",
                "apnea_active": False,
                "apnea_event": None,
            }

    def get_status(self, device_id: str) -> dict:
        """디바이스의 현재 수면 상태를 반환합니다.

        Returns:
            stage, apnea_active, session_start, total_apnea_events를 포함하는 dict.
        """
        try:
            if device_id not in self._sessions:
                return {"device_id": device_id, "status": "no_session"}

            session = self._sessions[device_id]
            return {
                "device_id": device_id,
                "current_stage": session.current_stage,
                "session_start": session.start_time,
                "total_apnea_events": len(session.apnea_events),
                "apnea_active": session.current_apnea_start is not None,
                "stage_count": len(session.stages),
            }
        except Exception as exc:
            return {"device_id": device_id, "error": str(exc)}

    def get_report(self, device_id: str) -> dict:
        """수면 세션 보고서를 생성합니다.

        Returns:
            단계별 시간 분포, 무호흡 통계를 포함하는 dict.
        """
        try:
            if device_id not in self._sessions:
                return {"device_id": device_id, "status": "no_session"}

            session = self._sessions[device_id]

            # 단계별 소요 시간 집계 (가장 최근 단계는 현재 시각 기준)
            stage_durations: dict[str, float] = {}
            now_iso = datetime.now(timezone.utc).isoformat()

            for entry in session.stages:
                end = entry.end_time or now_iso
                try:
                    start_dt = datetime.fromisoformat(entry.start_time)
                    end_dt = datetime.fromisoformat(end)
                    duration_min = (end_dt - start_dt).total_seconds() / 60.0
                except Exception:
                    duration_min = 0.0
                stage_durations[entry.stage] = stage_durations.get(entry.stage, 0.0) + duration_min

            total_minutes = sum(stage_durations.values())

            stage_pct: dict[str, float] = {}
            for stage, mins in stage_durations.items():
                stage_pct[stage] = round((mins / total_minutes * 100) if total_minutes > 0 else 0.0, 1)

            # 무호흡 통계
            apnea_durations = [e.duration_seconds for e in session.apnea_events]
            apnea_stats: dict = {
                "count": len(apnea_durations),
                "total_seconds": round(sum(apnea_durations), 2),
                "mean_seconds": round(float(np.mean(apnea_durations)) if apnea_durations else 0.0, 2),
                "max_seconds": round(max(apnea_durations) if apnea_durations else 0.0, 2),
            }

            return {
                "device_id": device_id,
                "session_start": session.start_time,
                "total_minutes": round(total_minutes, 2),
                "stage_durations_min": {k: round(v, 2) for k, v in stage_durations.items()},
                "stage_percentages": stage_pct,
                "apnea_stats": apnea_stats,
                "apnea_events": [
                    {
                        "start_time": e.start_time,
                        "end_time": e.end_time,
                        "duration_seconds": e.duration_seconds,
                    }
                    for e in session.apnea_events
                ],
            }

        except Exception as exc:
            return {"device_id": device_id, "error": str(exc)}


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    monitor = SleepMonitor(apnea_threshold=0.02, apnea_min_duration=3.0)  # 테스트용 3초

    import random

    device = "esp32_01"
    print("=== SleepMonitor 동작 테스트 ===")

    # Wake 구간
    for i in range(5):
        ts = datetime.now(timezone.utc).isoformat()
        result = monitor.update(device, breathing_rate=18.0, breathing_amplitude=0.15,
                                motion_index=0.5, timestamp=ts)
        print(f"[{i}] Wake  → stage={result['stage']}")

    # Deep 구간
    for i in range(10):
        ts = datetime.now(timezone.utc).isoformat()
        br = 12.0 + random.uniform(-0.3, 0.3)
        result = monitor.update(device, breathing_rate=br, breathing_amplitude=0.12,
                                motion_index=0.02, timestamp=ts)
        print(f"[{i}] Deep  → stage={result['stage']}, BRV={result['brv']}")

    # 무호흡 구간 (진폭 0.005로 감소)
    for i in range(5):
        ts = datetime.now(timezone.utc).isoformat()
        result = monitor.update(device, breathing_rate=10.0, breathing_amplitude=0.005,
                                motion_index=0.01, timestamp=ts)
        print(f"[{i}] Apnea → apnea_active={result['apnea_active']}")
        time.sleep(1)

    print("\n--- Status ---")
    print(monitor.get_status(device))
    print("\n--- Report ---")
    report = monitor.get_report(device)
    print(f"  Stage %: {report['stage_percentages']}")
    print(f"  Apnea stats: {report['apnea_stats']}")
