"""
Panic Detector — 반복적 고진폭 모션 기반 긴급 동작 감지.

낙상(단발성 급격한 모션)과 구별:
  - 낙상: motion spike 1회 후 정지
  - 패닉: motion > 임계값 상태가 5초 이상 지속, 또는 2초 내 3회 이상 스파이크
"""

import time
from collections import deque
from datetime import datetime, timezone
from typing import Optional

import numpy as np


class PanicDetector:
    """반복적 고진폭 모션 기반 패닉 상황 감지 클래스.

    낙상과의 구별:
    - 낙상은 단발 스파이크 → FallDetector가 처리.
    - 패닉은 지속·반복 패턴 → 이 클래스가 처리.

    감지 방법 두 가지 (OR 조건):
      1. sustained: motion >= sustained_threshold 가 sustained_duration 초 이상 지속
      2. rapid_spike: spike_window 초 내에 spike_threshold 초과 스파이크가 spike_count_threshold 회 이상
    """

    # 스파이크 윈도우 기본값 (초)
    SPIKE_WINDOW_DEFAULT = 2.0
    SPIKE_COUNT_THRESHOLD = 3

    def __init__(
        self,
        spike_threshold: float = 1.5,
        sustained_threshold: float = 1.0,
        sustained_duration: float = 5.0,
    ) -> None:
        """
        Args:
            spike_threshold: 스파이크 판정 motion_index 임계값 (default 1.5).
            sustained_threshold: 지속 상태 판정 motion_index 임계값 (default 1.0).
            sustained_duration: 지속 상태 판정 최소 시간(초) (default 5.0).
        """
        self.spike_threshold = spike_threshold
        self.sustained_threshold = sustained_threshold
        self.sustained_duration = sustained_duration

        # 디바이스별 상태
        self._sustained_start: dict[str, Optional[float]] = {}  # monotonic
        self._sustained_reported: dict[str, bool] = {}          # 동일 이벤트 중복 보고 방지
        # 스파이크 타임스탬프 이력 (monotonic)
        self._spike_times: dict[str, deque[float]] = {}

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------

    def _ensure_device(self, device_id: str) -> None:
        if device_id not in self._sustained_start:
            self._sustained_start[device_id] = None
            self._sustained_reported[device_id] = False
            self._spike_times[device_id] = deque()

    def _prune_spike_times(self, device_id: str, now: float) -> None:
        """SPIKE_WINDOW_DEFAULT 이전의 스파이크 기록을 제거합니다."""
        q = self._spike_times[device_id]
        while q and (now - q[0]) > self.SPIKE_WINDOW_DEFAULT:
            q.popleft()

    def _make_event(
        self,
        device_id: str,
        reason: str,
        motion_index: float,
        timestamp: str,
        extra: Optional[dict] = None,
    ) -> dict:
        event: dict = {
            "type": "panic",
            "device_id": device_id,
            "reason": reason,
            "motion_index": round(motion_index, 4),
            "timestamp": timestamp,
            "severity": "critical",
        }
        if extra:
            event.update(extra)
        return event

    # ------------------------------------------------------------------
    # 공개 API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        device_id: str,
        motion_index: float,
        timestamp: str,
    ) -> Optional[dict]:
        """패닉 이벤트 평가.

        Args:
            device_id: 디바이스 식별자.
            motion_index: 현재 모션 지수.
            timestamp: ISO8601 타임스탬프.

        Returns:
            패닉 감지 시 이벤트 dict 반환, 아니면 None.
        """
        try:
            self._ensure_device(device_id)
            now = time.monotonic()

            # ----- 1. sustained 패턴 감지 -----
            if motion_index >= self.sustained_threshold:
                if self._sustained_start[device_id] is None:
                    self._sustained_start[device_id] = now
                    self._sustained_reported[device_id] = False
                else:
                    elapsed = now - self._sustained_start[device_id]
                    if elapsed >= self.sustained_duration and not self._sustained_reported[device_id]:
                        self._sustained_reported[device_id] = True
                        return self._make_event(
                            device_id, "sustained_high_motion", motion_index, timestamp,
                            {"duration_seconds": round(elapsed, 2)},
                        )
            else:
                # 지속 상태 리셋
                self._sustained_start[device_id] = None
                self._sustained_reported[device_id] = False

            # ----- 2. rapid_spike 패턴 감지 -----
            if motion_index >= self.spike_threshold:
                q = self._spike_times[device_id]
                self._prune_spike_times(device_id, now)
                q.append(now)

                if len(q) >= self.SPIKE_COUNT_THRESHOLD:
                    # 이벤트 발생 후 큐 클리어 (중복 방지)
                    spike_count = len(q)
                    q.clear()
                    return self._make_event(
                        device_id, "rapid_spikes", motion_index, timestamp,
                        {
                            "spike_count": spike_count,
                            "window_seconds": self.SPIKE_WINDOW_DEFAULT,
                        },
                    )
            else:
                # spike_threshold 미만이면 윈도우 외 항목만 정리
                self._prune_spike_times(device_id, now)

            return None

        except Exception as exc:
            # 모듈 오류가 메인 루프를 죽이지 않도록 None 반환
            return None

    def reset(self, device_id: str) -> None:
        """디바이스 상태를 초기화합니다."""
        try:
            self._sustained_start[device_id] = None
            self._sustained_reported[device_id] = False
            if device_id in self._spike_times:
                self._spike_times[device_id].clear()
        except Exception:
            pass

    def get_status(self, device_id: str) -> dict:
        """디바이스의 현재 감지 상태를 반환합니다.

        Returns:
            sustained_active, spike_count_in_window를 포함하는 dict.
        """
        try:
            self._ensure_device(device_id)
            now = time.monotonic()
            self._prune_spike_times(device_id, now)

            sustained_start = self._sustained_start[device_id]
            return {
                "device_id": device_id,
                "sustained_active": sustained_start is not None,
                "sustained_elapsed_seconds": round(now - sustained_start, 2) if sustained_start else 0.0,
                "spike_count_in_window": len(self._spike_times[device_id]),
            }
        except Exception as exc:
            return {"device_id": device_id, "error": str(exc)}


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    detector = PanicDetector(
        spike_threshold=1.5,
        sustained_threshold=1.0,
        sustained_duration=3.0,  # 테스트용 3초
    )
    device = "esp32_01"
    now_iso = lambda: datetime.now(timezone.utc).isoformat()

    print("=== PanicDetector 동작 테스트 ===")

    # rapid_spike 시뮬레이션
    print("\n[rapid_spike 시나리오]")
    for i in range(5):
        result = detector.evaluate(device, motion_index=2.0, timestamp=now_iso())
        if result:
            print(f"  이벤트 감지! reason={result['reason']}, count={result.get('spike_count')}")
        time.sleep(0.3)

    detector.reset(device)

    # sustained 시뮬레이션
    print("\n[sustained 시나리오]")
    start = time.monotonic()
    event_fired = False
    while time.monotonic() - start < 5.0:
        result = detector.evaluate(device, motion_index=1.2, timestamp=now_iso())
        if result and not event_fired:
            event_fired = True
            print(f"  이벤트 감지! reason={result['reason']}, duration={result.get('duration_seconds')}s")
        time.sleep(0.5)

    print("\n--- Status ---")
    print(detector.get_status(device))
