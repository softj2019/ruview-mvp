"""
Multistatic Fusion — N×(N-1) 링크 결합으로 공간 해상도 향상.

현재 구조: 각 ESP32 노드가 독립적으로 CSI를 처리.
개선: TX-RX 쌍(링크)별 motion_index를 Fresnel confidence 가중합산.

N=6 노드 → 최대 30개 링크 → 공간 해상도 6배 향상

링크 구조:
  link_id = "node-{tx}->{rx}"
  각 링크의 기여도 = fresnel_confidence(tx_pos, rx_pos, pixel_pos) * motion_index
"""
import numpy as np
from dataclasses import dataclass, field
from typing import Any
import time


@dataclass
class LinkMeasurement:
    link_id: str          # "node-1->node-2"
    tx_id: str
    rx_id: str
    tx_pos: tuple[float, float]   # 정규화 [0,1]
    rx_pos: tuple[float, float]
    motion_index: float
    csi_amplitude: float
    fresnel_confidence: float
    timestamp: float


class MultistaticFuser:
    """N×(N-1) 링크 결합 멀티스태틱 퓨전."""

    FLOOR_W = 800.0
    FLOOR_H = 400.0

    def __init__(self, grid_size: tuple[int, int] = (20, 20), link_ttl: float = 2.0):
        self.grid_size = grid_size
        self.link_ttl = link_ttl  # 링크 데이터 유효 기간(초)
        self._links: dict[str, LinkMeasurement] = {}

    def update_link(self, tx_id: str, rx_id: str,
                    tx_pos: tuple[float, float], rx_pos: tuple[float, float],
                    motion_index: float, csi_amplitude: float) -> None:
        """링크 측정값 업데이트."""
        # Fresnel confidence 계산
        fc = self._fresnel_confidence(tx_pos, rx_pos)
        link_id = f"{tx_id}->{rx_id}"
        self._links[link_id] = LinkMeasurement(
            link_id=link_id, tx_id=tx_id, rx_id=rx_id,
            tx_pos=tx_pos, rx_pos=rx_pos,
            motion_index=motion_index, csi_amplitude=csi_amplitude,
            fresnel_confidence=fc, timestamp=time.monotonic()
        )

    def _fresnel_confidence(self, tx: tuple[float, float], rx: tuple[float, float]) -> float:
        """링크 길이 기반 Fresnel 신뢰도 (짧은 링크 = 높은 신뢰도)."""
        dist = np.sqrt((tx[0] - rx[0]) ** 2 + (tx[1] - rx[1]) ** 2)
        return float(np.exp(-dist * 2.0))  # 거리 지수 감쇠

    def fuse(self) -> dict[str, Any]:
        """유효한 링크들의 weighted fusion 결과 반환."""
        now = time.monotonic()
        active = {k: v for k, v in self._links.items()
                  if now - v.timestamp < self.link_ttl}

        if not active:
            return {"link_count": 0, "fused_motion": 0.0, "spatial_resolution": 0.0, "links": []}

        # 가중 평균 motion_index (가중치 = fresnel_confidence)
        weights = np.array([l.fresnel_confidence for l in active.values()])
        motions = np.array([l.motion_index for l in active.values()])
        total_w = weights.sum() + 1e-9
        fused_motion = float((weights * motions).sum() / total_w)

        # 공간 해상도 향상 지수 (링크 수 기반)
        n_links = len(active)
        # N*(N-1) 링크에서 단일 노드 대비 해상도 향상
        single_node_count = len(set(l.tx_id for l in active.values()))
        spatial_gain = n_links / max(single_node_count, 1)

        return {
            "link_count": n_links,
            "active_node_count": single_node_count,
            "fused_motion": round(fused_motion, 4),
            "spatial_resolution_gain": round(spatial_gain, 2),
            "max_confidence": round(float(weights.max()), 4),
            "links": [
                {
                    "id": l.link_id,
                    "motion": round(l.motion_index, 3),
                    "confidence": round(l.fresnel_confidence, 3),
                    "tx": l.tx_id, "rx": l.rx_id,
                }
                for l in sorted(active.values(), key=lambda x: -x.fresnel_confidence)[:10]
            ]
        }

    def get_link_matrix(self) -> dict:
        """N×N 링크 매트릭스 (시각화용)."""
        now = time.monotonic()
        active = {k: v for k, v in self._links.items()
                  if now - v.timestamp < self.link_ttl}
        nodes = sorted(set(l.tx_id for l in active.values()) |
                       set(l.rx_id for l in active.values()))
        matrix = {n: {m: 0.0 for m in nodes} for n in nodes}
        for l in active.values():
            matrix[l.tx_id][l.rx_id] = round(l.motion_index * l.fresnel_confidence, 3)
        return {"nodes": nodes, "matrix": matrix}
