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


# ---------------------------------------------------------------------------
# WiFi-pose rule-based keypoint head (Phase C-3)
# ---------------------------------------------------------------------------
class WifiPoseHead:
    """
    WiFi CSI → DensePose 헤드 (스캐폴드 + 규칙기반 fallback).

    Stage 2 구현 예정: CSI 특성벡터 → 24부위 UV 좌표 회귀
    현재: WiFiPoseEstimator의 규칙기반 결과를 UV 좌표로 변환
    """

    BODY_PARTS = [
        "nose", "neck", "right_shoulder", "right_elbow", "right_wrist",
        "left_shoulder", "left_elbow", "left_wrist", "right_hip", "right_knee",
        "right_ankle", "left_hip", "left_knee", "left_ankle",
        "right_eye", "left_eye", "right_ear", "left_ear",
    ]

    def pose_to_keypoints(self, pose_class: str, joints: dict) -> list[dict]:
        """포즈 클래스 + 관절 각도 → 17개 COCO 키포인트 (정규화 좌표)."""
        # 기준 스켈레톤 (정면 서있는 자세 [x, y] in [0,1])
        base: dict[str, list[float]] = {
            "nose": [0.5, 0.05], "neck": [0.5, 0.15],
            "right_shoulder": [0.65, 0.22], "right_elbow": [0.72, 0.38],
            "right_wrist": [0.75, 0.52],
            "left_shoulder": [0.35, 0.22], "left_elbow": [0.28, 0.38],
            "left_wrist": [0.25, 0.52],
            "right_hip": [0.58, 0.50], "right_knee": [0.60, 0.70],
            "right_ankle": [0.61, 0.90],
            "left_hip": [0.42, 0.50], "left_knee": [0.40, 0.70],
            "left_ankle": [0.39, 0.90],
            "right_eye": [0.53, 0.03], "left_eye": [0.47, 0.03],
            "right_ear": [0.56, 0.05], "left_ear": [0.44, 0.05],
        }
        # 포즈별 변형
        kpts = {k: list(v) for k, v in base.items()}
        if pose_class == "sitting":
            for k in ["right_knee", "right_ankle", "left_knee", "left_ankle"]:
                kpts[k][1] = max(0.0, kpts[k][1] - 0.2)
            for k in ["right_hip", "left_hip"]:
                kpts[k][1] = 0.45
        elif pose_class == "lying":
            for k in kpts:
                kpts[k] = [kpts[k][1], 0.5]  # 90도 회전
        elif pose_class == "fallen":
            for k in kpts:
                kpts[k][1] = 0.9

        # 팔 올림 적용
        arm_raise = joints.get("left_arm_raise", 0)
        if arm_raise > 0.3:
            kpts["left_elbow"][1] -= arm_raise * 0.15
            kpts["left_wrist"][1] -= arm_raise * 0.25

        return [
            {"part": p, "x": round(kpts[p][0], 3), "y": round(kpts[p][1], 3), "confidence": 0.7}
            for p in self.BODY_PARTS if p in kpts
        ]
