"""
WiFi CSI 기반 포즈 추정 — 2단계 접근 (Phase C-3)

Stage 1: 규칙 기반 6종 자세 분류
  - standing:   motion_index < 0.1, breathing_rate 정상, 수직 도플러 패턴
  - sitting:    motion_index < 0.08, 수직 속도 낮음, 횡방향 모션 낮음
  - lying:      motion_index < 0.05, breathing_rate 감소, 매우 낮은 도플러
  - walking:    motion_index 0.2~0.8, 주기적 도플러 패턴 (2Hz 근방)
  - exercising: motion_index > 0.8, 고주파 도플러, 빈번한 스파이크
  - fallen:     갑작스러운 motion spike 후 motion < 0.05 지속 (낙상 패턴)

Stage 2 (스캐폴드): DensePose 헤드를 통한 관절 각도 범위 추정
  - 팔 올림/내림 (상체 모션 에너지)
  - 무릎 굽힘 (하체 도플러 패턴)
  → 현재는 규칙 기반 근사만 구현, 딥러닝 헤드는 스캐폴드
"""
import numpy as np
from dataclasses import dataclass, field
from collections import deque
from typing import Optional
import time

POSE_CLASSES = ["standing", "sitting", "lying", "walking", "exercising", "fallen"]


@dataclass
class JointAngleEstimate:
    """관절 각도 근사 추정."""
    left_arm_raise: float = 0.0    # 0=내림, 1=완전 올림
    right_arm_raise: float = 0.0
    left_knee_bend: float = 0.0    # 0=펴짐, 1=완전 굽힘
    right_knee_bend: float = 0.0
    torso_lean: float = 0.0        # -1=앞, 0=수직, 1=뒤


@dataclass
class PoseEstimate:
    pose_class: str                 # 6종 중 하나
    confidence: float               # 0~1
    joint_angles: JointAngleEstimate
    motion_index: float
    breathing_rate: float
    doppler_frequency: float        # 주요 도플러 주파수 Hz
    timestamp: str


class WiFiPoseEstimator:
    """WiFi CSI 기반 6종 자세 분류 + 관절 각도 근사."""

    HISTORY_SIZE = 30  # 약 3초분 (10Hz 처리 가정)
    FALLEN_SPIKE_THRESHOLD = 1.5
    FALLEN_QUIET_THRESHOLD = 0.08
    FALLEN_QUIET_DURATION = 5       # 낙상 후 5프레임 이상 조용해야

    def __init__(self):
        # 디바이스별 히스토리
        self._motion_history: dict[str, deque] = {}
        self._pose_history: dict[str, deque] = {}
        self._fallen_candidates: dict[str, int] = {}  # 낙상 후 조용한 프레임 수
        self._last_estimate: dict[str, PoseEstimate] = {}

    def update(self, device_id: str, motion_index: float, breathing_rate: float,
               velocity: float, heart_rate: float, amplitude: list[float],
               timestamp: str) -> PoseEstimate:
        """새 CSI 프레임으로 포즈 추정 업데이트."""
        if device_id not in self._motion_history:
            self._motion_history[device_id] = deque(maxlen=self.HISTORY_SIZE)
            self._pose_history[device_id] = deque(maxlen=10)
            self._fallen_candidates[device_id] = 0

        hist = self._motion_history[device_id]
        hist.append(motion_index)

        # 도플러 주파수 추정 (motion 히스토리 FFT)
        doppler_freq = self._estimate_doppler_freq(list(hist))

        # 관절 각도 추정
        joints = self._estimate_joints(motion_index, velocity, amplitude)

        # 낙상 감지 (스파이크 후 조용)
        if len(hist) >= 2:
            prev = list(hist)[-2]
            if prev < self.FALLEN_SPIKE_THRESHOLD and motion_index >= self.FALLEN_SPIKE_THRESHOLD:
                self._fallen_candidates[device_id] = self.FALLEN_QUIET_DURATION
            elif self._fallen_candidates[device_id] > 0:
                if motion_index < self.FALLEN_QUIET_THRESHOLD:
                    self._fallen_candidates[device_id] -= 1
                else:
                    self._fallen_candidates[device_id] = 0  # 움직이면 리셋

        is_fallen = (self._fallen_candidates[device_id] > 0 and
                     motion_index < self.FALLEN_QUIET_THRESHOLD)

        # 6종 분류
        pose_class, confidence = self._classify(
            motion_index=motion_index,
            breathing_rate=breathing_rate,
            doppler_freq=doppler_freq,
            velocity=velocity,
            is_fallen=is_fallen,
        )

        # 히스테리시스: 직전 포즈 유지 보정
        pose_hist = self._pose_history[device_id]
        if pose_hist:
            prev_pose = pose_hist[-1]
            if pose_class != prev_pose and confidence < 0.6:
                pose_class = prev_pose
                confidence = 0.45
        pose_hist.append(pose_class)

        estimate = PoseEstimate(
            pose_class=pose_class,
            confidence=round(confidence, 3),
            joint_angles=joints,
            motion_index=round(motion_index, 3),
            breathing_rate=round(breathing_rate, 1),
            doppler_frequency=round(doppler_freq, 2),
            timestamp=timestamp,
        )
        self._last_estimate[device_id] = estimate
        return estimate

    def _estimate_doppler_freq(self, motion_hist: list[float]) -> float:
        if len(motion_hist) < 8:
            return 0.0
        arr = np.array(motion_hist) - np.mean(motion_hist)
        fft = np.abs(np.fft.rfft(arr))
        freqs = np.fft.rfftfreq(len(arr), d=0.1)  # 10Hz 가정
        if len(fft) < 2:
            return 0.0
        peak_idx = int(np.argmax(fft[1:])) + 1  # DC 제외
        return float(freqs[peak_idx]) if peak_idx < len(freqs) else 0.0

    def _classify(self, motion_index: float, breathing_rate: float,
                  doppler_freq: float, velocity: float, is_fallen: bool
                  ) -> tuple[str, float]:
        if is_fallen:
            return "fallen", 0.85

        if motion_index > 0.8:
            return "exercising", min(0.9, 0.6 + motion_index * 0.2)

        if 0.2 <= motion_index <= 0.8 and 1.5 <= doppler_freq <= 3.0:
            return "walking", min(0.85, 0.5 + doppler_freq * 0.1)

        if motion_index < 0.05 and breathing_rate > 0 and breathing_rate < 16:
            return "lying", 0.75

        if motion_index < 0.08:
            return "sitting", 0.70

        return "standing", max(0.5, 0.8 - motion_index)

    def _estimate_joints(self, motion_index: float, velocity: float,
                         amplitude: list[float]) -> JointAngleEstimate:
        """관절 각도 근사 — 규칙 기반."""
        # 상체 에너지 (상위 서브캐리어) vs 하체 에너지 (하위 서브캐리어)
        if amplitude and len(amplitude) >= 4:
            half = len(amplitude) // 2
            upper_energy = float(np.mean(np.abs(amplitude[:half])))
            lower_energy = float(np.mean(np.abs(amplitude[half:])))
            arm_raise = float(np.clip(upper_energy / (lower_energy + 0.01) - 0.5, 0, 1))
            knee_bend = float(np.clip(lower_energy / (upper_energy + 0.01) - 0.5, 0, 1))
        else:
            arm_raise = knee_bend = 0.0

        torso = float(np.clip(velocity / 2.0, -1.0, 1.0)) if velocity else 0.0

        return JointAngleEstimate(
            left_arm_raise=arm_raise,
            right_arm_raise=arm_raise,
            left_knee_bend=knee_bend,
            right_knee_bend=knee_bend,
            torso_lean=torso,
        )

    def get_all(self) -> dict:
        result = {}
        for did, est in self._last_estimate.items():
            result[did] = {
                "pose": est.pose_class,
                "confidence": est.confidence,
                "motion_index": est.motion_index,
                "breathing_rate": est.breathing_rate,
                "doppler_freq": est.doppler_frequency,
                "joints": {
                    "left_arm_raise": round(est.joint_angles.left_arm_raise, 2),
                    "right_arm_raise": round(est.joint_angles.right_arm_raise, 2),
                    "left_knee_bend": round(est.joint_angles.left_knee_bend, 2),
                    "right_knee_bend": round(est.joint_angles.right_knee_bend, 2),
                    "torso_lean": round(est.joint_angles.torso_lean, 2),
                },
                "timestamp": est.timestamp,
            }
        return result


if __name__ == "__main__":
    est = WiFiPoseEstimator()
    for i in range(15):
        r = est.update("node-1", motion_index=0.05 + i * 0.05,
                       breathing_rate=15.0, velocity=0.1, heart_rate=72.0,
                       amplitude=[0.5] * 16, timestamp="2026-03-29T00:00:00")
        print(f"frame {i}: {r.pose_class} ({r.confidence:.2f})")
