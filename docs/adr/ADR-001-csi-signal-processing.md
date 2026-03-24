# ADR-001: CSI Signal Processing Pipeline

## Status
Accepted

## Date
2025-06-15

## Context
We need to extract human vital signs (breathing rate, heart rate) from raw WiFi CSI
(Channel State Information) captured by ESP32-S3 nodes. Raw CSI data contains noise
from environmental reflections, multipath fading, and hardware imperfections. A robust
signal processing pipeline is required to isolate physiological micro-movements from
background clutter.

## Decision
Adopt a multi-stage DSP pipeline:

1. **CSI Ratio** -- Divide target subcarrier amplitudes by a reference antenna to cancel
   common-mode noise (transmitter phase drift, AGC fluctuations).
2. **Hampel Filter** -- Remove impulse outliers (window=10, threshold=3 sigma) before
   frequency analysis.
3. **Butterworth Bandpass Filters** -- 4th-order IIR filters:
   - Breathing: 0.1 -- 0.5 Hz (6--30 BPM)
   - Heart rate: 0.8 -- 2.0 Hz (48--120 BPM)
4. **FFT Peak Detection** -- 1024-point FFT on 30-second sliding window; pick dominant
   peak within each band.
5. **Fresnel Zone Model** -- Weight subcarrier contributions by Fresnel zone geometry
   to focus sensitivity on the subject location.

All processing runs server-side in the `signal-adapter` service (Rust).

## Consequences
- **Positive:** Reliable extraction of breathing (14--27 BPM) and heart rate (70--90 BPM)
  validated against pulse oximeter ground truth (MAE < 2 BPM breathing, < 5 BPM heart).
- **Positive:** CSI Ratio eliminates need for hardware synchronization between Tx/Rx.
- **Negative:** 30-second window introduces latency before first reading.
- **Negative:** Heart rate extraction degrades significantly beyond 2m Tx-Rx distance.
- **Trade-off:** Server-side processing centralizes compute but requires stable UDP
  delivery from ESP32 nodes.
