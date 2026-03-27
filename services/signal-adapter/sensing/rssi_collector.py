"""
RssiCollector — WiFi RSSI 시계열 수집 (Phase 3-11)

디바이스별 독립적인 circular buffer로 RSSI 값을 수집합니다.
- circular buffer (deque, 기본 500샘플)
- 디바이스별 독립 수집
- 정규화 + 이상치 제거 (IQR 기반)
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RssiSample:
    """단일 RSSI 측정 샘플."""

    timestamp: float   # UNIX epoch seconds
    rssi_dbm: float    # dBm
    device_id: str


class RssiCollector:
    """
    WiFi RSSI 시계열 수집기.

    Parameters
    ----------
    window_size : int
        디바이스당 circular buffer 크기 (기본 500샘플).
    outlier_iqr_factor : float
        IQR 기반 이상치 제거 계수 (기본 1.5).  0 이하이면 이상치 제거 비활성.
    """

    def __init__(
        self,
        window_size: int = 500,
        outlier_iqr_factor: float = 1.5,
    ) -> None:
        if window_size < 1:
            raise ValueError(f"window_size must be >= 1, got {window_size}")
        self._window_size = window_size
        self._iqr_factor = outlier_iqr_factor
        self._buffers: Dict[str, Deque[RssiSample]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def window_size(self) -> int:
        return self._window_size

    def push(self, device_id: str, rssi_dbm: float, timestamp: Optional[float] = None) -> None:
        """단일 RSSI 샘플을 해당 디바이스 버퍼에 추가합니다."""
        if timestamp is None:
            timestamp = time.time()
        sample = RssiSample(timestamp=timestamp, rssi_dbm=float(rssi_dbm), device_id=device_id)
        with self._lock:
            if device_id not in self._buffers:
                self._buffers[device_id] = deque(maxlen=self._window_size)
            self._buffers[device_id].append(sample)

    def get_samples(self, device_id: str, n: Optional[int] = None) -> List[RssiSample]:
        """
        디바이스의 수집된 샘플을 반환합니다.

        Parameters
        ----------
        device_id : str
        n : int, optional
            None이면 전체 버퍼, 정수이면 최근 n개.
        """
        with self._lock:
            buf = self._buffers.get(device_id)
            if buf is None:
                return []
            items = list(buf)
        if n is not None:
            items = items[-n:] if n < len(items) else items
        return items

    def get_rssi_array(
        self,
        device_id: str,
        n: Optional[int] = None,
        remove_outliers: bool = True,
    ) -> np.ndarray:
        """
        RSSI 값을 1-D numpy 배열로 반환합니다.

        Parameters
        ----------
        device_id : str
        n : int, optional
            최근 n개 샘플만 사용.
        remove_outliers : bool
            True이면 IQR 기반 이상치를 NaN으로 마스킹 후 제거.
        """
        samples = self.get_samples(device_id, n)
        if not samples:
            return np.array([], dtype=np.float64)

        arr = np.array([s.rssi_dbm for s in samples], dtype=np.float64)

        if remove_outliers and self._iqr_factor > 0 and len(arr) >= 4:
            arr = self._remove_outliers(arr)

        return arr

    def get_normalized(
        self,
        device_id: str,
        n: Optional[int] = None,
        remove_outliers: bool = True,
    ) -> np.ndarray:
        """
        RSSI를 [0, 1] 범위로 정규화하여 반환합니다.

        min-max 정규화를 적용합니다.
        신호 범위가 0이면 모두 0.5를 반환합니다.
        """
        arr = self.get_rssi_array(device_id, n, remove_outliers)
        if len(arr) == 0:
            return arr

        lo, hi = float(np.min(arr)), float(np.max(arr))
        span = hi - lo
        if span < 1e-9:
            return np.full_like(arr, 0.5)
        return (arr - lo) / span

    def device_ids(self) -> List[str]:
        """현재 수집 중인 디바이스 ID 목록을 반환합니다."""
        with self._lock:
            return list(self._buffers.keys())

    def sample_count(self, device_id: str) -> int:
        """디바이스의 현재 버퍼 내 샘플 수."""
        with self._lock:
            buf = self._buffers.get(device_id)
            return len(buf) if buf is not None else 0

    def clear(self, device_id: Optional[str] = None) -> None:
        """버퍼를 비웁니다. device_id가 None이면 전체 비웁니다."""
        with self._lock:
            if device_id is None:
                self._buffers.clear()
            elif device_id in self._buffers:
                self._buffers[device_id].clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _remove_outliers(self, arr: np.ndarray) -> np.ndarray:
        """IQR 기반 이상치를 제거하고 유효 값만 반환합니다."""
        q25, q75 = np.percentile(arr, [25.0, 75.0])
        iqr = q75 - q25
        fence = self._iqr_factor * iqr
        mask = (arr >= q25 - fence) & (arr <= q75 + fence)
        cleaned = arr[mask]
        # 너무 많이 제거되면 원본 반환 (50% 이상 제거 방지)
        if len(cleaned) < len(arr) // 2:
            logger.debug(
                "IQR outlier removal would drop >50%% of data; keeping original (%d samples).",
                len(arr),
            )
            return arr
        return cleaned
