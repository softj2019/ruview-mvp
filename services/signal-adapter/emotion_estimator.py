"""
Emotion Estimator — 바이탈 + 활동 조합 기반 감정 상태 추정.

3가지 상태:
  - calm:     HR 정상(60-80), HRV SDNN > 30ms, motion_index < 0.1
  - stressed: HR 상승(> 80), HRV SDNN < 20ms, motion_index < 0.2
  - agitated: motion_index > 0.5 + HR 상승, 또는 반복적 고진폭 모션
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import numpy as np


@dataclass
class _DeviceState:
    """디바이스별 평활화 상태."""
    # EMA 평활값
    hr_ema: float = 70.0
    sdnn_ema: float = 35.0
    motion_ema: float = 0.0
    br_ema: float = 15.0
    current_emotion: str = "calm"
    confidence: float = 0.5
    # 반복 고진폭 모션 카운터 (agitated 감지용)
    high_motion_streak: int = 0


class EmotionEstimator:
    """바이탈 + 활동 조합 기반 감정 상태 추정 클래스.

    Exponential Moving Average(EMA)로 입력값을 평활화하여
    순간 잡음에 강인한 감정 분류를 제공합니다.
    """

    # EMA 평활화 계수
    EMA_ALPHA = 0.3

    # 감정 분류 임계값
    HR_CALM_MAX = 80.0
    HR_CALM_MIN = 60.0
    HR_STRESSED_MIN = 80.0

    SDNN_CALM_MIN = 30.0        # ms
    SDNN_STRESSED_MAX = 20.0    # ms

    MOTION_CALM_MAX = 0.1
    MOTION_STRESSED_MAX = 0.2
    MOTION_AGITATED_MIN = 0.5

    HIGH_MOTION_STREAK_THRESHOLD = 3  # 연속 N회 이상 고진폭 → agitated

    def __init__(self) -> None:
        self._states: dict[str, _DeviceState] = {}

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------

    def _ensure_state(self, device_id: str) -> _DeviceState:
        if device_id not in self._states:
            self._states[device_id] = _DeviceState()
        return self._states[device_id]

    @staticmethod
    def _ema(prev: float, new: float, alpha: float) -> float:
        return alpha * new + (1.0 - alpha) * prev

    def _classify(self, state: _DeviceState) -> tuple[str, float]:
        """평활화된 값으로 감정 분류 및 confidence 계산."""
        hr = state.hr_ema
        sdnn = state.sdnn_ema
        motion = state.motion_ema

        # agitated 우선 판정
        if motion >= self.MOTION_AGITATED_MIN and hr > self.HR_STRESSED_MIN:
            # confidence: motion 초과 마진 + HR 초과 마진
            conf = min(
                0.5 + (motion - self.MOTION_AGITATED_MIN) * 0.5
                + (hr - self.HR_STRESSED_MIN) / 40.0,
                1.0,
            )
            return "agitated", round(conf, 4)

        if state.high_motion_streak >= self.HIGH_MOTION_STREAK_THRESHOLD:
            return "agitated", 0.75

        # stressed 판정
        stressed_score = 0.0
        if hr > self.HR_STRESSED_MIN:
            stressed_score += min((hr - self.HR_STRESSED_MIN) / 40.0, 0.4)
        if sdnn < self.SDNN_STRESSED_MAX:
            stressed_score += min((self.SDNN_STRESSED_MAX - sdnn) / self.SDNN_STRESSED_MAX, 0.4)
        if motion < self.MOTION_STRESSED_MAX:
            stressed_score += 0.2

        if stressed_score >= 0.5:
            return "stressed", round(min(stressed_score, 1.0), 4)

        # calm 판정
        calm_score = 0.0
        if self.HR_CALM_MIN <= hr <= self.HR_CALM_MAX:
            # 마진: 중앙값(70)에 가까울수록 높은 confidence
            calm_score += 0.35 * (1.0 - abs(hr - 70.0) / 10.0)
        if sdnn >= self.SDNN_CALM_MIN:
            calm_score += min((sdnn - self.SDNN_CALM_MIN) / 30.0, 0.35)
        if motion < self.MOTION_CALM_MAX:
            calm_score += 0.3 * (1.0 - motion / self.MOTION_CALM_MAX)

        if calm_score >= 0.3:
            return "calm", round(min(calm_score, 1.0), 4)

        # 기본 Light 상태 (Light는 별도 레이블 없이 calm으로 분류)
        return "calm", round(max(calm_score, 0.1), 4)

    # ------------------------------------------------------------------
    # 공개 API
    # ------------------------------------------------------------------

    def update(
        self,
        device_id: str,
        heart_rate: float,
        sdnn: float,
        motion_index: float,
        breathing_rate: float,
    ) -> dict:
        """감정 상태를 업데이트하고 현재 추정 결과를 반환합니다.

        Args:
            device_id: 디바이스 식별자.
            heart_rate: 심박수 (BPM).
            sdnn: HRV SDNN (ms).
            motion_index: CSI 모션 지수.
            breathing_rate: 호흡률 (BPM).

        Returns:
            emotion, confidence, 평활화된 바이탈 값을 포함하는 dict.
        """
        try:
            state = self._ensure_state(device_id)
            alpha = self.EMA_ALPHA

            # EMA 평활화
            state.hr_ema = self._ema(state.hr_ema, heart_rate, alpha)
            state.sdnn_ema = self._ema(state.sdnn_ema, sdnn, alpha)
            state.motion_ema = self._ema(state.motion_ema, motion_index, alpha)
            state.br_ema = self._ema(state.br_ema, breathing_rate, alpha)

            # 반복 고진폭 모션 추적
            if motion_index >= self.MOTION_AGITATED_MIN:
                state.high_motion_streak += 1
            else:
                state.high_motion_streak = 0

            emotion, confidence = self._classify(state)
            state.current_emotion = emotion
            state.confidence = confidence

            return {
                "device_id": device_id,
                "emotion": emotion,
                "confidence": confidence,
                "smoothed": {
                    "heart_rate": round(state.hr_ema, 2),
                    "sdnn": round(state.sdnn_ema, 2),
                    "motion_index": round(state.motion_ema, 4),
                    "breathing_rate": round(state.br_ema, 2),
                },
                "high_motion_streak": state.high_motion_streak,
            }

        except Exception as exc:
            return {
                "device_id": device_id,
                "emotion": "unknown",
                "confidence": 0.0,
                "error": str(exc),
            }

    def get_state(self, device_id: str) -> dict:
        """디바이스의 현재 감정 상태를 반환합니다.

        Returns:
            emotion, confidence, 평활화된 바이탈 값을 포함하는 dict.
        """
        try:
            if device_id not in self._states:
                return {"device_id": device_id, "status": "no_data"}

            state = self._states[device_id]
            return {
                "device_id": device_id,
                "emotion": state.current_emotion,
                "confidence": state.confidence,
                "smoothed": {
                    "heart_rate": round(state.hr_ema, 2),
                    "sdnn": round(state.sdnn_ema, 2),
                    "motion_index": round(state.motion_ema, 4),
                    "breathing_rate": round(state.br_ema, 2),
                },
            }
        except Exception as exc:
            return {"device_id": device_id, "error": str(exc)}


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    estimator = EmotionEstimator()
    device = "esp32_01"

    print("=== EmotionEstimator 동작 테스트 ===")

    scenarios = [
        ("Calm 시나리오",   {"heart_rate": 68.0, "sdnn": 45.0, "motion_index": 0.05, "breathing_rate": 14.0}),
        ("Stressed 시나리오", {"heart_rate": 92.0, "sdnn": 15.0, "motion_index": 0.15, "breathing_rate": 20.0}),
        ("Agitated 시나리오", {"heart_rate": 110.0, "sdnn": 10.0, "motion_index": 0.8, "breathing_rate": 25.0}),
    ]

    for label, params in scenarios:
        # 10 스텝 적용해 EMA 수렴
        for _ in range(10):
            result = estimator.update(device, **params)
        print(f"  [{label}] emotion={result['emotion']}, confidence={result['confidence']}")
        print(f"    smoothed HR={result['smoothed']['heart_rate']}, SDNN={result['smoothed']['sdnn']}")

    print("\n--- get_state ---")
    print(estimator.get_state(device))
