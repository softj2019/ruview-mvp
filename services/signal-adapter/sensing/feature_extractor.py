"""
RssiFeatureExtractor — RSSI 시계열에서 특징 추출 (Phase 3-10)

시간 영역 통계 + 주파수 영역 특징 + CUSUM 변화점 감지를 제공합니다.

알고리즘:
- CUSUM (누적합) 변화점 감지
- 호흡 대역 (0.1-0.5 Hz) 에너지 추출
- 운동 대역 (0.5-2.0 Hz) 에너지 추출
- 분산, 피크-투-피크 특성 추출
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
from numpy.typing import NDArray
from scipy import fft as scipy_fft
from scipy import stats as scipy_stats

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 특징 컨테이너
# ---------------------------------------------------------------------------

@dataclass
class RssiFeatures:
    """추출된 RSSI 특징 컨테이너."""

    # 시간 영역
    mean: float = 0.0
    variance: float = 0.0
    std: float = 0.0
    skewness: float = 0.0
    kurtosis: float = 0.0
    peak_to_peak: float = 0.0      # 피크-투-피크 (range)
    iqr: float = 0.0               # 사분위 범위

    # 주파수 영역
    dominant_freq_hz: float = 0.0
    breathing_band_power: float = 0.0    # 0.1 - 0.5 Hz
    motion_band_power: float = 0.0       # 0.5 - 2.0 Hz
    total_spectral_power: float = 0.0

    # 변화점
    change_points: List[int] = field(default_factory=list)
    n_change_points: int = 0

    # 메타
    n_samples: int = 0
    sample_rate_hz: float = 0.0
    duration_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Feature extractor
# ---------------------------------------------------------------------------

class RssiFeatureExtractor:
    """
    RSSI 시계열에서 시간/주파수 영역 특징을 추출합니다.

    Parameters
    ----------
    sample_rate_hz : float
        샘플링 주파수 (Hz). 기본 10.0.
    cusum_threshold : float
        CUSUM 임계값 (std 단위). 기본 3.0.
    cusum_drift : float
        CUSUM drift 허용치 (std 단위). 기본 0.5.
    """

    BREATHING_BAND_LOW = 0.1   # Hz
    BREATHING_BAND_HIGH = 0.5  # Hz
    MOTION_BAND_LOW = 0.5      # Hz
    MOTION_BAND_HIGH = 2.0     # Hz

    def __init__(
        self,
        sample_rate_hz: float = 10.0,
        cusum_threshold: float = 3.0,
        cusum_drift: float = 0.5,
    ) -> None:
        if sample_rate_hz <= 0:
            raise ValueError(f"sample_rate_hz must be > 0, got {sample_rate_hz}")
        self._sample_rate = sample_rate_hz
        self._cusum_threshold = cusum_threshold
        self._cusum_drift = cusum_drift

    @property
    def sample_rate_hz(self) -> float:
        return self._sample_rate

    def extract_from_array(
        self,
        rssi: NDArray[np.float64],
        sample_rate_hz: Optional[float] = None,
    ) -> RssiFeatures:
        """
        numpy 배열에서 특징을 추출합니다.

        Parameters
        ----------
        rssi : ndarray
            1-D RSSI 시계열 (dBm).
        sample_rate_hz : float, optional
            샘플링 주파수. None이면 생성자 값 사용.
        """
        fs = sample_rate_hz if sample_rate_hz is not None else self._sample_rate
        n = len(rssi)

        if n < 4:
            logger.warning("특징 추출에 샘플이 부족합니다 (%d < 4).", n)
            return RssiFeatures(n_samples=n, sample_rate_hz=fs)

        duration = n / fs
        features = RssiFeatures(
            n_samples=n,
            sample_rate_hz=float(fs),
            duration_seconds=float(duration),
        )

        self._compute_time_domain(rssi, features)
        self._compute_frequency_domain(rssi, fs, features)
        self._compute_change_points(rssi, features)

        return features

    # ------------------------------------------------------------------
    # 시간 영역 특징
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_time_domain(
        rssi: NDArray[np.float64], features: RssiFeatures
    ) -> None:
        features.mean = float(np.mean(rssi))
        features.variance = float(np.var(rssi, ddof=1)) if len(rssi) > 1 else 0.0
        features.std = float(np.std(rssi, ddof=1)) if len(rssi) > 1 else 0.0
        features.peak_to_peak = float(np.ptp(rssi))

        if features.std < 1e-12:
            features.skewness = 0.0
            features.kurtosis = 0.0
        else:
            features.skewness = (
                float(scipy_stats.skew(rssi, bias=False)) if len(rssi) > 2 else 0.0
            )
            features.kurtosis = (
                float(scipy_stats.kurtosis(rssi, bias=False)) if len(rssi) > 3 else 0.0
            )

        q75, q25 = np.percentile(rssi, [75.0, 25.0])
        features.iqr = float(q75 - q25)

    # ------------------------------------------------------------------
    # 주파수 영역 특징
    # ------------------------------------------------------------------

    @classmethod
    def _compute_frequency_domain(
        cls,
        rssi: NDArray[np.float64],
        sample_rate: float,
        features: RssiFeatures,
    ) -> None:
        n = len(rssi)
        if n < 4:
            return

        # DC 제거 + Hann window
        signal = rssi - np.mean(rssi)
        windowed = signal * np.hanning(n)

        # real FFT
        fft_vals = scipy_fft.rfft(windowed)
        freqs = scipy_fft.rfftfreq(n, d=1.0 / sample_rate)

        # PSD (정규화)
        psd = (np.abs(fft_vals) ** 2) / n

        # DC 제거 (인덱스 0)
        if len(freqs) < 2:
            return
        freqs_ac = freqs[1:]
        psd_ac = psd[1:]

        features.total_spectral_power = float(np.sum(psd_ac))

        if len(psd_ac) > 0:
            peak_idx = int(np.argmax(psd_ac))
            features.dominant_freq_hz = float(freqs_ac[peak_idx])

        features.breathing_band_power = float(
            _band_power(freqs_ac, psd_ac, cls.BREATHING_BAND_LOW, cls.BREATHING_BAND_HIGH)
        )
        features.motion_band_power = float(
            _band_power(freqs_ac, psd_ac, cls.MOTION_BAND_LOW, cls.MOTION_BAND_HIGH)
        )

    # ------------------------------------------------------------------
    # CUSUM 변화점 감지
    # ------------------------------------------------------------------

    def _compute_change_points(
        self, rssi: NDArray[np.float64], features: RssiFeatures
    ) -> None:
        """
        CUSUM 알고리즘으로 변화점을 감지합니다.

        신호 평균에서의 누적 이탈을 추적하여 급격한 평균 변화를 감지합니다.
        """
        if len(rssi) < 4:
            return

        std_val = float(np.std(rssi, ddof=1))
        if std_val < 1e-12:
            features.change_points = []
            features.n_change_points = 0
            return

        threshold = self._cusum_threshold * std_val
        drift = self._cusum_drift * std_val
        mean_val = float(np.mean(rssi))

        change_points = cusum_detect(rssi, mean_val, threshold, drift)
        features.change_points = change_points
        features.n_change_points = len(change_points)


# ---------------------------------------------------------------------------
# 헬퍼 함수
# ---------------------------------------------------------------------------

def _band_power(
    freqs: NDArray[np.float64],
    psd: NDArray[np.float64],
    low_hz: float,
    high_hz: float,
) -> float:
    """지정 주파수 대역 [low_hz, high_hz] 내 PSD 합계."""
    mask = (freqs >= low_hz) & (freqs <= high_hz)
    return float(np.sum(psd[mask]))


def cusum_detect(
    signal: NDArray[np.float64],
    target: float,
    threshold: float,
    drift: float,
) -> List[int]:
    """
    CUSUM (cumulative sum) 변화점 감지.

    상향/하향 양방향 평균 이동을 감지합니다.

    Parameters
    ----------
    signal : ndarray
        1-D 분석 대상 신호.
    target : float
        신호의 기대 평균.
    threshold : float
        변화점 선언 임계값.
    drift : float
        편차 누적 전 허용 drift.

    Returns
    -------
    list of int
        변화점이 감지된 인덱스 목록.
    """
    n = len(signal)
    s_pos = 0.0
    s_neg = 0.0
    change_points: List[int] = []

    for i in range(n):
        dev = signal[i] - target
        s_pos = max(0.0, s_pos + dev - drift)
        s_neg = max(0.0, s_neg - dev - drift)

        if s_pos > threshold or s_neg > threshold:
            change_points.append(i)
            # 감지 후 리셋하여 후속 변화점 탐색
            s_pos = 0.0
            s_neg = 0.0

    return change_points

