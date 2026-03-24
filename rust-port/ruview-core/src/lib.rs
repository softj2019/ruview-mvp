//! ruview-core — Core types for the RuView WiFi-CSI sensing system.
//!
//! Ported from Python `csi_processor.py` and `csi_extractor.py`.
//! Designed to be `no_std`-compatible (no external dependencies).

#![no_std]

extern crate alloc;
use alloc::string::String;
use alloc::vec::Vec;
use core::fmt;

// ---------------------------------------------------------------------------
// Complex number
// ---------------------------------------------------------------------------

/// A complex number with 32-bit floating-point components.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Complex {
    pub i: f32,
    pub q: f32,
}

impl Complex {
    #[inline]
    pub fn new(i: f32, q: f32) -> Self {
        Self { i, q }
    }

    /// Amplitude (magnitude): sqrt(i² + q²)
    #[inline]
    pub fn amplitude(&self) -> f32 {
        libm::sqrtf(self.i * self.i + self.q * self.q)
    }

    /// Phase angle: atan2(q, i)
    #[inline]
    pub fn phase(&self) -> f32 {
        libm::atan2f(self.q, self.i)
    }

    /// Conjugate: (i, -q)
    #[inline]
    pub fn conj(&self) -> Self {
        Self { i: self.i, q: -self.q }
    }

    /// Complex multiplication: self * other
    #[inline]
    pub fn mul(&self, other: &Self) -> Self {
        Self {
            i: self.i * other.i - self.q * other.q,
            q: self.i * other.q + self.q * other.i,
        }
    }
}

// ---------------------------------------------------------------------------
// Parse error
// ---------------------------------------------------------------------------

/// Errors that can occur when parsing a binary CSI frame.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ParseError {
    /// Frame is shorter than the minimum header size.
    FrameTooShort { need: usize, got: usize },
    /// Magic bytes do not match the expected value.
    InvalidMagic { expected: u32, got: u32 },
    /// Frame is too short to contain the declared I/Q payload.
    InsufficientIqData { need: usize, got: usize },
}

impl fmt::Display for ParseError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ParseError::FrameTooShort { need, got } => {
                write!(f, "frame too short: need {} bytes, got {}", need, got)
            }
            ParseError::InvalidMagic { expected, got } => {
                write!(f, "invalid magic: expected 0x{:08X}, got 0x{:08X}", expected, got)
            }
            ParseError::InsufficientIqData { need, got } => {
                write!(f, "insufficient I/Q data: need {} bytes, got {}", need, got)
            }
        }
    }
}

// ---------------------------------------------------------------------------
// CSI frame (raw, from ESP32)
// ---------------------------------------------------------------------------

/// Magic value for the ADR-018 binary CSI frame format.
pub const CSI_MAGIC: u32 = 0xC511_0001;

/// Header size in bytes (20 bytes including 2 reserved).
const HEADER_SIZE: usize = 20;

/// A raw CSI frame parsed from an ESP32 node in ADR-018 binary format.
///
/// Binary frame layout:
/// ```text
///   Offset  Size  Field
///   0       4     Magic: 0xC5110001 (LE)
///   4       1     Node ID
///   5       1     Number of antennas (ignored here; spec says 1 for ruview-core)
///   6       2     Number of subcarriers (LE u16)
///   8       4     Frequency MHz (LE u32)
///   12      4     Sequence number (LE u32)
///   16      1     RSSI (i8)
///   17      1     Noise floor (i8)
///   18      2     Reserved
///   20      N*2   I/Q pairs (n_subcarriers * 2 bytes, each signed i8)
/// ```
#[derive(Debug, Clone)]
pub struct CsiFrame {
    pub magic: u32,
    pub node_id: u8,
    pub n_subcarriers: u16,
    pub frequency_mhz: u32,
    pub sequence: u32,
    pub rssi: i8,
    pub noise_floor: i8,
    pub iq_data: Vec<Complex>,
}

impl CsiFrame {
    /// Parse an ADR-018 binary frame from a byte slice.
    ///
    /// The frame must be at least `HEADER_SIZE` (20) bytes plus
    /// `n_subcarriers * 2` bytes of I/Q payload.
    pub fn parse(data: &[u8]) -> Result<Self, ParseError> {
        if data.len() < HEADER_SIZE {
            return Err(ParseError::FrameTooShort {
                need: HEADER_SIZE,
                got: data.len(),
            });
        }

        // Parse header fields (all little-endian).
        let magic = u32::from_le_bytes([data[0], data[1], data[2], data[3]]);
        if magic != CSI_MAGIC {
            return Err(ParseError::InvalidMagic {
                expected: CSI_MAGIC,
                got: magic,
            });
        }

        let node_id = data[4];
        // data[5] is n_antennas — we read it but flatten into a single list
        let _n_antennas = data[5];
        let n_subcarriers = u16::from_le_bytes([data[6], data[7]]);
        let frequency_mhz = u32::from_le_bytes([data[8], data[9], data[10], data[11]]);
        let sequence = u32::from_le_bytes([data[12], data[13], data[14], data[15]]);
        let rssi = data[16] as i8;
        let noise_floor = data[17] as i8;
        // data[18..20] reserved

        let iq_count = n_subcarriers as usize;
        let iq_bytes = iq_count * 2;
        let expected_len = HEADER_SIZE + iq_bytes;

        if data.len() < expected_len {
            return Err(ParseError::InsufficientIqData {
                need: expected_len,
                got: data.len(),
            });
        }

        // Parse I/Q pairs as signed bytes.
        let mut iq_data = Vec::with_capacity(iq_count);
        for idx in 0..iq_count {
            let offset = HEADER_SIZE + idx * 2;
            let i_val = data[offset] as i8;
            let q_val = data[offset + 1] as i8;
            iq_data.push(Complex::new(i_val as f32, q_val as f32));
        }

        Ok(CsiFrame {
            magic,
            node_id,
            n_subcarriers,
            frequency_mhz,
            sequence,
            rssi,
            noise_floor,
            iq_data,
        })
    }

    /// Compute amplitude for each subcarrier.
    pub fn amplitudes(&self) -> Vec<f32> {
        self.iq_data.iter().map(|c| c.amplitude()).collect()
    }

    /// Compute phase for each subcarrier.
    pub fn phases(&self) -> Vec<f32> {
        self.iq_data.iter().map(|c| c.phase()).collect()
    }
}

// ---------------------------------------------------------------------------
// Processed CSI result
// ---------------------------------------------------------------------------

/// Processed CSI result after signal processing and classification.
#[derive(Debug, Clone)]
pub struct ProcessedCsi {
    pub device_id: String,
    pub amplitude: Vec<f32>,
    pub phase: Vec<f32>,
    pub motion_index: f32,
    pub breathing_rate: Option<f32>,
    pub heart_rate: Option<f32>,
    pub presence_score: f32,
    pub csi_pose: Option<String>,
    pub estimated_persons: u8,
}

// ---------------------------------------------------------------------------
// Welford online statistics
// ---------------------------------------------------------------------------

/// Welford's online algorithm for computing running mean, variance,
/// and standard deviation in a single pass with O(1) memory.
///
/// Ported from the statistical tracking patterns used throughout
/// the Python `csi_processor.py`.
#[derive(Debug, Clone)]
pub struct WelfordStats {
    count: u64,
    mean: f64,
    m2: f64,
}

impl WelfordStats {
    /// Create a new, empty statistics accumulator.
    pub fn new() -> Self {
        Self {
            count: 0,
            mean: 0.0,
            m2: 0.0,
        }
    }

    /// Number of values observed so far.
    #[inline]
    pub fn count(&self) -> u64 {
        self.count
    }

    /// Current running mean.
    #[inline]
    pub fn mean(&self) -> f64 {
        self.mean
    }

    /// Feed a new value into the accumulator.
    ///
    /// Updates mean and M2 using Welford's recurrence:
    ///   delta  = value - old_mean
    ///   mean  += delta / count
    ///   delta2 = value - new_mean
    ///   M2    += delta * delta2
    pub fn update(&mut self, value: f64) {
        self.count += 1;
        let delta = value - self.mean;
        self.mean += delta / self.count as f64;
        let delta2 = value - self.mean;
        self.m2 += delta * delta2;
    }

    /// Sample variance (M2 / (count - 1)).
    ///
    /// Returns 0.0 if fewer than 2 values have been observed.
    pub fn variance(&self) -> f64 {
        if self.count < 2 {
            return 0.0;
        }
        self.m2 / (self.count - 1) as f64
    }

    /// Sample standard deviation.
    pub fn std(&self) -> f64 {
        libm::sqrt(self.variance())
    }

    /// Compute z-score of a value relative to the accumulated distribution.
    ///
    /// Returns 0.0 if std is zero (constant signal).
    pub fn z_score(&self, value: f64) -> f64 {
        let s = self.std();
        if s < 1e-12 {
            return 0.0;
        }
        (value - self.mean) / s
    }
}

impl Default for WelfordStats {
    fn default() -> Self {
        Self::new()
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    extern crate std;
    use super::*;

    #[test]
    fn test_complex_amplitude_phase() {
        let c = Complex::new(3.0, 4.0);
        assert!((c.amplitude() - 5.0).abs() < 1e-5);
        assert!((c.phase() - libm::atan2f(4.0, 3.0)).abs() < 1e-5);
    }

    #[test]
    fn test_complex_conjugate_multiply() {
        let a = Complex::new(1.0, 2.0);
        let b = Complex::new(3.0, -1.0);
        let product = a.mul(&b);
        // (1+2i)(3-i) = 3 - i + 6i - 2i² = 3 + 5i + 2 = 5 + 5i
        assert!((product.i - 5.0).abs() < 1e-5);
        assert!((product.q - 5.0).abs() < 1e-5);

        let conj = a.conj();
        assert_eq!(conj.i, 1.0);
        assert_eq!(conj.q, -2.0);
    }

    #[test]
    fn test_welford_basic() {
        let mut w = WelfordStats::new();
        assert_eq!(w.count(), 0);
        assert_eq!(w.mean(), 0.0);

        w.update(10.0);
        assert_eq!(w.count(), 1);
        assert!((w.mean() - 10.0).abs() < 1e-10);

        w.update(20.0);
        assert_eq!(w.count(), 2);
        assert!((w.mean() - 15.0).abs() < 1e-10);

        w.update(30.0);
        assert_eq!(w.count(), 3);
        assert!((w.mean() - 20.0).abs() < 1e-10);
    }

    #[test]
    fn test_welford_variance() {
        let mut w = WelfordStats::new();
        // Feed values [2, 4, 4, 4, 5, 5, 7, 9]
        // Population mean = 5.0, sample variance = 4.571...
        let values = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0];
        for v in &values {
            w.update(*v);
        }

        assert!((w.mean() - 5.0).abs() < 1e-10);

        // Sample variance = sum((xi - mean)^2) / (n-1)
        // = (9+1+1+1+0+0+4+16) / 7 = 32/7 ≈ 4.571428...
        let expected_var = 32.0 / 7.0;
        assert!((w.variance() - expected_var).abs() < 1e-10);

        let expected_std = libm::sqrt(expected_var);
        assert!((w.std() - expected_std).abs() < 1e-10);

        // z-score of mean should be 0
        assert!((w.z_score(5.0)).abs() < 1e-10);
        // z-score of 7.0: (7-5)/std
        let expected_z = 2.0 / expected_std;
        assert!((w.z_score(7.0) - expected_z).abs() < 1e-10);
    }

    #[test]
    fn test_welford_single_value() {
        let mut w = WelfordStats::new();
        w.update(42.0);
        // Variance with a single sample should be 0 (not enough data)
        assert_eq!(w.variance(), 0.0);
        assert_eq!(w.std(), 0.0);
        // z-score should be 0 when std is 0
        assert_eq!(w.z_score(100.0), 0.0);
    }

    #[test]
    fn test_csi_frame_parse() {
        // Build a valid ADR-018 binary frame with 4 subcarriers.
        let n_sub: u16 = 4;
        let mut frame = std::vec::Vec::new();

        // Magic (LE)
        frame.extend_from_slice(&CSI_MAGIC.to_le_bytes());
        // Node ID
        frame.push(0x03);
        // n_antennas
        frame.push(0x01);
        // n_subcarriers (LE u16)
        frame.extend_from_slice(&n_sub.to_le_bytes());
        // Frequency MHz (LE u32) — 2437 MHz (channel 6)
        frame.extend_from_slice(&2437u32.to_le_bytes());
        // Sequence (LE u32)
        frame.extend_from_slice(&42u32.to_le_bytes());
        // RSSI (i8) — -50 dBm
        frame.push((-50i8) as u8);
        // Noise floor (i8) — -90 dBm
        frame.push((-90i8) as u8);
        // Reserved (2 bytes)
        frame.push(0x00);
        frame.push(0x00);

        // I/Q data: 4 subcarriers, each (I, Q) as i8
        let iq_pairs: [(i8, i8); 4] = [(10, 20), (-5, 15), (30, -10), (0, 127)];
        for (i_val, q_val) in &iq_pairs {
            frame.push(*i_val as u8);
            frame.push(*q_val as u8);
        }

        let parsed = CsiFrame::parse(&frame).expect("parse should succeed");
        assert_eq!(parsed.magic, CSI_MAGIC);
        assert_eq!(parsed.node_id, 3);
        assert_eq!(parsed.n_subcarriers, 4);
        assert_eq!(parsed.frequency_mhz, 2437);
        assert_eq!(parsed.sequence, 42);
        assert_eq!(parsed.rssi, -50);
        assert_eq!(parsed.noise_floor, -90);
        assert_eq!(parsed.iq_data.len(), 4);

        // Verify first I/Q pair
        assert!((parsed.iq_data[0].i - 10.0).abs() < 1e-5);
        assert!((parsed.iq_data[0].q - 20.0).abs() < 1e-5);

        // Verify amplitudes
        let amps = parsed.amplitudes();
        assert_eq!(amps.len(), 4);
        let expected_amp0 = libm::sqrtf(10.0 * 10.0 + 20.0 * 20.0);
        assert!((amps[0] - expected_amp0).abs() < 1e-3);
    }

    #[test]
    fn test_csi_frame_parse_too_short() {
        let data = [0u8; 10];
        let err = CsiFrame::parse(&data).unwrap_err();
        assert_eq!(
            err,
            ParseError::FrameTooShort {
                need: HEADER_SIZE,
                got: 10
            }
        );
    }

    #[test]
    fn test_csi_frame_parse_bad_magic() {
        let mut data = [0u8; HEADER_SIZE];
        // Write wrong magic
        data[0..4].copy_from_slice(&0xDEADBEEFu32.to_le_bytes());
        let err = CsiFrame::parse(&data).unwrap_err();
        match err {
            ParseError::InvalidMagic { expected, got } => {
                assert_eq!(expected, CSI_MAGIC);
                assert_eq!(got, 0xDEADBEEF);
            }
            _ => panic!("expected InvalidMagic error"),
        }
    }

    #[test]
    fn test_csi_frame_parse_insufficient_iq() {
        // Valid header declaring 64 subcarriers but no I/Q payload
        let mut data = [0u8; HEADER_SIZE];
        data[0..4].copy_from_slice(&CSI_MAGIC.to_le_bytes());
        data[4] = 1; // node_id
        data[5] = 1; // n_antennas
        data[6..8].copy_from_slice(&64u16.to_le_bytes()); // n_subcarriers = 64
        // rest zeros are fine for header

        let err = CsiFrame::parse(&data).unwrap_err();
        match err {
            ParseError::InsufficientIqData { need, got } => {
                assert_eq!(need, HEADER_SIZE + 64 * 2);
                assert_eq!(got, HEADER_SIZE);
            }
            _ => panic!("expected InsufficientIqData error"),
        }
    }
}
