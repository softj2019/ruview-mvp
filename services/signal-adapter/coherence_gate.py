"""
Coherence Gate — 서브캐리어 간 magnitude-squared coherence 기반 신호 품질 필터링.

역할: 직접 경로(LoS) 반사 신호만 선택적 통과, 멀티패스 잡음 제거.
삽입 위치: Hampel 필터 이후, FFT 이전 (csi_processor.py 파이프라인)

Magnitude-Squared Coherence (MSC):
  C_xy(f) = |P_xy(f)|² / (P_xx(f) * P_yy(f))
  MSC ∈ [0, 1] — 1에 가까울수록 두 신호가 선형 관계
"""
import numpy as np
from collections import deque


class CoherenceGate:
    """서브캐리어 쌍의 MSC 계산으로 비일관 서브캐리어 마스킹."""

    def __init__(self, window_size: int = 20, msc_threshold: float = 0.5,
                 n_reference: int = 4):
        """
        window_size: MSC 계산용 슬라이딩 윈도우 크기
        msc_threshold: 이 값 이하인 서브캐리어를 마스킹
        n_reference: 기준 서브캐리어 수 (중간 n개를 기준으로 사용)
        """
        self.window_size = window_size
        self.msc_threshold = msc_threshold
        self.n_reference = n_reference
        self._history: deque[np.ndarray] = deque(maxlen=window_size)

    def update(self, amplitudes: list[float]) -> np.ndarray:
        """새 프레임 추가. 현재 마스크 반환 (True = 유효)."""
        arr = np.array(amplitudes, dtype=np.float64)
        self._history.append(arr)
        if len(self._history) < 4:
            return np.ones(len(arr), dtype=bool)
        return self._compute_mask()

    def _compute_mask(self) -> np.ndarray:
        """히스토리 기반 MSC 마스크 계산."""
        data = np.array(self._history)  # (window, n_subcarriers)
        n_sub = data.shape[1]
        if n_sub < 2:
            return np.ones(n_sub, dtype=bool)

        # 중간 서브캐리어들을 기준으로 사용
        mid = n_sub // 2
        ref_idx = list(range(max(0, mid - self.n_reference // 2),
                             min(n_sub, mid + self.n_reference // 2)))
        ref_signal = data[:, ref_idx].mean(axis=1)  # 기준 신호

        mask = np.ones(n_sub, dtype=bool)
        ref_var = np.var(ref_signal) + 1e-12

        for i in range(n_sub):
            sub = data[:, i]
            # 단순 MSC 근사: 교차상관 / (자기상관의 기하평균)
            cross = np.mean(sub * ref_signal) - np.mean(sub) * np.mean(ref_signal)
            sub_var = np.var(sub) + 1e-12
            msc = (cross ** 2) / (sub_var * ref_var)
            msc = float(np.clip(msc, 0.0, 1.0))
            mask[i] = msc >= self.msc_threshold

        return mask

    def apply(self, amplitudes: list[float]) -> tuple[list[float], dict]:
        """마스크 적용 후 필터링된 진폭 반환."""
        arr = np.array(amplitudes, dtype=np.float64)
        mask = self.update(amplitudes)
        filtered = np.where(mask, arr, 0.0)
        n_removed = int((~mask).sum())
        return filtered.tolist(), {
            "original_count": len(amplitudes),
            "removed_count": n_removed,
            "kept_ratio": round(float(mask.mean()), 3),
            "msc_threshold": self.msc_threshold,
        }
