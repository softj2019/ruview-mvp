"""
SpotFi-inspired 위치 추정 — ESP32-S3 단일 안테나 최적화.

단일 안테나 제약:
  - 순수 AoA 불가 (복수 안테나 필요)
  - 대신: CSI 진폭 기반 거리 추정 + 최소자승 삼각측량

알고리즘:
1. 진폭 → Friis 경로손실 모델로 거리 추정
2. Phase slope (dφ/dk) → TOA → 거리 보정
3. 최소자승 삼각측량으로 위치 추정
4. Residual 기반 신뢰도 계산

참조:
  SpotFi: Kotaru et al., SIGCOMM 2015
  FILA: Liu et al., INFOCOM 2012
  IEEE 802.11az Next Generation Positioning
"""
import math
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
try:
    from scipy.optimize import minimize as _scipy_minimize
    _SCIPY_AVAILABLE = True
except ImportError:
    _SCIPY_AVAILABLE = False

WIFI_FREQ_HZ = 5.8e9
SPEED_OF_LIGHT = 3e8
WAVELENGTH = SPEED_OF_LIGHT / WIFI_FREQ_HZ   # ~0.052m
SUBCARRIER_SPACING_HZ = 312_500.0             # 802.11n/ac 서브캐리어 간격
FLOOR_W_METERS = 10.0                         # 800px = 10m
PIXELS_PER_METER = 80.0                       # 800/10
PATH_LOSS_EXP = 2.5                           # 실내 경로손실 지수
REF_DISTANCE_M = 1.0                          # 기준 거리 1m
REF_AMPLITUDE = 1.0                           # 기준 진폭 (정규화)


@dataclass
class NodePhaseData:
    node_id: str
    x: float           # 플로어맵 픽셀 (0-800)
    y: float           # 플로어맵 픽셀 (0-400)
    phase_mean: float  # 원형 평균 위상 (라디안)
    phase_slope: float # 서브캐리어 위상 기울기 (TOA 추정용)
    amplitude: float   # 평균 진폭
    dist_estimate: float  # 진폭 기반 거리 추정 (m)
    timestamp: float


@dataclass
class PositionEstimate:
    x: float
    y: float
    confidence: float
    method: str
    contributing_nodes: int


class AoAEstimator:
    """단일 안테나 ESP32-S3용 CSI 기반 위치 추정."""

    FLOOR_W = 800.0
    FLOOR_H = 400.0

    def __init__(self, data_ttl: float = 3.0):
        self.data_ttl = data_ttl
        self._node_data: dict[str, NodePhaseData] = {}

    def _estimate_distance(self, amplitudes: list[float]) -> float:
        """Friis 경로손실 모델로 거리 추정."""
        if not amplitudes:
            return 5.0  # 기본값 5m
        amp = float(np.median(np.abs(amplitudes)))
        if amp < 1e-6:
            return 5.0
        # d = d0 * (A_ref / amp)^(1/n)
        ratio = REF_AMPLITUDE / (amp + 1e-9)
        dist = REF_DISTANCE_M * (ratio ** (1.0 / PATH_LOSS_EXP))
        return float(np.clip(dist, 0.3, 12.0))  # 0.3m ~ 12m 클리핑

    def _estimate_phase_slope(self, phases: list[float]) -> float:
        """서브캐리어 위상 기울기 추정 (선형 회귀)."""
        n = len(phases)
        if n < 4:
            return 0.0
        x = np.arange(n, dtype=float)
        y = np.unwrap(np.array(phases, dtype=float))
        # 선형 회귀: y = slope * x + intercept
        slope = float(np.polyfit(x, y, 1)[0])
        return slope

    def update_node(self, node_id: str, x: float, y: float,
                    phases: list[float], amplitudes: list[float]) -> None:
        if not phases and not amplitudes:
            return
        phase_mean = float(np.angle(np.mean(np.exp(1j * np.array(phases))))) if phases else 0.0
        phase_slope = self._estimate_phase_slope(phases)
        amp_mean = float(np.mean(np.abs(amplitudes))) if amplitudes else 0.0
        dist = self._estimate_distance(amplitudes)

        # Phase slope으로 TOA 보정: τ = -slope / (2π * Δf)
        if abs(phase_slope) > 1e-6:
            toa_sec = -phase_slope / (2 * math.pi * SUBCARRIER_SPACING_HZ)
            toa_dist = abs(toa_sec) * SPEED_OF_LIGHT
            # 앙상블: 진폭 추정 70% + TOA 추정 30% (TOA 신뢰도 낮음)
            if 0.3 <= toa_dist <= 12.0:
                dist = 0.7 * dist + 0.3 * toa_dist

        self._node_data[node_id] = NodePhaseData(
            node_id=node_id, x=x, y=y,
            phase_mean=phase_mean, phase_slope=phase_slope,
            amplitude=amp_mean, dist_estimate=dist,
            timestamp=time.monotonic()
        )

    def _trilaterate(self, nodes: list[NodePhaseData]) -> tuple[float, float, float]:
        """비선형 최소자승 삼각측량. 반환: (x_m, y_m, residual)

        scipy 사용 시: Nelder-Mead 비선형 최적화 (정확도 우선)
        scipy 없을 시: 진폭 가중 평균 fallback
        """
        scale = FLOOR_W_METERS / self.FLOOR_W
        positions = np.array([[n.x * scale, n.y * scale] for n in nodes])
        distances = np.array([n.dist_estimate for n in nodes])
        amplitudes = np.array([n.amplitude for n in nodes])
        weights = amplitudes / (amplitudes.sum() + 1e-9)

        # 초기 추정값: 진폭 가중 평균 (중심 근처 수렴)
        x_init = float(np.average(positions[:, 0], weights=weights))
        y_init = float(np.average(positions[:, 1], weights=weights))

        def cost(p: np.ndarray) -> float:
            dists = np.sqrt((positions[:, 0] - p[0])**2 + (positions[:, 1] - p[1])**2)
            return float(np.sum(weights * (dists - distances)**2))

        if _SCIPY_AVAILABLE:
            try:
                res = _scipy_minimize(cost, [x_init, y_init], method="Nelder-Mead",
                                      options={"xatol": 0.05, "fatol": 1e-4, "maxiter": 500})
                x_m, y_m = float(res.x[0]), float(res.x[1])
                dists_est = np.sqrt((positions[:, 0] - x_m)**2 + (positions[:, 1] - y_m)**2)
                residual = float(np.sqrt(np.mean((dists_est - distances)**2)))
                return x_m, y_m, residual
            except Exception:
                pass

        # fallback: 진폭 가중 평균 (scipy 없거나 최적화 실패 시)
        return x_init, y_init, 999.0

    def estimate_position(self) -> PositionEstimate:
        now = time.monotonic()
        active = {k: v for k, v in self._node_data.items()
                  if now - v.timestamp < self.data_ttl and v.amplitude > 0.01}

        if not active:
            return PositionEstimate(x=400.0, y=200.0, confidence=0.0,
                                    method="fallback", contributing_nodes=0)
        if len(active) == 1:
            nd = next(iter(active.values()))
            return PositionEstimate(x=nd.x, y=nd.y, confidence=0.1,
                                    method="single_node", contributing_nodes=1)

        nodes = list(active.values())
        # 진폭 내림차순 정렬 → 신뢰도 높은 노드 우선
        nodes.sort(key=lambda n: n.amplitude, reverse=True)

        x_m, y_m, residual = self._trilaterate(nodes)
        scale = FLOOR_W_METERS / self.FLOOR_W
        x_pix = float(np.clip(x_m / scale, 0, self.FLOOR_W))
        y_pix = float(np.clip(y_m / scale, 0, self.FLOOR_H))

        # 신뢰도: residual 기반 (작을수록 좋음) + 노드 수 보너스
        node_bonus = min(0.2, (len(nodes) - 2) * 0.05)
        confidence = float(np.clip(math.exp(-residual / 2.0) + node_bonus, 0.0, 1.0))

        method = "triangulation" if len(nodes) >= 3 else "two_node"
        return PositionEstimate(
            x=x_pix, y=y_pix,
            confidence=round(confidence, 3),
            method=method,
            contributing_nodes=len(nodes)
        )

    def get_all_estimates(self) -> dict:
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
                 "amplitude": round(n.amplitude, 3),
                 "phase": round(n.phase_mean, 3),
                 "dist_m": round(n.dist_estimate, 2)}
                for n in active.values()
            ]
        }
