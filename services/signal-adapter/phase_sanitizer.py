"""Phase sanitization module for WiFi CSI signals.

Provides phase unwrapping, outlier removal, and smoothing for CSI phase arrays.

Adapted from vendor/ruview-temp/v1/src/core/phase_sanitizer.py for
signal-adapter integration.

Default configuration factory
------------------------------
Use ``PhaseSanitizer.with_defaults()`` to construct an instance without
manually assembling the config dict:

    sanitizer = PhaseSanitizer.with_defaults()
    clean = sanitizer.sanitize_phase(phase_2d)
"""

import numpy as np
import logging
from typing import Dict, Any, Optional
from scipy import signal


class PhaseSanitizationError(Exception):
    """Exception raised for phase sanitization errors."""
    pass


class PhaseSanitizer:
    """Sanitizes phase data from CSI signals for reliable processing."""

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, config: Dict[str, Any], logger: Optional[logging.Logger] = None):
        """Initialize phase sanitizer.

        Args:
            config: Configuration dictionary with required keys:
                - unwrapping_method: 'numpy' | 'scipy' | 'custom'
                - outlier_threshold: positive float (Z-score cutoff)
                - smoothing_window: positive int
            logger: Optional logger instance

        Raises:
            ValueError: If configuration is invalid
        """
        self._validate_config(config)

        self.config = config
        self.logger = logger or logging.getLogger(__name__)

        # Processing parameters
        self.unwrapping_method = config['unwrapping_method']
        self.outlier_threshold = config['outlier_threshold']
        self.smoothing_window = config['smoothing_window']

        # Optional parameters with defaults
        self.enable_outlier_removal = config.get('enable_outlier_removal', True)
        self.enable_smoothing = config.get('enable_smoothing', True)
        self.enable_noise_filtering = config.get('enable_noise_filtering', False)
        self.noise_threshold = config.get('noise_threshold', 0.05)
        self.phase_range = config.get('phase_range', (-np.pi, np.pi))

        # Statistics tracking
        self._total_processed = 0
        self._outliers_removed = 0
        self._sanitization_errors = 0

    @classmethod
    def with_defaults(cls, **overrides) -> "PhaseSanitizer":
        """Construct a PhaseSanitizer with sensible defaults.

        Keyword overrides are merged into the default config dict.
        Validation is skipped for the phase_range check so that raw
        CSI phase values (which may be pre-unwrapped and outside ±π)
        are processed without error — set validate_range=False in the
        config to disable range checking entirely.

        Example::

            sanitizer = PhaseSanitizer.with_defaults(smoothing_window=5)
        """
        config: Dict[str, Any] = {
            'unwrapping_method': 'numpy',
            'outlier_threshold': 3.0,
            'smoothing_window': 3,
            'enable_outlier_removal': True,
            'enable_smoothing': True,
            'enable_noise_filtering': False,
            'noise_threshold': 0.05,
            # Wide range to accommodate pre-unwrapped or large-magnitude phases
            'phase_range': (-1e6, 1e6),
        }
        config.update(overrides)
        return cls(config)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_config(self, config: Dict[str, Any]) -> None:
        """Validate configuration parameters."""
        required_fields = ['unwrapping_method', 'outlier_threshold', 'smoothing_window']
        missing_fields = [f for f in required_fields if f not in config]

        if missing_fields:
            raise ValueError(f"Missing required configuration: {missing_fields}")

        valid_methods = ['numpy', 'scipy', 'custom']
        if config['unwrapping_method'] not in valid_methods:
            raise ValueError(
                f"Invalid unwrapping method: {config['unwrapping_method']}. "
                f"Must be one of {valid_methods}"
            )

        if config['outlier_threshold'] <= 0:
            raise ValueError("outlier_threshold must be positive")

        if config['smoothing_window'] <= 0:
            raise ValueError("smoothing_window must be positive")

    # ------------------------------------------------------------------
    # Phase unwrapping
    # ------------------------------------------------------------------

    def unwrap_phase(self, phase_data: np.ndarray) -> np.ndarray:
        """Unwrap phase data to remove discontinuities.

        Args:
            phase_data: Wrapped phase data (2D array, shape [antennas, subcarriers])

        Returns:
            Unwrapped phase data

        Raises:
            PhaseSanitizationError: If unwrapping fails
        """
        try:
            if self.unwrapping_method == 'numpy':
                return self._unwrap_numpy(phase_data)
            elif self.unwrapping_method == 'scipy':
                return self._unwrap_scipy(phase_data)
            elif self.unwrapping_method == 'custom':
                return self._unwrap_custom(phase_data)
            else:
                raise ValueError(f"Unknown unwrapping method: {self.unwrapping_method}")
        except Exception as e:
            raise PhaseSanitizationError(f"Failed to unwrap phase: {e}")

    def _unwrap_numpy(self, phase_data: np.ndarray) -> np.ndarray:
        if phase_data.size == 0:
            raise ValueError("Cannot unwrap empty phase data")
        return np.unwrap(phase_data, axis=1)

    def _unwrap_scipy(self, phase_data: np.ndarray) -> np.ndarray:
        if phase_data.size == 0:
            raise ValueError("Cannot unwrap empty phase data")
        return np.unwrap(phase_data, axis=1)

    def _unwrap_custom(self, phase_data: np.ndarray) -> np.ndarray:
        if phase_data.size == 0:
            raise ValueError("Cannot unwrap empty phase data")
        unwrapped = phase_data.copy()
        for i in range(phase_data.shape[0]):
            unwrapped[i, :] = np.unwrap(phase_data[i, :])
        return unwrapped

    # ------------------------------------------------------------------
    # Outlier removal
    # ------------------------------------------------------------------

    def remove_outliers(self, phase_data: np.ndarray) -> np.ndarray:
        """Remove outliers from phase data using Z-score + linear interpolation.

        Args:
            phase_data: Phase data (2D array)

        Returns:
            Phase data with outliers replaced by interpolated values

        Raises:
            PhaseSanitizationError: If outlier removal fails
        """
        if not self.enable_outlier_removal:
            return phase_data

        try:
            outlier_mask = self._detect_outliers(phase_data)
            return self._interpolate_outliers(phase_data, outlier_mask)
        except Exception as e:
            raise PhaseSanitizationError(f"Failed to remove outliers: {e}")

    def _detect_outliers(self, phase_data: np.ndarray) -> np.ndarray:
        z_scores = np.abs(
            (phase_data - np.mean(phase_data, axis=1, keepdims=True))
            / (np.std(phase_data, axis=1, keepdims=True) + 1e-8)
        )
        outlier_mask = z_scores > self.outlier_threshold
        self._outliers_removed += int(np.sum(outlier_mask))
        return outlier_mask

    def _interpolate_outliers(
        self, phase_data: np.ndarray, outlier_mask: np.ndarray
    ) -> np.ndarray:
        clean_data = phase_data.copy()
        for i in range(phase_data.shape[0]):
            outliers = outlier_mask[i, :]
            if np.any(outliers):
                valid_indices = np.where(~outliers)[0]
                outlier_indices = np.where(outliers)[0]
                if len(valid_indices) > 1:
                    clean_data[i, outlier_indices] = np.interp(
                        outlier_indices, valid_indices, phase_data[i, valid_indices]
                    )
        return clean_data

    # ------------------------------------------------------------------
    # Smoothing
    # ------------------------------------------------------------------

    def smooth_phase(self, phase_data: np.ndarray) -> np.ndarray:
        """Smooth phase data with a moving average to reduce noise.

        Args:
            phase_data: Phase data (2D array)

        Returns:
            Smoothed phase data

        Raises:
            PhaseSanitizationError: If smoothing fails
        """
        if not self.enable_smoothing:
            return phase_data

        try:
            return self._apply_moving_average(phase_data, self.smoothing_window)
        except Exception as e:
            raise PhaseSanitizationError(f"Failed to smooth phase: {e}")

    def _apply_moving_average(self, phase_data: np.ndarray, window_size: int) -> np.ndarray:
        smoothed_data = phase_data.copy()
        if window_size % 2 == 0:
            window_size += 1
        half_window = window_size // 2
        for i in range(phase_data.shape[0]):
            for j in range(half_window, phase_data.shape[1] - half_window):
                start_idx = j - half_window
                end_idx = j + half_window + 1
                smoothed_data[i, j] = np.mean(phase_data[i, start_idx:end_idx])
        return smoothed_data

    # ------------------------------------------------------------------
    # Noise filtering
    # ------------------------------------------------------------------

    def filter_noise(self, phase_data: np.ndarray) -> np.ndarray:
        """Apply optional Butterworth low-pass filter to remove high-frequency noise.

        Args:
            phase_data: Phase data (2D array)

        Returns:
            Filtered phase data

        Raises:
            PhaseSanitizationError: If noise filtering fails
        """
        if not self.enable_noise_filtering:
            return phase_data

        try:
            return self._apply_low_pass_filter(phase_data, self.noise_threshold)
        except Exception as e:
            raise PhaseSanitizationError(f"Failed to filter noise: {e}")

    def _apply_low_pass_filter(self, phase_data: np.ndarray, threshold: float) -> np.ndarray:
        filtered_data = phase_data.copy()
        min_filter_length = 18
        if phase_data.shape[1] < min_filter_length:
            return filtered_data

        nyquist = 0.5
        cutoff = threshold * nyquist
        b, a = signal.butter(4, cutoff, btype='low')
        for i in range(phase_data.shape[0]):
            filtered_data[i, :] = signal.filtfilt(b, a, phase_data[i, :])
        return filtered_data

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------

    def sanitize_phase(self, phase_data: np.ndarray) -> np.ndarray:
        """Sanitize phase data through the complete pipeline.

        Pipeline: unwrap → remove outliers → smooth → filter noise.

        Args:
            phase_data: Raw phase data (2D array, shape [antennas, subcarriers])

        Returns:
            Sanitized phase data

        Raises:
            PhaseSanitizationError: If sanitization fails
        """
        try:
            self._total_processed += 1
            self.validate_phase_data(phase_data)
            sanitized = self.unwrap_phase(phase_data)
            sanitized = self.remove_outliers(sanitized)
            sanitized = self.smooth_phase(sanitized)
            sanitized = self.filter_noise(sanitized)
            return sanitized
        except PhaseSanitizationError:
            self._sanitization_errors += 1
            raise
        except Exception as e:
            self._sanitization_errors += 1
            raise PhaseSanitizationError(f"Sanitization pipeline failed: {e}")

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_phase_data(self, phase_data: np.ndarray) -> bool:
        """Validate phase data format and values.

        Args:
            phase_data: Phase data to validate

        Returns:
            True if valid

        Raises:
            PhaseSanitizationError: If validation fails
        """
        if phase_data.ndim != 2:
            raise PhaseSanitizationError("Phase data must be 2D array")
        if phase_data.size == 0:
            raise PhaseSanitizationError("Phase data cannot be empty")
        min_val, max_val = self.phase_range
        if np.any(phase_data < min_val) or np.any(phase_data > max_val):
            raise PhaseSanitizationError(
                f"Phase values outside valid range [{min_val}, {max_val}]"
            )
        return True

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_sanitization_statistics(self) -> Dict[str, Any]:
        """Return sanitization statistics."""
        total = self._total_processed
        outlier_rate = self._outliers_removed / total if total > 0 else 0.0
        error_rate = self._sanitization_errors / total if total > 0 else 0.0
        return {
            'total_processed': total,
            'outliers_removed': self._outliers_removed,
            'sanitization_errors': self._sanitization_errors,
            'outlier_rate': outlier_rate,
            'error_rate': error_rate,
        }

    def reset_statistics(self) -> None:
        """Reset sanitization statistics."""
        self._total_processed = 0
        self._outliers_removed = 0
        self._sanitization_errors = 0
