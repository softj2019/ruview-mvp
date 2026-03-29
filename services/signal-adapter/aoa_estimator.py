"""
SpotFi 기반 AoA(도래각) 추정 + 다중 노드 삼각측량으로 위치 추정.

ESP32-S3 단일 안테나 제약으로 순수 AoA 불가.
대신: 다중 노드의 CSI 위상 차이 → 상대 AoA → 삼각측량 → 위치 추정.

알고리즘:
1. 노드 쌍(i,j)의 위상 차이 Δφ = φ_i - φ_j
2. 위상 차이로부터 상대 도래각 추정: θ = arcsin(Δφ * λ / (2π * d))
   (d = 노드 간 거리, λ = 파장)
3. 각 노드 쌍의 방향각 선 교차점 → 위치 추정
4. 다중 교차점의 가중 평균 (신호 품질 가중치)
"""
import math
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np

WIFI_FREQ_HZ = 5.8e9          # 5.8 GHz
SPEED_OF_LIGHT = 3e8
WAVELENGTH = SPEED_OF_LIGHT / WIFI_FREQ_HZ   # ~0.052m


@dataclass
class NodePhaseData:
    node_id: str
    x: float           # 플로어맵 픽셀 (0-800)
    y: float           # 플로어맵 픽셀 (0-400)
    phase_mean: float  # 평균 위상 (라디안)
    amplitude: float
    timestamp: float


@dataclass
class PositionEstimate:
    x: float           # 추정 위치 픽셀
    y: float
    confidence: float  # 0~1
    method: str        # "triangulation" | "single_node" | "fallback"
    contributing_nodes: int


class AoAEstimator:
    """다중 노드 위상 차이 기반 위치 추정."""

    FLOOR_W = 800.0
    FLOOR_H = 400.0
    NODE_SEPARATION = 0.5   # 노드 간 가상 안테나 간격 (m)

    def __init__(self, data_ttl: float = 3.0):
        self.data_ttl = data_ttl
        self._node_data: dict[str, NodePhaseData] = {}

    def update_node(self, node_id: str, x: float, y: float,
                    phases: list[float], amplitudes: list[float]) -> None:
        """노드 위상/진폭 데이터 업데이트."""
        if not phases:
            return
        phase_mean = float(np.angle(np.mean(np.exp(1j * np.array(phases)))))
        amp_mean = float(np.mean(np.abs(amplitudes))) if amplitudes else 0.0
        self._node_data[node_id] = NodePhaseData(
            node_id=node_id, x=x, y=y,
            phase_mean=phase_mean, amplitude=amp_mean,
            timestamp=time.monotonic()
        )

    def estimate_position(self) -> PositionEstimate:
        """현재 데이터로 위치 추정."""
        now = time.monotonic()
        active = {k: v for k, v in self._node_data.items()
                  if now - v.timestamp < self.data_ttl and v.amplitude > 0.01}

        if len(active) < 2:
            # 노드 1개: 노드 위치를 반환 (fallback)
            if active:
                nd = next(iter(active.values()))
                return PositionEstimate(x=nd.x, y=nd.y, confidence=0.1,
                                        method="fallback", contributing_nodes=1)
            return PositionEstimate(x=400.0, y=200.0, confidence=0.0,
                                    method="fallback", contributing_nodes=0)

        # 노드 쌍별 위상 차이 → 상대 AoA → 방향선
        intersection_points: list[tuple[float, float]] = []
        weights: list[float] = []

        nodes = list(active.values())
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                ni, nj = nodes[i], nodes[j]
                result = self._pairwise_intersection(ni, nj)
                if result is not None:
                    px, py, w = result
                    if 0 <= px <= self.FLOOR_W and 0 <= py <= self.FLOOR_H:
                        intersection_points.append((px, py))
                        weights.append(w)

        if not intersection_points:
            # 진폭 가중 평균 위치
            pts = np.array([[n.x, n.y] for n in nodes])
            ws = np.array([n.amplitude for n in nodes])
            ws /= ws.sum() + 1e-9
            cx, cy = (pts * ws[:, None]).sum(axis=0)
            return PositionEstimate(x=float(cx), y=float(cy), confidence=0.2,
                                    method="single_node", contributing_nodes=len(nodes))

        pts = np.array(intersection_points)
        ws = np.array(weights)
        ws /= ws.sum() + 1e-9
        cx, cy = (pts * ws[:, None]).sum(axis=0)

        # 신뢰도: 교차점 밀집도 (분산 역수)
        spread = float(np.sqrt(np.var(pts[:, 0]) + np.var(pts[:, 1])))
        confidence = float(np.clip(1.0 / (1.0 + spread / 100.0), 0.0, 1.0))

        return PositionEstimate(
            x=float(cx), y=float(cy),
            confidence=round(confidence, 3),
            method="triangulation",
            contributing_nodes=len(nodes)
        )

    def _pairwise_intersection(self, ni: NodePhaseData, nj: NodePhaseData
                                ) -> Optional[tuple[float, float, float]]:
        """두 노드 위상 차이로 교차점 (x, y, weight) 계산."""
        try:
            # 픽셀→미터 변환 (800px = 10m 가정)
            scale = 10.0 / self.FLOOR_W
            xi, yi = ni.x * scale, ni.y * scale
            xj, yj = nj.x * scale, nj.y * scale

            # 노드 간 방향각
            dx, dy = xj - xi, yj - yi
            baseline_angle = math.atan2(dy, dx)
            baseline_len = math.sqrt(dx ** 2 + dy ** 2) + 1e-6

            # 위상 차이 → AoA (단순 근사)
            delta_phi = ni.phase_mean - nj.phase_mean
            delta_phi = (delta_phi + math.pi) % (2 * math.pi) - math.pi  # [-π, π] 정규화
            sin_arg = float(np.clip(
                delta_phi * WAVELENGTH / (2 * math.pi * self.NODE_SEPARATION),
                -1.0, 1.0
            ))
            aoa_i = math.asin(sin_arg)

            # 노드 i에서 방향각 = baseline_angle + aoa_i 방향 직선
            # 노드 j에서 방향각 = baseline_angle + π - aoa_i
            angle_i = baseline_angle + aoa_i
            angle_j = baseline_angle + math.pi - aoa_i

            # 두 직선 교차점
            # 직선: P = (xi,yi) + t*(cos(ai), sin(ai))
            #       Q = (xj,yj) + s*(cos(aj), sin(aj))
            cos_i, sin_i = math.cos(angle_i), math.sin(angle_i)
            cos_j, sin_j = math.cos(angle_j), math.sin(angle_j)

            # 크라머 법칙
            det = cos_i * (-sin_j) - sin_i * (-cos_j)
            if abs(det) < 1e-6:
                return None
            t = ((xj - xi) * (-sin_j) - (yj - yi) * (-cos_j)) / det
            px = xi + t * cos_i
            py = yi + t * sin_i

            # 미터 → 픽셀
            px_pix = px / scale
            py_pix = py / scale

            # 신뢰도 가중치 = 두 노드 진폭 곱 * baseline 길이 역수
            weight = (ni.amplitude * nj.amplitude) / (baseline_len + 0.1)

            return (px_pix, py_pix, weight)
        except Exception:
            return None

    def get_all_estimates(self) -> dict:
        """전체 추정 결과 직렬화."""
        est = self.estimate_position()
        now = time.monotonic()
        active = {k: v for k, v in self._node_data.items()
                  if now - v.timestamp < self.data_ttl}
        return {
            "position": {"x": round(est.x, 1), "y": round(est.y, 1)},
            "confidence": est.confidence,
            "method": est.method,
            "contributing_nodes": est.contributing_nodes,
            "active_nodes": len(active),
            "node_data": [
                {"id": n.node_id, "x": n.x, "y": n.y,
                 "amplitude": round(n.amplitude, 3), "phase": round(n.phase_mean, 3)}
                for n in active.values()
            ]
        }
