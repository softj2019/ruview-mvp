"""
PresenceClassifier — RSSI 기반 재실/움직임 3단계 분류 (Phase 3-9)

rule-based 분류기:
  ABSENT        — 사람 없음
  PRESENT_STILL — 사람 있음, 정적
  ACTIVE        — 사람 있음, 움직임 감지

슬라이딩 윈도우 분산 기반 분류 + 히스테리시스로 잦은 전환 방지.
"""
from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Deque, List, Optional

from .feature_extractor import RssiFeatureExtractor, RssiFeatures

logger = logging.getLogger(__name__)


class MotionLevel(Enum):
    """분류된 움직임 상태."""
    ABSENT = "absent"
    PRESENT_STILL = "present_still"
    ACTIVE = "active"


@dataclass
class SensingResult:
    """재실/움직임 분류기 출력."""
    motion_level: MotionLevel
    confidence: float            # 0.0 ~ 1.0
    presence_detected: bool
    rssi_variance: float
    motion_band_energy: float
    breathing_band_energy: float
    n_change_points: int
    details: str = ""


class PresenceClassifier:
    """
    RSSI 특징 기반 재실/움직임 3단계 분류기.

    분류 규칙
    ---------
    1. 재실 판정: RSSI 분산 >= presence_variance_threshold
    2. 움직임 단계:
       - ABSENT        : 분산 < 임계값
       - ACTIVE        : 분산 >= 임계값 AND 운동 대역 에너지 >= motion_energy_threshold
       - PRESENT_STILL : 분산 >= 임계값 AND 운동 에너지 낮음

    히스테리시스
    -----------
    history_size 개의 이전 결과를 저장하고, 최근 majority vote로
    잦은 상태 전환을 방지합니다.

    Parameters
    ----------
    presence_variance_threshold : float
        재실 판정 최소 RSSI 분산 (dBm^2). 기본 0.5.
    motion_energy_threshold : float
        ACTIVE 판정 최소 운동 대역 에너지. 기본 0.1.
    history_size : int
        히스테리시스 윈도우 크기 (과거 결과 수). 기본 5.
    hysteresis_ratio : float
        상태 유지를 위한 majority 비율 임계값 (0~1). 기본 0.6.
    """

    def __init__(
        self,
        presence_variance_threshold: float = 0.5,
        motion_energy_threshold: float = 0.1,
        history_size: int = 5,
        hysteresis_ratio: float = 0.6,
    ) -> None:
        self._var_thresh = presence_variance_threshold
        self._motion_thresh = motion_energy_threshold
        self._history_size = max(1, history_size)
        self._hysteresis_ratio = hysteresis_ratio

        # 디바이스별 히스테리시스 이력
        self._level_history: dict[str, Deque[MotionLevel]] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def presence_variance_threshold(self) -> float:
        return self._var_thresh

    @property
    def motion_energy_threshold(self) -> float:
        return self._motion_thresh

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(
        self,
        features: RssiFeatures,
        device_id: str = "default",
        other_results: Optional[List[SensingResult]] = None,
    ) -> SensingResult:
        """
        RSSI 특징에서 재실/움직임을 분류합니다.

        Parameters
        ----------
        features : RssiFeatures
            추출된 RSSI 특징.
        device_id : str
            히스테리시스 이력을 관리할 디바이스 ID.
        other_results : list of SensingResult, optional
            다른 수신기 결과 (교차 수신기 합의에 활용).

        Returns
        -------
        SensingResult
        """
        variance = features.variance
        motion_energy = features.motion_band_power
        breathing_energy = features.breathing_band_power

        # 1차 분류
        raw_level = self._classify_raw(variance, motion_energy)

        # 히스테리시스 적용
        level = self._apply_hysteresis(device_id, raw_level)

        presence = (level != MotionLevel.ABSENT)

        confidence = self._compute_confidence(
            variance, motion_energy, breathing_energy, level, other_results
        )

        details = (
            f"var={variance:.4f} (thresh={self._var_thresh}), "
            f"motion_energy={motion_energy:.4f} (thresh={self._motion_thresh}), "
            f"breathing_energy={breathing_energy:.4f}, "
            f"change_points={features.n_change_points}, "
            f"raw={raw_level.value}, final={level.value}"
        )

        return SensingResult(
            motion_level=level,
            confidence=confidence,
            presence_detected=presence,
            rssi_variance=variance,
            motion_band_energy=motion_energy,
            breathing_band_energy=breathing_energy,
            n_change_points=features.n_change_points,
            details=details,
        )

    def classify_from_array(
        self,
        rssi_array,
        device_id: str = "default",
        sample_rate_hz: float = 10.0,
    ) -> SensingResult:
        """
        numpy 배열에서 직접 분류합니다 (편의 메서드).

        Parameters
        ----------
        rssi_array : array-like
            1-D RSSI 시계열 (dBm).
        device_id : str
        sample_rate_hz : float
        """
        import numpy as np
        arr = np.asarray(rssi_array, dtype=np.float64)
        extractor = RssiFeatureExtractor(sample_rate_hz=sample_rate_hz)
        features = extractor.extract_from_array(arr)
        return self.classify(features, device_id=device_id)

    def reset_history(self, device_id: Optional[str] = None) -> None:
        """히스테리시스 이력을 초기화합니다."""
        if device_id is None:
            self._level_history.clear()
        elif device_id in self._level_history:
            self._level_history[device_id].clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _classify_raw(self, variance: float, motion_energy: float) -> MotionLevel:
        """히스테리시스 없이 즉시 분류합니다."""
        if variance < self._var_thresh:
            return MotionLevel.ABSENT
        if motion_energy >= self._motion_thresh:
            return MotionLevel.ACTIVE
        return MotionLevel.PRESENT_STILL

    def _apply_hysteresis(self, device_id: str, raw_level: MotionLevel) -> MotionLevel:
        """
        이전 분류 이력을 이용해 잦은 전환을 방지합니다.

        히스테리시스 윈도우가 채워지기 전까지는 raw_level을 그대로 반환합니다.
        """
        if device_id not in self._level_history:
            self._level_history[device_id] = deque(maxlen=self._history_size)

        history = self._level_history[device_id]
        history.append(raw_level)

        if len(history) < self._history_size:
            return raw_level

        # majority vote
        counts: dict[MotionLevel, int] = {}
        for lvl in history:
            counts[lvl] = counts.get(lvl, 0) + 1

        best = max(counts, key=lambda k: counts[k])
        if counts[best] / self._history_size >= self._hysteresis_ratio:
            return best
        return raw_level

    def _compute_confidence(
        self,
        variance: float,
        motion_energy: float,
        breathing_energy: float,
        level: MotionLevel,
        other_results: Optional[List[SensingResult]],
    ) -> float:
        """
        신뢰도 점수 [0, 1] 계산.

        구성:
          - 기본 (60%): 분산이 임계값 대비 얼마나 명확히 초과/미달하는지
          - 스펙트럼 (20%): 해당 대역 에너지 강도
          - 수신기 합의 (20%): 교차 수신기 일치율
        """
        # 기본 신뢰도
        if level == MotionLevel.ABSENT:
            base = max(0.0, 1.0 - variance / self._var_thresh) if self._var_thresh > 0 else 1.0
        else:
            ratio = variance / self._var_thresh if self._var_thresh > 0 else 10.0
            base = min(1.0, ratio)

        # 스펙트럼 신뢰도
        if level == MotionLevel.ACTIVE:
            spectral = min(1.0, motion_energy / max(self._motion_thresh, 1e-12))
        elif level == MotionLevel.PRESENT_STILL:
            spectral = min(1.0, breathing_energy / max(self._motion_thresh, 1e-12))
        else:
            spectral = 1.0

        # 수신기 합의
        agreement = 1.0
        if other_results:
            same = sum(1 for r in other_results if r.motion_level == level)
            agreement = (same + 1) / (len(other_results) + 1)

        confidence = 0.6 * base + 0.2 * spectral + 0.2 * agreement
        return max(0.0, min(1.0, confidence))
