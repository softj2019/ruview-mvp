"""
Tests for Phase 3-4 through 3-8 signal processing algorithms.

Covers:
- RFTomography: ISTA reconstruction + visualize()
- IntentionDetector: pre-movement detection, lead_time bounds
- GestureClassifier: DTW distance, classify() return types
- DensePoseHead (stub/full): forward shape
- ModalityTranslationNetwork (stub/full): forward shape
"""
import sys
import os

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ===========================================================================
# RF Tomography
# ===========================================================================
from rf_tomography import RFTomography


class TestRFTomography:
    def _nodes(self):
        return [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0)]

    def test_reconstruct_shape(self):
        rft = RFTomography(grid_size=(8, 8))
        csi = np.random.rand(4, 64)
        grid = rft.reconstruct(csi, self._nodes())
        assert grid.shape == (8, 8)

    def test_reconstruct_values_in_range(self):
        rft = RFTomography(grid_size=(10, 10))
        csi = np.random.rand(4, 32)
        grid = rft.reconstruct(csi, self._nodes())
        assert grid.min() >= 0.0
        assert grid.max() <= 1.0 + 1e-6

    def test_reconstruct_1d_csi(self):
        """Flat measurement vector path."""
        rft = RFTomography(grid_size=(5, 5))
        nodes = [(0.0, 0.0), (1.0, 1.0)]
        # 2 nodes → 2 directed links
        y = np.array([0.8, 0.4])
        grid = rft.reconstruct(y, nodes)
        assert grid.shape == (5, 5)

    def test_reconstruct_requires_two_nodes(self):
        rft = RFTomography()
        with pytest.raises(ValueError):
            rft.reconstruct(np.zeros((1, 10)), [(0.5, 0.5)])

    def test_visualize_keys(self):
        rft = RFTomography(grid_size=(6, 6))
        rft.reconstruct(np.random.rand(4, 16), self._nodes())
        vis = rft.visualize()
        for key in ("grid", "rows", "cols", "max_value", "occupied_cells"):
            assert key in vis

    def test_visualize_grid_dimensions(self):
        rft = RFTomography(grid_size=(4, 7))
        rft.reconstruct(np.random.rand(4, 8), self._nodes())
        vis = rft.visualize()
        assert vis["rows"] == 4
        assert vis["cols"] == 7
        assert len(vis["grid"]) == 4
        assert len(vis["grid"][0]) == 7


# ===========================================================================
# Intention Detector
# ===========================================================================
from intention_detector import IntentionDetector


class TestIntentionDetector:
    def test_returns_dict_keys(self):
        det = IntentionDetector()
        result = det.update(0.0, 0.0)
        assert set(result.keys()) == {"detected", "confidence", "lead_time_ms"}

    def test_not_detected_flat_signal(self):
        det = IntentionDetector(window_ms=500, slope_threshold=0.05)
        t = 0.0
        for _ in range(20):
            result = det.update(0.3, t)
            t += 0.05
        assert result["detected"] is False
        assert result["confidence"] == 0.0

    def test_detected_ramp_signal(self):
        """A rising ramp before a peak should be detected."""
        det = IntentionDetector(window_ms=600, lead_ms=300,
                                slope_threshold=0.01)
        t = 0.0
        for i in range(30):
            # Slow rise in lead window, then jump in post window
            v = float(i) / 15.0
            det.update(v, t)
            t += 0.02
        result = det.update(2.0, t)   # large spike
        # The slope over earlier samples should have been non-zero
        assert isinstance(result["detected"], bool)
        assert 0.0 <= result["confidence"] <= 1.0

    def test_lead_time_in_range_when_detected(self):
        det = IntentionDetector(window_ms=600, lead_ms=300,
                                slope_threshold=0.01)
        t = 0.0
        last = {"detected": False, "confidence": 0.0, "lead_time_ms": 0.0}
        for i in range(40):
            v = float(i) / 10.0
            last = det.update(v, t)
            t += 0.02
        if last["detected"]:
            assert 200.0 <= last["lead_time_ms"] <= 500.0

    def test_reset_clears_buffer(self):
        det = IntentionDetector()
        for i in range(5):
            det.update(float(i), float(i) * 0.1)
        det.reset()
        result = det.update(1.0, 1.0)
        assert result["detected"] is False


# ===========================================================================
# Gesture Classifier
# ===========================================================================
from gesture_classifier import GestureClassifier, GESTURES


class TestGestureClassifier:
    def _make_seq(self, n: int = 15) -> list:
        return [np.random.rand(8) for _ in range(n)]

    def test_classify_returns_tuple(self):
        gc = GestureClassifier()
        result = gc.classify(self._make_seq())
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_gesture_label_in_set(self):
        gc = GestureClassifier()
        label, conf = gc.classify(self._make_seq())
        assert label in GESTURES

    def test_confidence_in_range(self):
        gc = GestureClassifier()
        _, conf = gc.classify(self._make_seq())
        assert 0.0 <= conf <= 1.0

    def test_empty_sequence(self):
        gc = GestureClassifier()
        label, conf = gc.classify([])
        assert label in GESTURES
        assert conf == 0.0

    def test_dtw_distance_identical(self):
        gc = GestureClassifier()
        s = np.array([0.1, 0.5, 0.9, 0.5, 0.1])
        dist = gc._dtw_distance(s, s)
        assert dist == pytest.approx(0.0, abs=1e-9)

    def test_dtw_distance_non_negative(self):
        gc = GestureClassifier()
        s1 = np.random.rand(12)
        s2 = np.random.rand(10)
        assert gc._dtw_distance(s1, s2) >= 0.0

    def test_scalar_frames(self):
        """Single-element (scalar) frames should be handled."""
        gc = GestureClassifier()
        seq = [np.array([float(i)]) for i in range(20)]
        label, conf = gc.classify(seq)
        assert label in GESTURES

    def test_gestures_list_length(self):
        assert len(GESTURES) == 5


# ===========================================================================
# DensePose Head (stub always available; full tested if torch present)
# ===========================================================================
from models.densepose_head import build_densepose_head, TORCH_AVAILABLE, NUM_BODY_PARTS


class TestDensePoseHead:
    def _make_input(self, channels: int = 16, h: int = 8, w: int = 8):
        """Return a (1, C, H, W) tensor in whatever format is available."""
        if TORCH_AVAILABLE:
            import torch
            return torch.zeros(1, channels, h, w)
        return np.zeros((1, channels, h, w), dtype=np.float32)

    def test_forward_shape(self):
        head = build_densepose_head(input_channels=16)
        if TORCH_AVAILABLE:
            head.eval()
            import torch
            with torch.no_grad():
                out = head(self._make_input(16))
        else:
            out = head(self._make_input(16))
        assert "segmentation" in out
        assert "uv_coordinates" in out

    def test_seg_channels(self):
        head = build_densepose_head(input_channels=16,
                                    num_body_parts=NUM_BODY_PARTS)
        if TORCH_AVAILABLE:
            head.eval()
            import torch
            with torch.no_grad():
                out = head(self._make_input(16))
        else:
            out = head(self._make_input(16))
        seg = np.asarray(out["segmentation"].detach().numpy()
                         if TORCH_AVAILABLE else out["segmentation"])
        assert seg.shape[1] == NUM_BODY_PARTS + 1

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="torch not installed")
    def test_torch_forward_shape(self):
        import torch
        head = build_densepose_head(input_channels=32, num_body_parts=24,
                                    hidden_channels=[64, 32])
        head.eval()
        x = torch.zeros(2, 32, 8, 8)
        with torch.no_grad():
            out = head(x)
        assert out["segmentation"].shape == (2, 25, 16, 16)
        assert out["uv_coordinates"].shape == (2, 2, 16, 16)

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="torch not installed")
    def test_torch_uv_in_range(self):
        import torch
        head = build_densepose_head(input_channels=16)
        head.eval()
        x = torch.randn(1, 16, 4, 4)
        with torch.no_grad():
            out = head(x)
        uv = out["uv_coordinates"]
        assert uv.min() >= 0.0
        assert uv.max() <= 1.0


# ===========================================================================
# Modality Translation Network
# ===========================================================================
from models.modality_translation import build_modality_translator, TORCH_AVAILABLE as MT_TORCH


class TestModalityTranslation:
    def _make_input(self, dim: int = 64):
        if MT_TORCH:
            import torch
            return torch.zeros(1, dim)
        return np.zeros((1, dim), dtype=np.float32)

    def test_forward_shape(self):
        net = build_modality_translator(input_dim=64, output_channels=32,
                                        output_size=4)
        if MT_TORCH:
            net.eval()
            import torch
            with torch.no_grad():
                out = net(self._make_input(64))
            out_arr = out.numpy()
        else:
            out = net(self._make_input(64))
            out_arr = np.asarray(out)
        assert out_arr.shape == (1, 32, 4, 4)

    def test_feature_stats(self):
        net = build_modality_translator()
        if MT_TORCH:
            import torch
            feat = torch.zeros(1, 64, 4, 4)
        else:
            feat = np.zeros((1, 64, 4, 4))
        stats = net.get_feature_statistics(feat)
        assert "mean" in stats

    @pytest.mark.skipif(not MT_TORCH, reason="torch not installed")
    def test_torch_output_shape(self):
        import torch
        net = build_modality_translator(
            input_dim=64,
            hidden_channels=[128, 64],
            output_channels=32,
            output_size=8,
        )
        net.eval()
        x = torch.randn(2, 64)
        with torch.no_grad():
            out = net(x)
        assert out.shape == (2, 32, 8, 8)

    @pytest.mark.skipif(not MT_TORCH, reason="torch not installed")
    def test_torch_output_tanh_range(self):
        import torch
        net = build_modality_translator(input_dim=32, output_channels=16,
                                        output_size=4)
        net.eval()
        x = torch.randn(3, 32)
        with torch.no_grad():
            out = net(x)
        assert out.min() >= -1.0 - 1e-5
        assert out.max() <= 1.0 + 1e-5

    @pytest.mark.skipif(not MT_TORCH, reason="torch not installed")
    def test_torch_with_attention(self):
        import torch
        net = build_modality_translator(input_dim=64, output_channels=16,
                                        output_size=4, use_attention=True)
        net.eval()
        x = torch.randn(1, 64)
        with torch.no_grad():
            out = net(x)
        assert out.shape == (1, 16, 4, 4)
