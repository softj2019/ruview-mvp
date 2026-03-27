"""
Modality Translation Network — CSI → visual feature space. (Phase 3-8)

Lightweight encoder-decoder (MLP or CNN) that maps raw CSI amplitude /
phase vectors into a visual-like feature representation compatible with
the DensePose head.  Falls back to a numpy stub when PyTorch is absent.

Architecture (PyTorch mode):
    CSI vector (N_subcarriers)
      → 1-D CNN encoder (strided convolutions)
      → bottleneck (attention-weighted global pool, optional)
      → linear projection → 2-D feature map (C×H×W)
      → suitable as input to DensePoseHead

Fallback (numpy mode):
    Returns a zero tensor of the expected output shape.

References:
    ruvnet/RuView modality_translation.py — adapted for lightweight
    real-time CSI inference on edge devices.
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Optional PyTorch import
# ---------------------------------------------------------------------------
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False


# ---------------------------------------------------------------------------
# Fallback stub
# ---------------------------------------------------------------------------
class _ModalityTranslationStub:
    """Numpy stub used when PyTorch is not installed."""

    def __init__(self, input_dim: int = 64, output_channels: int = 64,
                 output_size: int = 8) -> None:
        self.input_dim = input_dim
        self.output_channels = output_channels
        self.output_size = output_size

    def forward(self, x: Any) -> Any:
        import numpy as np
        return np.zeros(
            (1, self.output_channels, self.output_size, self.output_size),
            dtype=np.float32,
        )

    def __call__(self, x: Any) -> Any:
        return self.forward(x)

    def eval(self) -> "_ModalityTranslationStub":
        return self

    def get_feature_statistics(self, features: Any) -> dict:
        return {"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0}


# ---------------------------------------------------------------------------
# Full PyTorch implementation
# ---------------------------------------------------------------------------
if _TORCH_AVAILABLE:
    class ModalityTranslationNetwork(nn.Module):
        """CSI-to-visual feature translator.

        Parameters
        ----------
        input_dim : int
            Length of the 1-D CSI input vector (number of subcarriers × 2
            for amplitude+phase, or just amplitude).
        hidden_channels : list[int]
            Channel widths for the 1-D CNN encoder stages.
        output_channels : int
            Number of feature-map channels fed to DensePoseHead.
        output_size : int
            Spatial resolution (H = W) of the output feature map.
        use_attention : bool
            Whether to add a lightweight channel-attention gate.
        dropout_rate : float
            Dropout probability.
        """

        def __init__(self,
                     input_dim: int = 64,
                     hidden_channels: list[int] | None = None,
                     output_channels: int = 64,
                     output_size: int = 8,
                     use_attention: bool = False,
                     dropout_rate: float = 0.1) -> None:
            super().__init__()
            if hidden_channels is None:
                hidden_channels = [128, 64]
            self.output_channels = output_channels
            self.output_size = output_size
            self.use_attention = use_attention

            # 1-D CNN encoder (treats subcarrier axis as sequence)
            enc_layers: list[nn.Module] = []
            cin = 1   # channel-first 1-D: (B, 1, N_sub)
            for cout in hidden_channels:
                enc_layers += [
                    nn.Conv1d(cin, cout, kernel_size=3, padding=1, bias=False),
                    nn.BatchNorm1d(cout),
                    nn.ReLU(inplace=True),
                    nn.Dropout(dropout_rate),
                    nn.MaxPool1d(kernel_size=2, stride=2),
                ]
                cin = cout
            self.encoder = nn.Sequential(*enc_layers)

            # Channel attention (SE-like)
            if use_attention:
                self.attention = nn.Sequential(
                    nn.AdaptiveAvgPool1d(1),
                    nn.Flatten(),
                    nn.Linear(hidden_channels[-1], hidden_channels[-1] // 4),
                    nn.ReLU(inplace=True),
                    nn.Linear(hidden_channels[-1] // 4, hidden_channels[-1]),
                    nn.Sigmoid(),
                )

            # Linear projection → 2-D feature map
            self.proj = nn.Linear(hidden_channels[-1],
                                  output_channels * output_size * output_size)
            self._out_ch = output_channels
            self._out_sz = output_size

            self._init_weights()

        def _init_weights(self) -> None:
            for m in self.modules():
                if isinstance(m, nn.Conv1d):
                    nn.init.kaiming_normal_(m.weight, nonlinearity='relu')
                    if m.bias is not None:
                        nn.init.constant_(m.bias, 0)
                elif isinstance(m, (nn.BatchNorm1d,)):
                    nn.init.constant_(m.weight, 1)
                    nn.init.constant_(m.bias, 0)
                elif isinstance(m, nn.Linear):
                    nn.init.xavier_uniform_(m.weight)
                    if m.bias is not None:
                        nn.init.constant_(m.bias, 0)

        def encode(self, x: "torch.Tensor") -> "torch.Tensor":
            """Encode (B, N_sub) → (B, C_hidden) via 1-D CNN + global pool."""
            # x: (B, N_sub) → (B, 1, N_sub)
            h = x.unsqueeze(1)
            h = self.encoder(h)               # (B, C, L')
            if self.use_attention:
                attn = self.attention(h)      # (B, C)
                h = h * attn.unsqueeze(-1)
            h = h.mean(dim=-1)               # global average pool → (B, C)
            return h

        def forward(self, x: "torch.Tensor") -> "torch.Tensor":
            """Translate CSI vector to visual feature map.

            Parameters
            ----------
            x : Tensor, shape (B, N_subcarriers)

            Returns
            -------
            Tensor, shape (B, output_channels, output_size, output_size)
            """
            h = self.encode(x)
            h = self.proj(h)                 # (B, C*H*W)
            h = h.view(-1, self._out_ch,
                        self._out_sz, self._out_sz)
            return torch.tanh(h)

        def compute_translation_loss(self,
                                     predicted: "torch.Tensor",
                                     target: "torch.Tensor",
                                     loss_type: str = 'mse') -> "torch.Tensor":
            if loss_type == 'l1':
                return F.l1_loss(predicted, target)
            elif loss_type == 'smooth_l1':
                return F.smooth_l1_loss(predicted, target)
            return F.mse_loss(predicted, target)

        def get_feature_statistics(self, features: "torch.Tensor") -> dict:
            with torch.no_grad():
                return {
                    'mean': float(features.mean()),
                    'std': float(features.std()),
                    'min': float(features.min()),
                    'max': float(features.max()),
                }

else:
    ModalityTranslationNetwork = _ModalityTranslationStub  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------
def build_modality_translator(input_dim: int = 64,
                               output_channels: int = 64,
                               output_size: int = 8,
                               **kwargs: Any) -> Any:
    """Return a ModalityTranslationNetwork (full or stub)."""
    if _TORCH_AVAILABLE:
        return ModalityTranslationNetwork(
            input_dim=input_dim,
            output_channels=output_channels,
            output_size=output_size,
            **kwargs,
        )
    return _ModalityTranslationStub(
        input_dim=input_dim,
        output_channels=output_channels,
        output_size=output_size,
    )


TORCH_AVAILABLE = _TORCH_AVAILABLE
