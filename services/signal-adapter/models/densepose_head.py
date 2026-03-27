"""
DensePose Head — 24-part body segmentation + UV regression. (Phase 3-7)

Lightweight PyTorch implementation adapted from ruvnet/RuView densepose_head.py.
Designed for real-time inference on CPU/GPU.  Falls back gracefully when
PyTorch is not installed.

Body parts follow the DensePose-COCO 24-part convention:
    0=Torso, 1=R.Hand, 2=L.Hand, 3=L.Foot, 4=R.Foot,
    5=R.UpperLeg, 6=L.UpperLeg, 7=R.LowerLeg, 8=L.LowerLeg,
    9=L.UpperArm, 10=R.UpperArm, 11=L.LowerArm, 12=R.LowerArm,
    13=Head  ... (24 total)
"""
from __future__ import annotations

from typing import Any

NUM_BODY_PARTS = 24

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
# Fallback stub (no-torch)
# ---------------------------------------------------------------------------
class _DensePoseHeadStub:
    """CPU-only numpy stub used when PyTorch is unavailable."""

    def __init__(self, input_channels: int = 64,
                 num_body_parts: int = NUM_BODY_PARTS) -> None:
        self.input_channels = input_channels
        self.num_body_parts = num_body_parts

    def forward(self, x: Any) -> dict:
        import numpy as np
        return {
            "segmentation": np.zeros((1, self.num_body_parts + 1, 8, 8), dtype=np.float32),
            "uv_coordinates": np.zeros((1, 2, 8, 8), dtype=np.float32),
        }

    def __call__(self, x: Any) -> dict:
        return self.forward(x)

    def eval(self) -> "_DensePoseHeadStub":
        return self


# ---------------------------------------------------------------------------
# Full PyTorch implementation
# ---------------------------------------------------------------------------
if _TORCH_AVAILABLE:
    class _ConvBnRelu(nn.Sequential):
        def __init__(self, cin: int, cout: int, k: int = 3, p: int = 1,
                     dropout: float = 0.1) -> None:
            super().__init__(
                nn.Conv2d(cin, cout, k, padding=p, bias=False),
                nn.BatchNorm2d(cout),
                nn.ReLU(inplace=True),
                nn.Dropout2d(dropout),
            )

    class DensePoseHead(nn.Module):
        """Lightweight DensePose head for 24-part segmentation + UV regression.

        Parameters
        ----------
        input_channels : int
            Number of input feature-map channels (from backbone).
        num_body_parts : int
            Number of body-part classes (default 24).
        hidden_channels : list[int]
            Channel widths for the shared trunk conv layers.
        dropout_rate : float
            Spatial dropout probability.
        """

        def __init__(self,
                     input_channels: int = 64,
                     num_body_parts: int = NUM_BODY_PARTS,
                     hidden_channels: list[int] | None = None,
                     dropout_rate: float = 0.1) -> None:
            super().__init__()
            self.input_channels = input_channels
            self.num_body_parts = num_body_parts
            if hidden_channels is None:
                hidden_channels = [128, 64]

            # --- shared trunk ---
            trunk: list[nn.Module] = []
            cin = input_channels
            for cout in hidden_channels:
                trunk.append(_ConvBnRelu(cin, cout, dropout=dropout_rate))
                cin = cout
            self.trunk = nn.Sequential(*trunk)
            final = hidden_channels[-1]

            # --- segmentation branch (num_body_parts + 1 for background) ---
            self.seg_head = nn.Sequential(
                _ConvBnRelu(final, final // 2, dropout=dropout_rate),
                nn.ConvTranspose2d(final // 2, final // 4,
                                   kernel_size=4, stride=2, padding=1),
                nn.BatchNorm2d(final // 4),
                nn.ReLU(inplace=True),
                nn.Conv2d(final // 4, num_body_parts + 1, kernel_size=1),
            )

            # --- UV regression branch (2 channels: u, v) ---
            self.uv_head = nn.Sequential(
                _ConvBnRelu(final, final // 2, dropout=dropout_rate),
                nn.ConvTranspose2d(final // 2, final // 4,
                                   kernel_size=4, stride=2, padding=1),
                nn.BatchNorm2d(final // 4),
                nn.ReLU(inplace=True),
                nn.Conv2d(final // 4, 2, kernel_size=1),
            )

            self._init_weights()

        def _init_weights(self) -> None:
            for m in self.modules():
                if isinstance(m, nn.Conv2d):
                    nn.init.kaiming_normal_(m.weight, mode='fan_out',
                                           nonlinearity='relu')
                    if m.bias is not None:
                        nn.init.constant_(m.bias, 0)
                elif isinstance(m, nn.BatchNorm2d):
                    nn.init.constant_(m.weight, 1)
                    nn.init.constant_(m.bias, 0)

        def forward(self, x: "torch.Tensor") -> dict:
            """Forward pass.

            Parameters
            ----------
            x : Tensor, shape (B, C, H, W)

            Returns
            -------
            dict:
                segmentation  — (B, num_parts+1, H*2, W*2) logits
                uv_coordinates — (B, 2, H*2, W*2) in [0, 1]
            """
            features = self.trunk(x)
            seg = self.seg_head(features)
            uv = torch.sigmoid(self.uv_head(features))
            return {"segmentation": seg, "uv_coordinates": uv}

        def compute_loss(self,
                         pred: dict,
                         seg_target: "torch.Tensor",
                         uv_target: "torch.Tensor",
                         seg_weight: float = 1.0,
                         uv_weight: float = 1.0) -> "torch.Tensor":
            seg_loss = F.cross_entropy(pred["segmentation"], seg_target,
                                       ignore_index=-1)
            uv_loss = F.l1_loss(pred["uv_coordinates"], uv_target)
            return seg_weight * seg_loss + uv_weight * uv_loss

else:
    # Expose the stub as DensePoseHead when torch is absent
    DensePoseHead = _DensePoseHeadStub  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------
def build_densepose_head(input_channels: int = 64,
                         num_body_parts: int = NUM_BODY_PARTS,
                         **kwargs: Any) -> Any:
    """Return a DensePoseHead (full or stub) depending on torch availability."""
    if _TORCH_AVAILABLE:
        return DensePoseHead(input_channels=input_channels,
                             num_body_parts=num_body_parts, **kwargs)
    return _DensePoseHeadStub(input_channels=input_channels,
                              num_body_parts=num_body_parts)


TORCH_AVAILABLE = _TORCH_AVAILABLE
