# MERIDIAN — Modal Intelligence Dynamic Auto-Switch
# 가용 모달리티(CSI, Camera, mmWave, Multistatic)를 신호 품질 기반으로 자동 전환

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ModalityScore:
    name: str
    score: float = 0.0          # 0.0 ~ 1.0
    available: bool = False
    last_updated: float = 0.0   # monotonic timestamp


# 동점 시 우선순위 (낮을수록 높은 우선순위)
_PRIORITY: dict[str, int] = {
    "multistatic": 0,
    "csi": 1,
    "rf_tomography": 2,
    "camera": 3,
}

# 모달리티가 유효하다고 간주하는 최대 경과 시간 (초)
_STALENESS_TIMEOUT = 5.0


class MeridianController:
    """모달리티 품질 점수를 추적하고 최적 모달리티를 자동 선택한다."""

    def __init__(self) -> None:
        self._modalities: dict[str, ModalityScore] = {
            name: ModalityScore(name=name)
            for name in ("csi", "camera", "multistatic", "rf_tomography")
        }

    # ------------------------------------------------------------------ #
    # 모달리티별 업데이트                                                   #
    # ------------------------------------------------------------------ #

    def update_csi(self, motion_index: float, coherence_ratio: float) -> None:
        """CSI 품질 점수 업데이트.

        score = motion_index * coherence_ratio (0~1 클리핑)
        """
        score = float(motion_index) * float(coherence_ratio)
        self._set(
            "csi",
            score=max(0.0, min(1.0, score)),
            available=True,
        )

    def update_camera(self, person_count: int, confidence: float) -> None:
        """카메라 품질 점수 업데이트.

        사람이 감지되면 confidence, 아니면 0.3(대기 상태 점수).
        """
        if int(person_count) > 0:
            score = min(1.0, float(confidence))
        else:
            score = 0.3
        self._set("camera", score=score, available=True)

    def update_multistatic(
        self,
        spatial_resolution_gain: float,
        link_count: int,
    ) -> None:
        """멀티스태틱 품질 점수 업데이트.

        score = min(1.0, spatial_resolution_gain / 3.0)
                * min(1.0, link_count / 6.0)
        """
        gain_norm = min(1.0, float(spatial_resolution_gain) / 3.0)
        link_norm = min(1.0, int(link_count) / 6.0)
        score = gain_norm * link_norm
        self._set("multistatic", score=score, available=True)

    def update_rf_tomography(
        self,
        occupied_cells: int,
        max_value: float,
    ) -> None:
        """RF 토모그래피 품질 점수 업데이트.

        score = min(1.0, occupied_cells / 50) * min(1.0, max_value)
        """
        cell_norm = min(1.0, int(occupied_cells) / 50.0)
        val_norm = min(1.0, float(max_value))
        score = cell_norm * val_norm
        self._set("rf_tomography", score=score, available=True)

    # ------------------------------------------------------------------ #
    # 조회                                                                  #
    # ------------------------------------------------------------------ #

    def get_active_modality(self) -> str:
        """5초 이내 업데이트된 모달리티 중 최고 점수를 반환.

        동점 시: multistatic > csi > rf_tomography > camera 우선순위.
        """
        now = time.monotonic()
        candidates = [
            m for m in self._modalities.values()
            if m.available and (now - m.last_updated) <= _STALENESS_TIMEOUT
        ]
        if not candidates:
            return "csi"  # 기본값

        best = max(
            candidates,
            key=lambda m: (round(m.score, 6), -_PRIORITY.get(m.name, 99)),
        )
        return best.name

    def get_status(self) -> dict:
        """전체 모달리티 상태 + active + recommendation 반환."""
        now = time.monotonic()
        active = self.get_active_modality()

        modalities_out = {}
        for name, m in self._modalities.items():
            age = now - m.last_updated if m.last_updated > 0 else None
            fresh = age is not None and age <= _STALENESS_TIMEOUT
            modalities_out[name] = {
                "score": round(m.score, 4),
                "available": m.available,
                "fresh": fresh,
                "age_seconds": round(age, 2) if age is not None else None,
            }

        # recommendation: 가장 높은 점수의 fresh 모달리티
        active_score = self._modalities[active].score if active in self._modalities else 0.0
        if active_score >= 0.7:
            recommendation = f"Use {active} (high confidence)"
        elif active_score >= 0.4:
            recommendation = f"Use {active} (moderate confidence — consider fusion)"
        else:
            recommendation = "Low confidence on all modalities — check sensor status"

        return {
            "active": active,
            "modalities": modalities_out,
            "recommendation": recommendation,
        }

    def get_fusion_weights(self) -> dict[str, float]:
        """각 모달리티 점수를 합산 1.0으로 정규화한 가중치 반환.

        점수 합이 0이면 가용 모달리티 균등 분배, 없으면 csi=1.0.
        """
        now = time.monotonic()
        scores: dict[str, float] = {}
        for name, m in self._modalities.items():
            age = now - m.last_updated if m.last_updated > 0 else None
            fresh = age is not None and age <= _STALENESS_TIMEOUT
            if m.available and fresh:
                scores[name] = max(0.0, m.score)

        total = sum(scores.values())
        if total <= 0.0:
            if scores:
                # 점수가 모두 0이지만 가용 모달리티가 있으면 균등 분배
                n = len(scores)
                return {k: round(1.0 / n, 6) for k in scores}
            # 아무것도 없으면 csi 단독
            return {"csi": 1.0}

        return {k: round(v / total, 6) for k, v in scores.items()}

    # ------------------------------------------------------------------ #
    # 내부 헬퍼                                                             #
    # ------------------------------------------------------------------ #

    def _set(self, name: str, score: float, available: bool) -> None:
        m = self._modalities[name]
        m.score = score
        m.available = available
        m.last_updated = time.monotonic()
