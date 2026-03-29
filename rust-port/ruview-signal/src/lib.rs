//! ruview-signal — Signal processing algorithms for the RuView WiFi-CSI system.
//!
//! Ported from Python `csi_processor.py` and `phase_sanitizer.py`.
//! All functions operate on slices and return owned vectors — no heap-heavy
//! abstractions, no async, no I/O.

use ruview_core::Complex;

// ---------------------------------------------------------------------------
// Hampel filter
// ---------------------------------------------------------------------------

/// Hampel filter: replace outliers in `data` with the local median.
///
/// For each sample, the median and MAD (median absolute deviation) of the
/// surrounding window `[i - half_window, i + half_window]` are computed.
/// If the sample deviates from the median by more than `threshold * MAD`,
/// it is replaced with the median.
///
/// Returns the number of samples replaced.
///
/// Ported from the outlier detection / z-score pattern in
/// `phase_sanitizer.py::_detect_outliers` and `_interpolate_outliers`.
pub fn hampel_filter(data: &mut [f32], half_window: usize, threshold: f32) -> usize {
    let n = data.len();
    if n == 0 || half_window == 0 {
        return 0;
    }

    // Work on a copy so the window computation uses original values.
    let original: Vec<f32> = data.to_vec();
    let mut replaced = 0usize;

    // MAD scale factor: 1.4826 makes MAD a consistent estimator of std for
    // normally distributed data.
    const MAD_SCALE: f32 = 1.4826;

    for i in 0..n {
        let lo = if i >= half_window { i - half_window } else { 0 };
        let hi = if i + half_window < n { i + half_window + 1 } else { n };

        // Collect window values
        let mut window: Vec<f32> = original[lo..hi].to_vec();
        window.sort_unstable_by(|a, b| a.partial_cmp(b).unwrap_or(core::cmp::Ordering::Equal));

        let median = median_sorted(&window);

        // Compute MAD
        let mut abs_devs: Vec<f32> = window.iter().map(|v| libm::fabsf(*v - median)).collect();
        abs_devs.sort_unstable_by(|a, b| a.partial_cmp(b).unwrap_or(core::cmp::Ordering::Equal));
        let mad = median_sorted(&abs_devs) * MAD_SCALE;

        if mad > 1e-12 {
            let deviation = libm::fabsf(original[i] - median);
            if deviation > threshold * mad {
                data[i] = median;
                replaced += 1;
            }
        }
    }

    replaced
}

/// Median of a sorted slice. For even-length slices, returns the mean of the
/// two middle elements.
fn median_sorted(sorted: &[f32]) -> f32 {
    let n = sorted.len();
    if n == 0 {
        return 0.0;
    }
    if n % 2 == 1 {
        sorted[n / 2]
    } else {
        (sorted[n / 2 - 1] + sorted[n / 2]) / 2.0
    }
}

// ---------------------------------------------------------------------------
// Phase unwrapping
// ---------------------------------------------------------------------------

/// Unwrap phase values to remove 2-pi discontinuities between consecutive frames.
///
/// For each subcarrier index, the difference `current[i] - previous[i]` is
/// adjusted so that it lies within `(-pi, pi]`, then accumulated from the
/// previous value.  This mirrors `numpy.unwrap` applied across the time axis.
///
/// Ported from `phase_sanitizer.py::_unwrap_custom`.
pub fn unwrap_phase(current: &[f32], previous: &[f32]) -> Vec<f32> {
    let n = current.len().min(previous.len());
    let mut result = Vec::with_capacity(n);
    let pi = core::f32::consts::PI;
    let two_pi = 2.0 * pi;

    for idx in 0..n {
        let mut diff = current[idx] - previous[idx];
        // Wrap diff into (-pi, pi]
        diff = diff - two_pi * libm::floorf((diff + pi) / two_pi);
        result.push(previous[idx] + diff);
    }
    result
}

// ---------------------------------------------------------------------------
// CSI Ratio (conjugate multiplication)
// ---------------------------------------------------------------------------

/// Compute the CSI ratio using conjugate multiplication against a reference
/// subcarrier.
///
/// For each subcarrier `k`, the result is `csi[k] * conj(csi[ref_idx])`.
/// This removes common phase offsets (e.g., carrier frequency offset,
/// sampling clock offset) while preserving channel-induced phase changes.
///
/// Ported from the Doppler/phase-difference extraction pattern in
/// `csi_processor.py::_extract_doppler_features`.
pub fn csi_ratio(csi: &[Complex], ref_idx: usize) -> Vec<Complex> {
    if csi.is_empty() || ref_idx >= csi.len() {
        return Vec::new();
    }

    let ref_conj = csi[ref_idx].conj();
    csi.iter().map(|c| c.mul(&ref_conj)).collect()
}

// ---------------------------------------------------------------------------
// Top-K subcarrier selection by variance
// ---------------------------------------------------------------------------

/// Select the indices of the top-K subcarriers ranked by variance (descending).
///
/// This implements the subcarrier selection strategy from the Python codebase
/// where only the most informative subcarriers (highest variance in amplitude)
/// are used for downstream processing, reducing noise and computation.
///
/// If `k >= variances.len()`, all indices are returned (sorted by variance).
pub fn select_top_k(variances: &[f64], k: usize) -> Vec<usize> {
    let mut indexed: Vec<(usize, f64)> = variances.iter().copied().enumerate().collect();
    // Sort descending by variance
    indexed.sort_unstable_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(core::cmp::Ordering::Equal));

    let take = k.min(indexed.len());
    indexed[..take].iter().map(|(idx, _)| *idx).collect()
}

// ---------------------------------------------------------------------------
// Zero-crossing BPM estimation
// ---------------------------------------------------------------------------

/// Estimate BPM (breaths or beats per minute) from a band-pass filtered signal
/// using the zero-crossing method.
///
/// Counts the number of upward zero-crossings (negative-to-positive) and
/// converts to BPM: `crossings / duration_seconds * 60`.
///
/// Returns `None` if the signal is too short or has fewer than 2 crossings.
///
/// Ported from the breathing/heart-rate estimation logic referenced in
/// `csi_processor.py` feature extraction.
pub fn zero_crossing_bpm(filtered: &[f32], sample_rate: f32) -> Option<f32> {
    if filtered.len() < 4 || sample_rate <= 0.0 {
        return None;
    }

    let mut crossings = 0u32;
    for i in 1..filtered.len() {
        // Count upward zero crossings (negative -> positive)
        if filtered[i - 1] < 0.0 && filtered[i] >= 0.0 {
            crossings += 1;
        }
    }

    if crossings < 2 {
        return None;
    }

    let duration_s = filtered.len() as f32 / sample_rate;
    let frequency_hz = crossings as f32 / duration_s;
    let bpm = frequency_hz * 60.0;

    Some(bpm)
}

// ---------------------------------------------------------------------------
// Motion index
// ---------------------------------------------------------------------------

/// Compute a motion index from a buffer of amplitude snapshots.
///
/// The motion index is the mean of the per-subcarrier standard deviations
/// across time, clipped to `[0, 1]`.  Higher values indicate more movement.
///
/// Ported from `csi_processor.py::_analyze_motion_patterns` which uses
/// amplitude variance as a proxy for motion.
pub fn motion_index(amplitude_buffer: &[Vec<f32>]) -> f32 {
    if amplitude_buffer.is_empty() {
        return 0.0;
    }

    // Determine number of subcarriers from the first frame.
    let n_sub = amplitude_buffer[0].len();
    if n_sub == 0 {
        return 0.0;
    }

    let n_frames = amplitude_buffer.len() as f64;
    if n_frames < 2.0 {
        return 0.0;
    }

    let mut total_std = 0.0f64;

    for sc in 0..n_sub {
        // Compute mean for this subcarrier across all frames.
        let mut sum = 0.0f64;
        for frame in amplitude_buffer {
            if sc < frame.len() {
                sum += frame[sc] as f64;
            }
        }
        let mean = sum / n_frames;

        // Compute variance (population) for this subcarrier.
        let mut var_sum = 0.0f64;
        for frame in amplitude_buffer {
            let val = if sc < frame.len() { frame[sc] as f64 } else { 0.0 };
            let diff = val - mean;
            var_sum += diff * diff;
        }
        let std_dev = libm::sqrt(var_sum / n_frames);
        total_std += std_dev;
    }

    let mean_std = total_std / n_sub as f64;

    // Normalize: empirically, raw std values from i8 I/Q data rarely exceed
    // ~50, so we divide by 50 and clamp to [0, 1].
    let normalized = mean_std / 50.0;
    if normalized > 1.0 {
        1.0
    } else {
        normalized as f32
    }
}

// ---------------------------------------------------------------------------
// Pose classification
// ---------------------------------------------------------------------------

/// Classify the current pose / activity state from motion index and optional
/// Doppler shift magnitude.
///
/// Returns `(pose_label, confidence)`.
///
/// Classification thresholds (ported from Python `csi_processor.py`
/// human detection confidence logic):
///
/// | Motion     | Doppler    | Pose            |
/// |------------|------------|-----------------|
/// | < 0.05     | —          | "empty"         |
/// | 0.05–0.15  | —          | "stationary"    |
/// | 0.15–0.40  | low / None | "sitting"       |
/// | 0.15–0.40  | high       | "gesturing"     |
/// | 0.40–0.70  | —          | "walking"       |
/// | > 0.70     | —          | "running"       |
pub fn classify_pose(motion: f32, doppler: Option<f32>) -> (&'static str, f32) {
    if motion < 0.05 {
        ("empty", 1.0 - motion / 0.05)
    } else if motion < 0.15 {
        let conf = (motion - 0.05) / 0.10;
        ("stationary", 0.5 + 0.5 * conf)
    } else if motion < 0.40 {
        // Distinguish sitting from gesturing using Doppler.
        let conf = 0.6 + 0.4 * ((motion - 0.15) / 0.25);
        match doppler {
            Some(d) if d > 0.5 => ("gesturing", conf),
            _ => ("sitting", conf),
        }
    } else if motion < 0.70 {
        let conf = 0.7 + 0.3 * ((motion - 0.40) / 0.30);
        ("walking", conf)
    } else {
        let conf = if motion > 1.0 { 1.0 } else { 0.85 + 0.15 * ((motion - 0.70) / 0.30) };
        ("running", conf)
    }
}

// ---------------------------------------------------------------------------
// Butterworth 2nd-order IIR bandpass filter
// ---------------------------------------------------------------------------

/// Butterworth 2nd-order IIR bandpass filter state.
///
/// Uses a bilinear-transform approximation to design a 2nd-order bandpass
/// Butterworth IIR filter.  The design follows the standard Direct Form II
/// transposed structure with pre-warped analogue corner frequencies.
pub struct ButterworthBandpass {
    b: [f64; 3],
    a: [f64; 2], // a[1], a[2] (a[0] normalised to 1)
    x_hist: [f64; 2],
    y_hist: [f64; 2],
}

impl ButterworthBandpass {
    /// Create a bandpass filter for the given `sample_rate` (Hz),
    /// `low_hz` (lower −3 dB corner) and `high_hz` (upper −3 dB corner).
    ///
    /// The implementation derives the 2nd-order bandpass coefficients via
    /// the bilinear transform with frequency pre-warping.
    pub fn new(sample_rate: f64, low_hz: f64, high_hz: f64) -> Self {
        let pi = core::f64::consts::PI;

        // Pre-warp analogue frequencies.
        let w_low = 2.0 * sample_rate * libm::tan(pi * low_hz / sample_rate);
        let w_high = 2.0 * sample_rate * libm::tan(pi * high_hz / sample_rate);

        let bw = w_high - w_low;           // analogue bandwidth
        let w0 = libm::sqrt(w_low * w_high); // geometric centre frequency

        // Bilinear transform for 2nd-order bandpass.
        // Denominator coefficients (normalised, a0 = 1):
        //   a0 = 4*fs^2 + 2*BW*fs + w0^2  (normalisation divisor)
        //   a1 = 2*(w0^2 - 4*fs^2)
        //   a2 = 4*fs^2 - 2*BW*fs + w0^2
        let fs = sample_rate;
        let a0 = 4.0 * fs * fs + 2.0 * bw * fs + w0 * w0;
        let a1 = 2.0 * (w0 * w0 - 4.0 * fs * fs);
        let a2 = 4.0 * fs * fs - 2.0 * bw * fs + w0 * w0;

        // Numerator coefficients (bandpass: b0 = 2*BW*fs, b1 = 0, b2 = -b0)
        let b0 = 2.0 * bw * fs / a0;
        let b1 = 0.0;
        let b2 = -b0;

        Self {
            b: [b0, b1, b2],
            a: [a1 / a0, a2 / a0],
            x_hist: [0.0; 2],
            y_hist: [0.0; 2],
        }
    }

    /// Filter a single sample using Direct Form II transposed IIR structure.
    pub fn filter(&mut self, x: f64) -> f64 {
        let y = self.b[0] * x
            + self.b[1] * self.x_hist[0]
            + self.b[2] * self.x_hist[1]
            - self.a[0] * self.y_hist[0]
            - self.a[1] * self.y_hist[1];

        // Shift history buffers.
        self.x_hist[1] = self.x_hist[0];
        self.x_hist[0] = x;
        self.y_hist[1] = self.y_hist[0];
        self.y_hist[0] = y;

        y
    }
}

// ---------------------------------------------------------------------------
// Breathing envelope extraction
// ---------------------------------------------------------------------------

/// Extract breathing envelope amplitude from a signal window using RMS.
///
/// Computes the RMS (root-mean-square) over the full signal as an envelope
/// estimate.  Returns a value in `[0.0, 1.0]` — the raw RMS normalised by
/// the maximum possible value seen in the window.
///
/// Returns `0.0` for an empty slice.
pub fn breathing_envelope(signal: &[f64], _sub_window: usize) -> f64 {
    if signal.is_empty() {
        return 0.0;
    }
    let sum_sq: f64 = signal.iter().map(|v| v * v).sum();
    let rms = libm::sqrt(sum_sq / signal.len() as f64);

    // Normalise by the peak absolute value so the result stays in [0, 1].
    let peak = signal
        .iter()
        .map(|v| {
            let av = if *v < 0.0 { -*v } else { *v };
            av
        })
        .fold(0.0f64, f64::max);

    if peak < 1e-12 {
        0.0
    } else {
        let norm = rms / peak;
        if norm > 1.0 { 1.0 } else { norm }
    }
}

// ---------------------------------------------------------------------------
// HRV metrics
// ---------------------------------------------------------------------------

/// HRV (heart-rate variability) metrics derived from inter-beat intervals.
#[derive(Debug, Clone)]
pub struct HrvMetrics {
    /// Standard deviation of NN intervals (ms).
    pub sdnn: f64,
    /// Root mean square of successive differences (ms).
    pub rmssd: f64,
    /// Percentage of consecutive NN intervals differing by more than 50 ms.
    pub pnn50: f64,
}

/// Compute HRV metrics from a series of inter-beat intervals (`ibi_ms`) in
/// milliseconds.
///
/// Returns `None` if fewer than 4 IBI values are supplied (not enough data
/// for meaningful HRV statistics).
pub fn compute_hrv(ibi_ms: &[f64]) -> Option<HrvMetrics> {
    if ibi_ms.len() < 4 {
        return None;
    }

    let n = ibi_ms.len() as f64;

    // SDNN — standard deviation of all NN intervals.
    let mean = ibi_ms.iter().sum::<f64>() / n;
    let variance = ibi_ms.iter().map(|v| (v - mean) * (v - mean)).sum::<f64>() / n;
    let sdnn = libm::sqrt(variance);

    // RMSSD — root mean square of successive differences.
    let m = ibi_ms.len() - 1;
    let sq_diff_sum: f64 = (0..m)
        .map(|i| {
            let d = ibi_ms[i + 1] - ibi_ms[i];
            d * d
        })
        .sum();
    let rmssd = libm::sqrt(sq_diff_sum / m as f64);

    // pNN50 — percentage of successive differences > 50 ms.
    let nn50 = (0..m)
        .filter(|&i| {
            let d = ibi_ms[i + 1] - ibi_ms[i];
            let ad = if d < 0.0 { -d } else { d };
            ad > 50.0
        })
        .count();
    let pnn50 = nn50 as f64 / m as f64 * 100.0;

    Some(HrvMetrics { sdnn, rmssd, pnn50 })
}

// ---------------------------------------------------------------------------
// Sleep stage classification
// ---------------------------------------------------------------------------

/// Sleep stage derived from motion and breathing parameters.
#[derive(Debug, Clone, PartialEq)]
pub enum SleepStage {
    Wake,
    Light,
    Deep,
    Rem,
    Unknown,
}

/// Classify sleep stage from motion and breathing parameters.
///
/// | Condition | Stage |
/// |-----------|-------|
/// | `motion_index > 0.3` | Wake |
/// | `motion < 0.05` AND `breathing_variability > 3.0` | REM |
/// | `motion < 0.05` AND `brv < 1.5` AND `8 < br < 15` | Deep |
/// | otherwise | Light |
pub fn classify_sleep_stage(
    motion_index: f64,
    breathing_rate: f64,
    breathing_variability: f64,
) -> SleepStage {
    if motion_index > 0.3 {
        SleepStage::Wake
    } else if motion_index < 0.05 && breathing_variability > 3.0 {
        SleepStage::Rem
    } else if motion_index < 0.05
        && breathing_variability < 1.5
        && breathing_rate > 8.0
        && breathing_rate < 15.0
    {
        SleepStage::Deep
    } else {
        SleepStage::Light
    }
}

// ---------------------------------------------------------------------------
// Fall risk score
// ---------------------------------------------------------------------------

/// Compute fall risk score in `[0.0, 1.0]` from gait parameters.
///
/// | Parameter | Contribution |
/// |-----------|-------------|
/// | `cadence < 80` steps/min | high risk (+0.5) |
/// | `asymmetry > 0.2` | elevated (+0.3) |
/// | `variability > 0.3` | elevated (+0.2) |
///
/// The contributions are weighted and clamped to `[0.0, 1.0]`.
pub fn fall_risk_score(cadence: f64, asymmetry: f64, variability: f64) -> f64 {
    let mut score = 0.0f64;

    // Cadence contribution: linearly interpolate between 0 (cadence >= 100)
    // and 0.5 (cadence <= 60).
    if cadence < 100.0 {
        let cadence_risk = if cadence <= 60.0 {
            0.5
        } else {
            0.5 * (100.0 - cadence) / 40.0
        };
        score += cadence_risk;
    }

    // Asymmetry contribution: linearly interpolate between 0 (asym <= 0.1)
    // and 0.3 (asym >= 0.4).
    if asymmetry > 0.1 {
        let asym_risk = if asymmetry >= 0.4 {
            0.3
        } else {
            0.3 * (asymmetry - 0.1) / 0.3
        };
        score += asym_risk;
    }

    // Variability contribution: linearly interpolate between 0 (var <= 0.15)
    // and 0.2 (var >= 0.45).
    if variability > 0.15 {
        let var_risk = if variability >= 0.45 {
            0.2
        } else {
            0.2 * (variability - 0.15) / 0.3
        };
        score += var_risk;
    }

    if score > 1.0 { 1.0 } else { score }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    // -- Hampel filter ------------------------------------------------------

    #[test]
    fn test_hampel_filter() {
        // Insert a clear outlier into smooth data.
        let mut data = vec![1.0, 1.1, 1.0, 0.9, 1.0, 100.0, 1.1, 0.9, 1.0, 1.0];
        let replaced = hampel_filter(&mut data, 3, 3.0);
        assert!(replaced >= 1, "should replace at least the outlier at index 5");
        // The outlier (100.0) should be replaced with something close to 1.0
        assert!(
            (data[5] - 1.0).abs() < 1.0,
            "outlier should be replaced with local median, got {}",
            data[5]
        );
    }

    #[test]
    fn test_hampel_filter_no_outliers() {
        let mut data = vec![5.0, 5.1, 4.9, 5.0, 5.1, 4.9];
        let replaced = hampel_filter(&mut data, 2, 3.0);
        assert_eq!(replaced, 0, "no outliers should be replaced");
    }

    #[test]
    fn test_hampel_filter_empty() {
        let mut data: Vec<f32> = vec![];
        let replaced = hampel_filter(&mut data, 3, 3.0);
        assert_eq!(replaced, 0);
    }

    // -- Phase unwrapping ---------------------------------------------------

    #[test]
    fn test_unwrap_phase() {
        let pi = core::f32::consts::PI;
        // Simulate a phase that wraps around from ~pi to ~-pi
        let previous = vec![2.8, 3.0, 3.1];
        let current = vec![-3.0, -2.9, -2.8]; // wrapped around 2*pi boundary

        let unwrapped = unwrap_phase(&current, &previous);
        assert_eq!(unwrapped.len(), 3);

        // After unwrapping, the result should be continuous (close to previous + small delta)
        for i in 0..3 {
            let diff = (unwrapped[i] - previous[i]).abs();
            // The actual phase change should be small (< pi), not ~2*pi
            assert!(
                diff < pi,
                "unwrapped phase at {} should be close to previous, diff = {}",
                i,
                diff
            );
        }
    }

    #[test]
    fn test_unwrap_phase_no_wrap() {
        // Phases that don't wrap should pass through unchanged
        let previous = vec![0.1, 0.2, 0.3];
        let current = vec![0.15, 0.25, 0.35];
        let unwrapped = unwrap_phase(&current, &previous);
        for i in 0..3 {
            assert!(
                (unwrapped[i] - current[i]).abs() < 1e-5,
                "non-wrapping phases should be unchanged"
            );
        }
    }

    // -- CSI ratio ----------------------------------------------------------

    #[test]
    fn test_csi_ratio() {
        let csi = vec![
            Complex::new(1.0, 0.0),
            Complex::new(0.0, 1.0),
            Complex::new(1.0, 1.0),
        ];
        // Use index 0 as reference: conj(1+0i) = (1-0i) = (1,0)
        let ratio = csi_ratio(&csi, 0);
        assert_eq!(ratio.len(), 3);
        // ratio[0] = (1,0) * (1,0) = (1,0)
        assert!((ratio[0].i - 1.0).abs() < 1e-5);
        assert!((ratio[0].q - 0.0).abs() < 1e-5);
        // ratio[1] = (0,1) * (1,0) = (0,1)
        assert!((ratio[1].i - 0.0).abs() < 1e-5);
        assert!((ratio[1].q - 1.0).abs() < 1e-5);
    }

    #[test]
    fn test_csi_ratio_empty() {
        let result = csi_ratio(&[], 0);
        assert!(result.is_empty());
    }

    // -- Top-K selection ----------------------------------------------------

    #[test]
    fn test_select_top_k() {
        let variances = vec![0.1, 5.0, 2.0, 8.0, 0.5];
        let top2 = select_top_k(&variances, 2);
        assert_eq!(top2.len(), 2);
        // Highest variance is at index 3 (8.0), second is index 1 (5.0)
        assert_eq!(top2[0], 3);
        assert_eq!(top2[1], 1);
    }

    #[test]
    fn test_select_top_k_all() {
        let variances = vec![1.0, 2.0, 3.0];
        let result = select_top_k(&variances, 10);
        assert_eq!(result.len(), 3);
        assert_eq!(result[0], 2); // highest first
    }

    // -- Zero-crossing BPM -------------------------------------------------

    #[test]
    fn test_zero_crossing() {
        // Generate a 1 Hz sine wave at 100 Hz sample rate for 5 seconds.
        // Should have ~5 upward zero crossings -> 60 BPM.
        let sample_rate = 100.0f32;
        let duration_s = 5.0;
        let n = (sample_rate * duration_s) as usize;
        let freq = 1.0f32;

        let signal: Vec<f32> = (0..n)
            .map(|i| {
                let t = i as f32 / sample_rate;
                libm::sinf(2.0 * core::f32::consts::PI * freq * t)
            })
            .collect();

        let bpm = zero_crossing_bpm(&signal, sample_rate);
        assert!(bpm.is_some());
        let bpm = bpm.unwrap();
        // Should be close to 60 BPM (1 Hz * 60)
        assert!(
            (bpm - 60.0).abs() < 5.0,
            "expected ~60 BPM, got {}",
            bpm
        );
    }

    #[test]
    fn test_zero_crossing_too_short() {
        let signal = vec![0.0, 1.0, -1.0];
        assert!(zero_crossing_bpm(&signal, 100.0).is_none());
    }

    #[test]
    fn test_zero_crossing_constant() {
        // Constant signal — no crossings
        let signal = vec![1.0; 100];
        assert!(zero_crossing_bpm(&signal, 100.0).is_none());
    }

    // -- Motion index -------------------------------------------------------

    #[test]
    fn test_motion_index_still() {
        // All frames identical -> zero motion
        let frames = vec![vec![10.0, 20.0, 30.0]; 10];
        let mi = motion_index(&frames);
        assert!(
            mi < 0.01,
            "identical frames should have near-zero motion index, got {}",
            mi
        );
    }

    #[test]
    fn test_motion_index_moving() {
        // Frames with high variance per subcarrier
        let mut frames = Vec::new();
        for i in 0..20 {
            let val = if i % 2 == 0 { 50.0 } else { -50.0 };
            frames.push(vec![val, val, val]);
        }
        let mi = motion_index(&frames);
        assert!(
            mi > 0.5,
            "high-variance frames should have high motion index, got {}",
            mi
        );
    }

    // -- Pose classification ------------------------------------------------

    #[test]
    fn test_classify_pose() {
        let (pose, conf) = classify_pose(0.01, None);
        assert_eq!(pose, "empty");
        assert!(conf > 0.0);

        let (pose, _) = classify_pose(0.10, None);
        assert_eq!(pose, "stationary");

        let (pose, _) = classify_pose(0.25, None);
        assert_eq!(pose, "sitting");

        let (pose, _) = classify_pose(0.25, Some(0.8));
        assert_eq!(pose, "gesturing");

        let (pose, _) = classify_pose(0.55, None);
        assert_eq!(pose, "walking");

        let (pose, _) = classify_pose(0.85, None);
        assert_eq!(pose, "running");
    }

    #[test]
    fn test_classify_pose_boundary() {
        // Exact boundary values
        let (pose, _) = classify_pose(0.05, None);
        assert_eq!(pose, "stationary");

        let (pose, _) = classify_pose(0.15, None);
        assert_eq!(pose, "sitting");

        let (pose, _) = classify_pose(0.40, None);
        assert_eq!(pose, "walking");

        let (pose, _) = classify_pose(0.70, None);
        assert_eq!(pose, "running");
    }

    // -- Breathing envelope -------------------------------------------------

    #[test]
    fn test_breathing_envelope_nonzero() {
        // A simple sine-like signal should produce a non-zero envelope.
        let signal: Vec<f64> = (0..100)
            .map(|i| libm::sin(2.0 * core::f64::consts::PI * i as f64 / 20.0))
            .collect();
        let env = breathing_envelope(&signal, 10);
        assert!(
            env > 0.0 && env <= 1.0,
            "envelope should be in (0, 1], got {}",
            env
        );
    }

    #[test]
    fn test_breathing_envelope_empty() {
        assert_eq!(breathing_envelope(&[], 10), 0.0);
    }

    // -- HRV ----------------------------------------------------------------

    #[test]
    fn test_compute_hrv_basic() {
        // IBI series with known properties.
        let ibi = vec![800.0, 810.0, 790.0, 820.0, 780.0, 805.0];
        let hrv = compute_hrv(&ibi).expect("should return HRV for 6 IBIs");
        // SDNN > 0 (there is variability)
        assert!(hrv.sdnn > 0.0, "sdnn should be > 0, got {}", hrv.sdnn);
        // RMSSD > 0
        assert!(hrv.rmssd > 0.0, "rmssd should be > 0, got {}", hrv.rmssd);
        // pNN50 in [0, 100]
        assert!(
            hrv.pnn50 >= 0.0 && hrv.pnn50 <= 100.0,
            "pnn50 out of range: {}",
            hrv.pnn50
        );
    }

    #[test]
    fn test_compute_hrv_too_short() {
        assert!(compute_hrv(&[800.0, 810.0, 790.0]).is_none());
        assert!(compute_hrv(&[]).is_none());
    }

    // -- Sleep stage --------------------------------------------------------

    #[test]
    fn test_sleep_stage_wake() {
        let stage = classify_sleep_stage(0.5, 14.0, 2.0);
        assert_eq!(stage, SleepStage::Wake);
    }

    #[test]
    fn test_sleep_stage_deep() {
        // Low motion, low variability, breathing in 8-15 range.
        let stage = classify_sleep_stage(0.02, 12.0, 1.0);
        assert_eq!(stage, SleepStage::Deep);
    }

    #[test]
    fn test_sleep_stage_rem() {
        // Very low motion but high breathing variability.
        let stage = classify_sleep_stage(0.01, 14.0, 4.0);
        assert_eq!(stage, SleepStage::Rem);
    }

    #[test]
    fn test_sleep_stage_light() {
        // Motion in between, doesn't fit other criteria.
        let stage = classify_sleep_stage(0.1, 14.0, 2.0);
        assert_eq!(stage, SleepStage::Light);
    }

    // -- Fall risk score ----------------------------------------------------

    #[test]
    fn test_fall_risk_high() {
        // cadence well below 80, high asymmetry, high variability → high risk.
        let score = fall_risk_score(50.0, 0.5, 0.5);
        assert!(
            score > 0.7,
            "high-risk gait should score > 0.7, got {}",
            score
        );
        assert!(score <= 1.0, "score capped at 1.0, got {}", score);
    }

    #[test]
    fn test_fall_risk_low() {
        // cadence = 110, asymmetry = 0.05, variability = 0.05 → near 0.
        let score = fall_risk_score(110.0, 0.05, 0.05);
        assert!(
            score < 0.1,
            "low-risk gait should score < 0.1, got {}",
            score
        );
    }

    // -- Butterworth bandpass -----------------------------------------------

    #[test]
    fn test_butterworth_passthrough() {
        // A 1 Hz sine wave should pass through a 0.1–5 Hz bandpass filter
        // with meaningful (non-zero) output.
        let mut bp = ButterworthBandpass::new(100.0, 0.1, 5.0);
        let signal: Vec<f64> = (0..200)
            .map(|i| libm::sin(2.0 * core::f64::consts::PI * 1.0 * i as f64 / 100.0))
            .collect();
        // Let the filter settle for half the samples.
        let output: Vec<f64> = signal.iter().map(|&x| bp.filter(x)).collect();
        let rms_out = libm::sqrt(
            output[100..].iter().map(|v| v * v).sum::<f64>() / 100.0,
        );
        assert!(
            rms_out > 0.1,
            "in-band signal should not be heavily attenuated, rms={}",
            rms_out
        );
    }

    #[test]
    fn test_butterworth_attenuates_dc() {
        // DC (0 Hz) should be blocked by the bandpass filter.
        let mut bp = ButterworthBandpass::new(100.0, 0.5, 5.0);
        // Feed a constant DC signal — the bandpass should attenuate it.
        let output: Vec<f64> = (0..200).map(|_| bp.filter(1.0)).collect();
        // After settling (skip first 50 samples), output should be near zero.
        let max_abs = output[50..]
            .iter()
            .map(|v| if *v < 0.0 { -*v } else { *v })
            .fold(0.0f64, f64::max);
        assert!(
            max_abs < 0.5,
            "DC should be attenuated by bandpass filter, max_abs={}",
            max_abs
        );
    }
}
