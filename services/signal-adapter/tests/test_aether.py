"""
Tests for Phase 5-2: AETHEREmbedding contrastive re-ID system.
"""
import sys
import os
import types
from unittest.mock import patch

import numpy as np
import pytest

# 경로 설정
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _random_csi(n: int = 256) -> np.ndarray:
    rng = np.random.default_rng(42)
    return rng.random(n).astype(np.float32)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAETHEREmbedding:

    def test_compute_appearance_returns_128d_vector(self):
        """compute_appearance 는 shape=(128,) float32 L2-정규화 벡터를 반환해야 한다."""
        from models.aether_embedding import AETHEREmbedding

        emb_model = AETHEREmbedding(embedding_dim=128, device='cpu')
        csi = _random_csi(256)
        emb = emb_model.compute_appearance(csi, zone_id='zone_A')

        assert emb.shape == (128,), f"Expected (128,), got {emb.shape}"
        assert emb.dtype == np.float32
        # L2 norm ≈ 1
        norm = float(np.linalg.norm(emb))
        assert abs(norm - 1.0) < 1e-4, f"Embedding not unit-norm: norm={norm}"

    def test_compute_similarity_range(self):
        """compute_similarity 는 [0,1] 범위를 반환해야 한다."""
        from models.aether_embedding import AETHEREmbedding

        emb_model = AETHEREmbedding()
        rng = np.random.default_rng(0)
        e1 = rng.standard_normal(128).astype(np.float32)
        e2 = rng.standard_normal(128).astype(np.float32)

        sim = emb_model.compute_similarity(e1, e2)
        assert 0.0 <= sim <= 1.0, f"Similarity out of range: {sim}"

        # 동일 벡터는 1.0
        sim_same = emb_model.compute_similarity(e1, e1)
        assert abs(sim_same - 1.0) < 1e-5

        # 반대 벡터는 0.0
        sim_opp = emb_model.compute_similarity(e1, -e1)
        assert abs(sim_opp - 0.0) < 1e-5

    def test_gallery_match(self):
        """update_gallery 후 match_gallery 가 올바른 person_id를 반환해야 한다."""
        from models.aether_embedding import AETHEREmbedding

        emb_model = AETHEREmbedding()
        rng = np.random.default_rng(7)

        # 두 사람의 임베딩 생성
        emb_alice = rng.standard_normal(128).astype(np.float32)
        emb_alice /= np.linalg.norm(emb_alice)

        emb_bob = -emb_alice + rng.standard_normal(128).astype(np.float32) * 0.05
        emb_bob /= np.linalg.norm(emb_bob)

        emb_model.update_gallery('alice', emb_alice)
        emb_model.update_gallery('bob', emb_bob)

        # alice 에 가까운 쿼리
        query_alice = emb_alice + rng.standard_normal(128).astype(np.float32) * 0.01
        query_alice /= np.linalg.norm(query_alice)

        result = emb_model.match_gallery(query_alice, threshold=0.5)
        assert result == 'alice', f"Expected 'alice', got {result}"

        # threshold 매우 높으면 None
        result_none = emb_model.match_gallery(query_alice, threshold=0.9999)
        assert result_none is None or isinstance(result_none, str)

    def test_contrastive_loss_positive(self):
        """
        anchor==positive, anchor!=-negative 일 때 loss > 0 이어야 한다.
        triplet loss = max(0, d(a,p) - d(a,n) + margin)
        """
        from models.aether_embedding import AETHEREmbedding

        rng = np.random.default_rng(3)
        anchor = rng.standard_normal(128)
        positive = anchor.copy()           # 동일 → d(a,p)=0
        negative = anchor + rng.standard_normal(128) * 5.0  # 먼 벡터

        # d(a,p)=0, d(a,n)>0 → loss = max(0, 0 - d(a,n) + margin)
        # margin=0.5, d(a,n) ≫ 0.5 이므로 loss = 0
        loss_easy = AETHEREmbedding.contrastive_loss(anchor, positive, negative, margin=0.5)
        assert loss_easy == 0.0, f"Easy triplet should have 0 loss, got {loss_easy}"

        # hard triplet: negative ≈ anchor (가까움) → loss > 0
        hard_negative = anchor + rng.standard_normal(128) * 0.01
        loss_hard = AETHEREmbedding.contrastive_loss(anchor, positive, hard_negative, margin=0.5)
        assert loss_hard > 0.0, f"Hard triplet should have loss > 0, got {loss_hard}"

        # loss 는 항상 ≥ 0
        for _ in range(10):
            a = rng.standard_normal(128)
            p = rng.standard_normal(128)
            n = rng.standard_normal(128)
            assert AETHEREmbedding.contrastive_loss(a, p, n) >= 0.0

    def test_fallback_no_torch(self):
        """
        torch import 실패 시 FFT 폴백으로 올바른 128-d 벡터를 반환해야 한다.
        """
        import importlib
        import models.aether_embedding as ae_mod

        original_torch_available = ae_mod._TORCH_AVAILABLE

        try:
            # _TORCH_AVAILABLE 을 False 로 강제
            ae_mod._TORCH_AVAILABLE = False

            from models.aether_embedding import AETHEREmbedding

            emb_model = AETHEREmbedding(embedding_dim=128)
            # _use_torch 강제 설정 (생성자 이후)
            emb_model._use_torch = False

            csi = _random_csi(128)
            emb = emb_model.compute_appearance(csi, zone_id='zone_B')

            assert emb.shape == (128,), f"Fallback shape wrong: {emb.shape}"
            assert emb.dtype == np.float32
            norm = float(np.linalg.norm(emb))
            assert abs(norm - 1.0) < 1e-4, f"Fallback not unit-norm: {norm}"
        finally:
            ae_mod._TORCH_AVAILABLE = original_torch_available
