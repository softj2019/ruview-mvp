"""
ADR-031 단순화 ViewpointFusion — 기하학적 편향 어텐션 융합.

6노드 CSI 피처를 기하학적 다양성 기반 어텐션으로 융합.
AETHER 128차원 임베딩 없이 현재 CSI 피처(motion_index, amplitude, phase_slope)만 사용.

참조: ruvnet/RuView ADR-031-ruview-sensing-first-rf-mode (Silver tier)
알고리즘:
  1. 노드별 128차원→현재 피처 벡터 구성
  2. 기하학적 편향 행렬: G_bias[i,j] = w_angle*cos(θ_ij) + w_dist*exp(-d_ij/d_ref)
  3. Scaled dot-product attention with G_bias
  4. 가중 평균 융합
"""
import math
import numpy as np
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class NodeFeature:
    node_id: str
    x: float          # 픽셀
    y: float          # 픽셀
    motion_index: float
    amplitude: float
    phase_slope: float
    presence_score: float
    timestamp: float

@dataclass
class FusionResult:
    fused_motion: float
    fused_presence: float
    fused_position_x: float
    fused_position_y: float
    confidence: float
    contributing_nodes: int
    attention_weights: list[float]

class ViewpointFusion:
    """ADR-031 Silver tier: 6노드 기하학적 어텐션 융합."""

    W_ANGLE = 0.6   # 각도 편향 가중치
    W_DIST = 0.4    # 거리 편향 가중치
    D_REF = 400.0   # 기준 거리 (픽셀)

    def __init__(self):
        self._node_features: dict[str, NodeFeature] = {}

    def update_node(self, nf: NodeFeature) -> None:
        self._node_features[nf.node_id] = nf

    def _geometric_bias(self, nodes: list[NodeFeature]) -> np.ndarray:
        n = len(nodes)
        G = np.zeros((n, n))
        for i, ni in enumerate(nodes):
            for j, nj in enumerate(nodes):
                if i == j:
                    G[i, j] = 1.0
                    continue
                dx = nj.x - ni.x
                dy = nj.y - ni.y
                d_ij = math.sqrt(dx*dx + dy*dy) + 1e-9
                theta_ij = math.acos(max(-1, min(1, dx / d_ij)))
                G[i, j] = (self.W_ANGLE * math.cos(theta_ij) +
                           self.W_DIST * math.exp(-d_ij / self.D_REF))
        return G

    def fuse(self, ttl: float = 3.0) -> Optional[FusionResult]:
        import time
        now = time.monotonic()
        active = [nf for nf in self._node_features.values()
                  if now - nf.timestamp < ttl and nf.amplitude > 0.01]
        if len(active) < 2:
            return None

        # 피처 행렬: (n_nodes, 3) — motion, amplitude, presence
        F = np.array([[n.motion_index, n.amplitude, n.presence_score] for n in active])
        F = F / (np.linalg.norm(F, axis=1, keepdims=True) + 1e-9)

        # 기하학적 편향 어텐션
        G = self._geometric_bias(active)
        scores = F @ F.T + G  # (n, n)
        scores /= math.sqrt(F.shape[1])
        weights = np.exp(scores).sum(axis=1)
        weights /= weights.sum() + 1e-9

        # 가중 융합
        fused_motion = float(np.average([n.motion_index for n in active], weights=weights))
        fused_presence = float(np.average([n.presence_score for n in active], weights=weights))
        fused_x = float(np.average([n.x for n in active], weights=weights))
        fused_y = float(np.average([n.y for n in active], weights=weights))

        # 신뢰도: 노드 수 + 어텐션 분산 (균일할수록 낮음)
        entropy = -float(np.sum(weights * np.log(weights + 1e-9)))
        max_entropy = math.log(len(active))
        confidence = min(1.0, 0.5 + 0.3 * len(active) / 6.0 + 0.2 * (1 - entropy / (max_entropy + 1e-9)))

        return FusionResult(
            fused_motion=round(fused_motion, 3),
            fused_presence=round(fused_presence, 3),
            fused_position_x=round(fused_x, 1),
            fused_position_y=round(fused_y, 1),
            confidence=round(confidence, 3),
            contributing_nodes=len(active),
            attention_weights=[round(float(w), 3) for w in weights],
        )

    def get_status(self) -> dict:
        result = self.fuse()
        if result is None:
            return {"status": "insufficient_nodes", "contributing_nodes": len(self._node_features)}
        return {
            "fused_motion": result.fused_motion,
            "fused_presence": result.fused_presence,
            "position": {"x": result.fused_position_x, "y": result.fused_position_y},
            "confidence": result.confidence,
            "contributing_nodes": result.contributing_nodes,
            "attention_weights": result.attention_weights,
        }
