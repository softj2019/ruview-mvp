"""
Gait Analyzer — 도플러 속도 프로파일 기반 보행 패턴 분석.

분석 지표:
  - cadence: 분당 걸음 수 (도플러 피크 주기에서 추출)
  - asymmetry: 좌우 비대칭 비율 (연속 피크 간 시간 차이)
  - variability: 보행 속도 변동 계수
  - fall_risk_score: 낙상 위험도 (cadence < 80, variability > 0.3, asymmetry > 0.2)
"""

from collections import deque
from datetime import datetime, timezone
from typing import Optional

import numpy as np

# scipy.signal.find_peaks 사용 시도, 없으면 numpy fallback
try:
    from scipy.signal import find_peaks as _scipy_find_peaks
    _SCIPY_AVAILABLE = True
except ImportError:
    _SCIPY_AVAILABLE = False


def _numpy_find_peaks(arr: np.ndarray, height: float = 0.0, distance: int = 1) -> tuple[np.ndarray, dict]:
    """scipy 없을 경우 사용하는 단순 극댓값 감지 fallback."""
    peaks = []
    n = len(arr)
    for i in range(1, n - 1):
        if arr[i] > arr[i - 1] and arr[i] > arr[i + 1] and arr[i] >= height:
            if not peaks or (i - peaks[-1]) >= distance:
                peaks.append(i)
    return np.array(peaks, dtype=int), {}


def _find_peaks(arr: np.ndarray, height: float = 0.0, distance: int = 1) -> tuple[np.ndarray, dict]:
    if _SCIPY_AVAILABLE:
        return _scipy_find_peaks(arr, height=height, distance=distance)
    return _numpy_find_peaks(arr, height=height, distance=distance)


class GaitAnalyzer:
    """도플러 속도 프로파일로 보행 패턴을 분석합니다.

    ProcessedCSI의 doppler_velocity 및 motion_index를 입력으로 받아
    cadence, asymmetry, variability, fall_risk_score를 계산합니다.
    """

    # 낙상 위험 임계값
    CADENCE_RISK_THRESHOLD = 80.0       # steps/min 미만 시 위험
    VARIABILITY_RISK_THRESHOLD = 0.3    # 변동 계수 초과 시 위험
    ASYMMETRY_RISK_THRESHOLD = 0.2      # 비대칭 비율 초과 시 위험

    # 피크 감지 파라미터
    PEAK_HEIGHT_FACTOR = 0.3            # 전체 범위의 30% 이상을 피크로 인정
    PEAK_MIN_DISTANCE = 3               # 최소 3샘플 간격

    def __init__(self, history_size: int = 100) -> None:
        """
        Args:
            history_size: 디바이스별 속도 이력 최대 크기 (default 100).
        """
        self.history_size = history_size
        # 디바이스별 속도 이력: (velocity, timestamp_mono)
        self._velocity_history: dict[str, deque[tuple[float, float]]] = {}
        self._analysis_cache: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------

    def _ensure_history(self, device_id: str) -> deque[tuple[float, float]]:
        if device_id not in self._velocity_history:
            self._velocity_history[device_id] = deque(maxlen=self.history_size)
        return self._velocity_history[device_id]

    def _compute_cadence_and_asymmetry(
        self, velocities: np.ndarray, times: np.ndarray
    ) -> tuple[float, float]:
        """피크 주기에서 cadence와 asymmetry를 계산합니다."""
        if len(velocities) < 6:
            return 0.0, 0.0

        v_range = float(np.max(velocities) - np.min(velocities))
        height = float(np.min(velocities)) + self.PEAK_HEIGHT_FACTOR * v_range

        peaks, _ = _find_peaks(velocities, height=height, distance=self.PEAK_MIN_DISTANCE)

        if len(peaks) < 2:
            return 0.0, 0.0

        # 피크 간 시간 간격 (초)
        intervals = np.diff(times[peaks])
        if len(intervals) == 0 or np.mean(intervals) == 0:
            return 0.0, 0.0

        mean_interval = float(np.mean(intervals))
        cadence = 60.0 / mean_interval  # steps/min

        # asymmetry: 연속 피크 간격의 변동 (홀수/짝수 차이)
        if len(intervals) >= 2:
            even_intervals = intervals[0::2]
            odd_intervals = intervals[1::2]
            min_len = min(len(even_intervals), len(odd_intervals))
            if min_len > 0:
                diff = np.abs(even_intervals[:min_len] - odd_intervals[:min_len])
                asymmetry = float(np.mean(diff) / mean_interval)
            else:
                asymmetry = 0.0
        else:
            asymmetry = 0.0

        return round(cadence, 2), round(min(asymmetry, 1.0), 4)

    def _compute_variability(self, velocities: np.ndarray) -> float:
        """속도 변동 계수(CV = std/mean)를 계산합니다."""
        if len(velocities) < 2:
            return 0.0
        mean_v = float(np.mean(np.abs(velocities)))
        if mean_v < 1e-6:
            return 0.0
        return round(float(np.std(velocities)) / mean_v, 4)

    def _compute_fall_risk(
        self, cadence: float, asymmetry: float, variability: float
    ) -> float:
        """cadence, asymmetry, variability 가중합으로 낙상 위험도를 계산합니다 (0-1).

        각 지표의 기여도는 1/3씩 동일합니다.
        """
        # cadence 기여도: cadence < 80 이면 위험 (낮을수록 위험)
        if cadence <= 0:
            cadence_score = 1.0
        elif cadence >= self.CADENCE_RISK_THRESHOLD:
            cadence_score = 0.0
        else:
            cadence_score = 1.0 - (cadence / self.CADENCE_RISK_THRESHOLD)

        # variability 기여도
        variability_score = min(variability / self.VARIABILITY_RISK_THRESHOLD, 1.0)

        # asymmetry 기여도
        asymmetry_score = min(asymmetry / self.ASYMMETRY_RISK_THRESHOLD, 1.0)

        score = (cadence_score + variability_score + asymmetry_score) / 3.0
        return round(float(score), 4)

    # ------------------------------------------------------------------
    # 공개 API
    # ------------------------------------------------------------------

    def update(
        self,
        device_id: str,
        motion_index: float,
        velocity: float,
        timestamp: str,
    ) -> dict:
        """속도 샘플을 이력에 추가하고 최신 분석 결과를 반환합니다.

        Args:
            device_id: 디바이스 식별자.
            motion_index: CSI 모션 지수 (보행 중인지 판단용).
            velocity: 도플러 추정 속도 (m/s).
            timestamp: ISO8601 타임스탬프.

        Returns:
            cadence, asymmetry, variability, fall_risk_score를 포함하는 dict.
        """
        try:
            import time
            history = self._ensure_history(device_id)
            history.append((velocity, time.monotonic()))

            analysis = self.get_analysis(device_id)
            analysis["timestamp"] = timestamp
            analysis["motion_index"] = round(motion_index, 4)
            return analysis

        except Exception as exc:
            return {
                "device_id": device_id,
                "timestamp": timestamp,
                "error": str(exc),
                "cadence": 0.0,
                "asymmetry": 0.0,
                "variability": 0.0,
                "fall_risk_score": 0.0,
            }

    def get_analysis(self, device_id: str) -> dict:
        """현재 이력 기반 보행 분석 결과를 반환합니다.

        Returns:
            cadence, asymmetry, variability, fall_risk_score, sample_count를 포함하는 dict.
        """
        try:
            history = self._velocity_history.get(device_id)
            if not history or len(history) < 6:
                return {
                    "device_id": device_id,
                    "cadence": 0.0,
                    "asymmetry": 0.0,
                    "variability": 0.0,
                    "fall_risk_score": 0.0,
                    "sample_count": len(history) if history else 0,
                }

            vels = np.array([v for v, _ in history], dtype=np.float64)
            times = np.array([t for _, t in history], dtype=np.float64)

            cadence, asymmetry = self._compute_cadence_and_asymmetry(vels, times)
            variability = self._compute_variability(vels)
            fall_risk = self._compute_fall_risk(cadence, asymmetry, variability)

            result = {
                "device_id": device_id,
                "cadence": cadence,
                "asymmetry": asymmetry,
                "variability": variability,
                "fall_risk_score": fall_risk,
                "sample_count": len(history),
            }
            self._analysis_cache[device_id] = result
            return result

        except Exception as exc:
            return {"device_id": device_id, "error": str(exc), "cadence": 0.0,
                    "asymmetry": 0.0, "variability": 0.0, "fall_risk_score": 0.0}


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import math

    analyzer = GaitAnalyzer(history_size=60)
    device = "esp32_02"

    print("=== GaitAnalyzer 동작 테스트 ===")
    # 정상 보행 시뮬레이션 (1 Hz 걸음 주기 ~ cadence 60)
    for i in range(40):
        # 사인파로 걸음 모션 시뮬레이션
        velocity = 1.0 + 0.8 * math.sin(2 * math.pi * i / 10)
        ts = datetime.now(timezone.utc).isoformat()
        result = analyzer.update(device, motion_index=0.6, velocity=velocity, timestamp=ts)

    print(f"  cadence      : {result['cadence']} steps/min")
    print(f"  asymmetry    : {result['asymmetry']}")
    print(f"  variability  : {result['variability']}")
    print(f"  fall_risk    : {result['fall_risk_score']}")

    # 불규칙 보행 (고위험)
    device2 = "esp32_03"
    import random
    for i in range(40):
        velocity = random.uniform(0.1, 3.0)
        ts = datetime.now(timezone.utc).isoformat()
        result2 = analyzer.update(device2, motion_index=0.4, velocity=velocity, timestamp=ts)

    print(f"\n  [불규칙] fall_risk={result2['fall_risk_score']}, variability={result2['variability']}")
