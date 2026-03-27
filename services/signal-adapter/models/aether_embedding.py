"""
AETHER Contrastive Embedding — Phase 5-2
CSI 기반 비접촉 재식별(re-ID) 임베딩 시스템.

PyTorch 사용 불가 환경에서는 FFT 밴드 에너지 특징 + L2 정규화 폴백.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Dict, Optional

import numpy as np

__all__ = ['AETHEREmbedding']

# ──────────────────────────────────────────────────────────────────────────────
# Optional torch import (graceful fallback)
# ──────────────────────────────────────────────────────────────────────────────
try:
    import torch
    import torch.nn as nn
    _TORCH_AVAILABLE = True
except ImportError:  # pragma: no cover
    _TORCH_AVAILABLE = False


# ──────────────────────────────────────────────────────────────────────────────
# Lightweight MLP backbone (torch path)
# ──────────────────────────────────────────────────────────────────────────────
if _TORCH_AVAILABLE:
    class _EmbeddingMLP(nn.Module):
        """128-d 임베딩 MLP: input_dim → 256 → 128 (L2 normed)."""

        def __init__(self, input_dim: int = 256, embedding_dim: int = 128):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(input_dim, 256),
                nn.BatchNorm1d(256),
                nn.ReLU(inplace=True),
                nn.Dropout(0.2),
                nn.Linear(256, embedding_dim),
            )

        def forward(self, x: 'torch.Tensor') -> 'torch.Tensor':
            out = self.net(x)
            # L2 normalize
            return out / (out.norm(dim=-1, keepdim=True) + 1e-8)


# ──────────────────────────────────────────────────────────────────────────────
# FFT 밴드 에너지 폴백 특징 추출
# ──────────────────────────────────────────────────────────────────────────────
_NUM_BANDS = 16  # 폴백 밴드 수 (총 특징 = _NUM_BANDS * 8 = 128)


def _fft_band_features(csi_amplitude: np.ndarray, embedding_dim: int = 128) -> np.ndarray:
    """FFT 밴드 에너지를 이용해 embedding_dim 차원 특징 벡터를 생성."""
    arr = np.asarray(csi_amplitude, dtype=np.float64).ravel()

    # 최소 길이 보장
    if arr.size < 64:
        arr = np.pad(arr, (0, 64 - arr.size))

    # FFT magnitude
    fft_mag = np.abs(np.fft.rfft(arr))

    # 밴드별 평균 에너지: embedding_dim 개 밴드로 균등 분할
    bands = np.array_split(fft_mag, embedding_dim)
    feat = np.array([b.mean() if b.size > 0 else 0.0 for b in bands], dtype=np.float64)

    # L2 정규화
    norm = np.linalg.norm(feat)
    if norm > 1e-8:
        feat /= norm
    return feat.astype(np.float32)


# ──────────────────────────────────────────────────────────────────────────────
# AETHEREmbedding 메인 클래스
# ──────────────────────────────────────────────────────────────────────────────

class AETHEREmbedding:
    """
    AETHER 대조 학습 기반 re-ID 임베딩.

    Parameters
    ----------
    embedding_dim : int
        출력 임베딩 차원 (기본 128).
    device : str
        'cpu' 또는 'cuda' (torch 사용 시).
    ema_alpha : float
        갤러리 EMA 업데이트 계수 (0~1, 높을수록 새 임베딩 반영).
    """

    def __init__(
        self,
        embedding_dim: int = 128,
        device: str = 'cpu',
        ema_alpha: float = 0.3,
    ) -> None:
        self.embedding_dim = embedding_dim
        self.ema_alpha = ema_alpha
        self._gallery: Dict[str, np.ndarray] = {}
        self._use_torch = _TORCH_AVAILABLE

        if self._use_torch:
            self._device = torch.device(device)
            self._model = _EmbeddingMLP(
                input_dim=256, embedding_dim=embedding_dim
            ).to(self._device)
            self._model.eval()
        else:
            self._device = None
            self._model = None

    # ──────────────────────────────────────────────────────────────────────
    # 공개 API
    # ──────────────────────────────────────────────────────────────────────

    def compute_appearance(
        self,
        csi_amplitude: np.ndarray,
        zone_id: str,  # noqa: ARG002 — 추후 zone-conditioned 임베딩에 활용
    ) -> np.ndarray:
        """
        CSI amplitude 배열에서 128-d 임베딩 벡터를 계산한다.

        Returns
        -------
        np.ndarray  shape=(embedding_dim,), dtype=float32, L2-normalized
        """
        if self._use_torch:
            return self._torch_compute(csi_amplitude)
        return _fft_band_features(csi_amplitude, self.embedding_dim)

    def compute_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """
        두 임베딩 벡터의 코사인 유사도를 반환한다.

        Returns
        -------
        float in [0, 1]  (1 = 동일, 0 = 직교)
        """
        e1 = np.asarray(emb1, dtype=np.float32).ravel()
        e2 = np.asarray(emb2, dtype=np.float32).ravel()
        norm1 = np.linalg.norm(e1)
        norm2 = np.linalg.norm(e2)
        if norm1 < 1e-8 or norm2 < 1e-8:
            return 0.0
        cos = float(np.dot(e1, e2) / (norm1 * norm2))
        # [-1,1] → [0,1]
        return (cos + 1.0) / 2.0

    def update_gallery(self, person_id: str, embedding: np.ndarray) -> None:
        """
        갤러리에 person_id의 임베딩을 저장/EMA 업데이트한다.
        """
        emb = np.asarray(embedding, dtype=np.float32).ravel()
        if person_id in self._gallery:
            prev = self._gallery[person_id]
            updated = (1.0 - self.ema_alpha) * prev + self.ema_alpha * emb
            # re-normalize
            norm = np.linalg.norm(updated)
            if norm > 1e-8:
                updated /= norm
            self._gallery[person_id] = updated
        else:
            norm = np.linalg.norm(emb)
            self._gallery[person_id] = emb / norm if norm > 1e-8 else emb

    def match_gallery(
        self,
        embedding: np.ndarray,
        threshold: float = 0.7,
    ) -> Optional[str]:
        """
        갤러리에서 가장 유사한 person_id를 반환한다.

        Parameters
        ----------
        threshold : float
            유사도 임계값 (기본 0.7). 미만 시 None 반환.

        Returns
        -------
        str | None
        """
        if not self._gallery:
            return None

        best_id: Optional[str] = None
        best_sim: float = -1.0

        for pid, ref_emb in self._gallery.items():
            sim = self.compute_similarity(embedding, ref_emb)
            if sim > best_sim:
                best_sim = sim
                best_id = pid

        return best_id if best_sim >= threshold else None

    @staticmethod
    def contrastive_loss(
        anchor: np.ndarray,
        positive: np.ndarray,
        negative: np.ndarray,
        margin: float = 0.5,
    ) -> float:
        """
        Triplet margin loss (numpy-only).

        loss = max(0, d(a,p) - d(a,n) + margin)

        여기서 d는 유클리드 거리.

        Returns
        -------
        float  ≥ 0
        """
        a = np.asarray(anchor, dtype=np.float64).ravel()
        p = np.asarray(positive, dtype=np.float64).ravel()
        n = np.asarray(negative, dtype=np.float64).ravel()

        dist_ap = float(np.linalg.norm(a - p))
        dist_an = float(np.linalg.norm(a - n))
        loss = max(0.0, dist_ap - dist_an + margin)
        return loss

    # ──────────────────────────────────────────────────────────────────────
    # 내부 헬퍼
    # ──────────────────────────────────────────────────────────────────────

    def _torch_compute(self, csi_amplitude: np.ndarray) -> np.ndarray:
        """torch MLP 경로: CSI amplitude → 256-d 입력 특징 → 128-d 임베딩."""
        arr = np.asarray(csi_amplitude, dtype=np.float32).ravel()

        # 256-d 입력 특징 구성: FFT 밴드 128 + 통계 특징 128
        fft_feat = _fft_band_features(arr, 128)

        # 통계: 슬라이딩 윈도우 평균/std × 64 → 128
        if arr.size >= 64:
            windows = np.lib.stride_tricks.sliding_window_view(arr[:64], 8)
        else:
            padded = np.pad(arr, (0, 64 - arr.size))
            windows = np.lib.stride_tricks.sliding_window_view(padded, 8)

        stat_mean = windows.mean(axis=1).astype(np.float32)
        stat_std = windows.std(axis=1).astype(np.float32)
        stat_feat = np.concatenate([stat_mean, stat_std])[:128]
        # 패딩
        if stat_feat.size < 128:
            stat_feat = np.pad(stat_feat, (0, 128 - stat_feat.size))

        # L2 normalize stat_feat
        s_norm = np.linalg.norm(stat_feat)
        if s_norm > 1e-8:
            stat_feat /= s_norm

        input_vec = np.concatenate([fft_feat, stat_feat]).astype(np.float32)  # (256,)

        with torch.no_grad():
            t = torch.from_numpy(input_vec).unsqueeze(0).to(self._device)  # (1,256)
            out = self._model(t)  # (1,128)
            emb = out.squeeze(0).cpu().numpy()

        return emb.astype(np.float32)
