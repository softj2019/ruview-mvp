/**
 * SignalViz — Canvas-based CSI signal visualization panels.
 *
 * Converted from vendor/ruview-temp/ui/components/signal-viz.js (Three.js scene)
 * to React canvas components using useRef + useEffect (same pattern as SkeletonCanvas
 * in WifiPosePage.tsx).
 *
 * Three panels:
 *   CsiHeatmap          — 30 subcarriers × 40 time slots, blue→cyan→amber ramp
 *   PhaseConstellation  — I/Q scatter plot (64-point complex plane)
 *   DopplerSpectrum     — 16-bar frequency spectrum
 *
 * Data source:
 *   - useSignalStore for live csi_amplitude scalar and breathing/motion hints
 *   - Synthetic demo generation (from original signal-viz.js logic) fills the
 *     full subcarrier / IQ / doppler arrays when granular live data is absent
 */

import { useRef, useEffect, useCallback } from 'react';
import { useSignalStore } from '@/stores/signalStore';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SUBCARRIERS = 30;
const TIME_SLOTS = 40;
const IQ_POINTS = 64;
const DOPPLER_BARS = 16;

// ---------------------------------------------------------------------------
// Demo data generator — ported from signal-viz.js generateDemoData()
// ---------------------------------------------------------------------------

interface SignalArrays {
  amplitude: Float32Array;   // [SUBCARRIERS] 0..1
  iq: Float32Array;          // [IQ_POINTS * 2] interleaved re, im — normalised -1..1
  doppler: Float32Array;     // [DOPPLER_BARS] 0..1
  motionEnergy: number;      // 0..1
}

function generateDemoData(elapsed: number, amplitudeBias: number): SignalArrays {
  // Amplitude
  const amplitude = new Float32Array(SUBCARRIERS);
  for (let i = 0; i < SUBCARRIERS; i++) {
    const base = Math.sin(elapsed * 2 + i * 0.3) * 0.3;
    const body = Math.sin(elapsed * 0.8 + i * 0.15) * 0.25;
    const noise = (Math.random() - 0.5) * 0.1;
    // Mix live bias (csi_amplitude scalar from store) with synthetic shape
    amplitude[i] = Math.max(0, Math.min(1, amplitudeBias * 0.6 + 0.4 + base + body + noise));
  }

  // I/Q — linear phase offset + perturbation, magnitude driven by amplitude
  const iq = new Float32Array(IQ_POINTS * 2);
  for (let i = 0; i < IQ_POINTS; i++) {
    const theta = (i / IQ_POINTS) * Math.PI * 2 + elapsed * 0.5;
    const perturbation = Math.sin(elapsed * 1.5 + i * 0.2) * 0.25;
    const r = 0.6 + Math.sin(elapsed * 0.9 + i * 0.1) * 0.25;
    iq[i * 2]     = r * Math.cos(theta + perturbation);
    iq[i * 2 + 1] = r * Math.sin(theta + perturbation);
  }

  // Doppler
  const doppler = new Float32Array(DOPPLER_BARS);
  const center = DOPPLER_BARS / 2 + Math.sin(elapsed * 0.7) * 3;
  for (let i = 0; i < DOPPLER_BARS; i++) {
    const d = Math.abs(i - center);
    doppler[i] = Math.max(
      0,
      Math.min(1, Math.exp(-d * d * 0.15) * (0.6 + Math.sin(elapsed * 1.2) * 0.3) + (Math.random() - 0.5) * 0.05),
    );
  }

  const motionEnergy = (Math.sin(elapsed * 0.5) + 1) / 2 * 0.7 + 0.15;

  return { amplitude, iq, doppler, motionEnergy };
}

// ---------------------------------------------------------------------------
// Color helpers
// ---------------------------------------------------------------------------

/** HSL amplitude ramp: blue(0.6) → cyan(0.5) → amber(0.1) */
function amplitudeColor(val: number): string {
  const hue = Math.round((0.6 - val * 0.5) * 360);
  const sat = 90;
  const lig = Math.round(10 + val * 50);
  return `hsl(${hue},${sat}%,${lig}%)`;
}

/** Doppler bar color: blue(0.7) → purple(0.5) → magenta(0.4) */
function dopplerColor(val: number): string {
  const hue = Math.round((0.7 - val * 0.3) * 360);
  const lig = Math.round(25 + val * 35);
  return `hsl(${hue},80%,${lig}%)`;
}

// ---------------------------------------------------------------------------
// CsiHeatmap — 30×40 grid, 400×300 canvas
// ---------------------------------------------------------------------------

interface CsiHeatmapProps {
  amplitude: Float32Array | null;
}

function CsiHeatmap({ amplitude }: CsiHeatmapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  // Rolling history: newest row pushed to end, oldest shifted off
  const historyRef = useRef<Float32Array[]>(
    Array.from({ length: TIME_SLOTS }, () => new Float32Array(SUBCARRIERS)),
  );

  useEffect(() => {
    if (!amplitude) return;
    // Shift history and append new row
    historyRef.current.shift();
    historyRef.current.push(new Float32Array(amplitude));
  }, [amplitude]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const W = canvas.width;
    const H = canvas.height;
    const cellW = W / SUBCARRIERS;
    const cellH = H / TIME_SLOTS;

    ctx.clearRect(0, 0, W, H);

    const history = historyRef.current;
    for (let t = 0; t < TIME_SLOTS; t++) {
      const row = history[t];
      for (let s = 0; s < SUBCARRIERS; s++) {
        const val = row[s] ?? 0;
        ctx.fillStyle = amplitudeColor(val);
        ctx.fillRect(
          Math.floor(s * cellW),
          Math.floor(t * cellH),
          Math.ceil(cellW - 0.5),
          Math.ceil(cellH - 0.5),
        );
      }
    }

    // Border
    ctx.strokeStyle = 'rgba(51,85,119,0.5)';
    ctx.lineWidth = 1;
    ctx.strokeRect(0.5, 0.5, W - 1, H - 1);

    // Axis labels
    ctx.fillStyle = '#4b6a88';
    ctx.font = '10px monospace';
    ctx.fillText('subcarrier →', 4, H - 4);
    ctx.save();
    ctx.translate(10, H - 20);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('time ↑', 0, 0);
    ctx.restore();
  }, [amplitude]);

  return (
    <canvas
      ref={canvasRef}
      width={400}
      height={300}
      className="rounded border border-gray-800 w-full"
      style={{ display: 'block', maxWidth: 400 }}
    />
  );
}

// ---------------------------------------------------------------------------
// PhaseConstellation — I/Q scatter, 200×200 canvas
// ---------------------------------------------------------------------------

interface PhaseConstellationProps {
  iq: Float32Array | null;
}

function PhaseConstellation({ iq }: PhaseConstellationProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const W = canvas.width;
    const H = canvas.height;
    const cx = W / 2;
    const cy = H / 2;
    const scale = (W / 2) * 0.85;

    ctx.clearRect(0, 0, W, H);

    // Background
    ctx.fillStyle = '#0a0f1a';
    ctx.fillRect(0, 0, W, H);

    // Grid circles
    ctx.strokeStyle = 'rgba(34,68,85,0.4)';
    ctx.lineWidth = 0.5;
    for (const r of [0.33, 0.66, 1.0]) {
      ctx.beginPath();
      ctx.arc(cx, cy, scale * r, 0, Math.PI * 2);
      ctx.stroke();
    }

    // Crosshairs
    ctx.strokeStyle = 'rgba(34,68,85,0.5)';
    ctx.lineWidth = 0.5;
    ctx.beginPath();
    ctx.moveTo(cx, 4); ctx.lineTo(cx, H - 4);
    ctx.moveTo(4, cy); ctx.lineTo(W - 4, cy);
    ctx.stroke();

    // Scatter points
    if (iq && iq.length >= IQ_POINTS * 2) {
      // Compute phase variance for color shift (mirrors original signal-viz.js)
      let variance = 0;
      let meanI = 0;
      let meanQ = 0;
      for (let i = 0; i < IQ_POINTS; i++) {
        meanI += iq[i * 2];
        meanQ += iq[i * 2 + 1];
      }
      meanI /= IQ_POINTS;
      meanQ /= IQ_POINTS;
      for (let i = 0; i < IQ_POINTS; i++) {
        variance += (iq[i * 2] - meanI) ** 2 + (iq[i * 2 + 1] - meanQ) ** 2;
      }
      variance /= IQ_POINTS;
      const activity = Math.min(1, variance / 2);
      // hue: green (120°) → yellow-green on activity
      const hue = Math.round(120 - activity * 54);
      const lig = Math.round(35 + activity * 30);

      for (let i = 0; i < IQ_POINTS; i++) {
        const re = iq[i * 2];
        const im = iq[i * 2 + 1];
        const px = cx + re * scale;
        const py = cy - im * scale; // canvas Y inverted

        ctx.beginPath();
        ctx.arc(px, py, 2.5, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${hue},100%,${lig}%,0.8)`;
        ctx.fill();
      }

      // Unit circle guide
      ctx.strokeStyle = `hsla(${hue},60%,30%,0.35)`;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(cx, cy, scale, 0, Math.PI * 2);
      ctx.stroke();
    }

    // Axis labels
    ctx.fillStyle = '#4b6a88';
    ctx.font = '9px monospace';
    ctx.fillText('I', W - 10, cy - 4);
    ctx.fillText('Q', cx + 4, 10);
  }, [iq]);

  return (
    <canvas
      ref={canvasRef}
      width={200}
      height={200}
      className="rounded border border-gray-800"
      style={{ display: 'block' }}
    />
  );
}

// ---------------------------------------------------------------------------
// DopplerSpectrum — 16-bar chart, 300×150 canvas
// ---------------------------------------------------------------------------

interface DopplerSpectrumProps {
  doppler: Float32Array | null;
}

function DopplerSpectrum({ doppler }: DopplerSpectrumProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  // Smooth displayed heights to avoid jitter (lerp toward target)
  const smoothRef = useRef<Float32Array>(new Float32Array(DOPPLER_BARS));

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const W = canvas.width;
    const H = canvas.height;
    const barSlot = W / DOPPLER_BARS;
    const barW = barSlot * 0.75;
    const gap = barSlot * 0.25;
    const baselineY = H - 16;
    const maxBarH = baselineY - 8;

    ctx.clearRect(0, 0, W, H);

    // Background
    ctx.fillStyle = '#0a0f1a';
    ctx.fillRect(0, 0, W, H);

    // Baseline
    ctx.strokeStyle = 'rgba(51,85,119,0.5)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, baselineY);
    ctx.lineTo(W, baselineY);
    ctx.stroke();

    const smooth = smoothRef.current;

    for (let i = 0; i < DOPPLER_BARS; i++) {
      const target = doppler ? (doppler[i] ?? 0) : 0;
      // Lerp: fast attack (0.3) slow decay (0.08)
      smooth[i] += target > smooth[i]
        ? (target - smooth[i]) * 0.35
        : (target - smooth[i]) * 0.08;
      smooth[i] = Math.max(0.005, smooth[i]);

      const barH = smooth[i] * maxBarH;
      const x = gap / 2 + i * barSlot;
      const y = baselineY - barH;

      // Bar fill
      const grad = ctx.createLinearGradient(x, y, x, baselineY);
      grad.addColorStop(0, dopplerColor(smooth[i]));
      grad.addColorStop(1, 'rgba(0,20,40,0.4)');
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.roundRect(x, y, barW, barH, [2, 2, 0, 0]);
      ctx.fill();
    }

    // Frequency bin labels (every 4th)
    ctx.fillStyle = '#4b6a88';
    ctx.font = '8px monospace';
    ctx.textAlign = 'center';
    for (let i = 0; i < DOPPLER_BARS; i += 4) {
      const x = gap / 2 + i * barSlot + barW / 2;
      ctx.fillText(String(i), x, H - 3);
    }
    ctx.textAlign = 'left';
  }, [doppler]);

  return (
    <canvas
      ref={canvasRef}
      width={300}
      height={150}
      className="rounded border border-gray-800 w-full"
      style={{ display: 'block', maxWidth: 300 }}
    />
  );
}

// ---------------------------------------------------------------------------
// SignalViz — compound component driving animated demo loop
// ---------------------------------------------------------------------------

export interface SignalVizProps {
  /** Device ID used for label display only. */
  deviceId?: string;
  /** When true the component self-animates using synthetic demo data. */
  demoMode?: boolean;
}

/**
 * SignalViz renders three CSI visualization panels side-by-side.
 * It drives an rAF loop that generates synthetic demo data blended with
 * live csi_amplitude from the signal store.
 */
export function SignalViz({ deviceId, demoMode = true }: SignalVizProps) {
  const signalHistory = useSignalStore((s) => s.history);

  // Per-frame data refs (avoids re-rendering on every frame; canvases pull)
  const ampRef   = useRef<Float32Array>(new Float32Array(SUBCARRIERS));
  const iqRef    = useRef<Float32Array>(new Float32Array(IQ_POINTS * 2));
  const dopRef   = useRef<Float32Array>(new Float32Array(DOPPLER_BARS));
  const frameRef = useRef<number>(0);
  const tRef     = useRef<number>(0);

  // Expose refs as "current data" props — panels subscribe via their own effects
  // We use counter state to trigger panel re-renders each animation frame.
  const tickRef = useRef(0);
  const ampStateRef   = useRef<Float32Array | null>(null);
  const iqStateRef    = useRef<Float32Array | null>(null);
  const dopStateRef   = useRef<Float32Array | null>(null);

  // Stable draw callback
  const draw = useCallback(() => {
    tRef.current += 0.016; // ~60fps

    // Bias from live store: last csi_amplitude scalar (0 if no data)
    const liveBias =
      signalHistory.length > 0
        ? (signalHistory[signalHistory.length - 1].csi_amplitude ?? 0.5)
        : 0.5;

    const data = generateDemoData(tRef.current, liveBias);

    // Copy into stable refs
    ampRef.current.set(data.amplitude);
    iqRef.current.set(data.iq);
    dopRef.current.set(data.doppler);

    // Snapshot refs for React components (new Float32Array triggers useEffect)
    ampStateRef.current  = new Float32Array(data.amplitude);
    iqStateRef.current   = new Float32Array(data.iq);
    dopStateRef.current  = new Float32Array(data.doppler);
    tickRef.current += 1;

    // Manually trigger canvas redraws by dispatching to child canvas useEffects
    // We do this by storing refs to the child redraw functions.
    if (heatmapDrawRef.current)      heatmapDrawRef.current(ampStateRef.current);
    if (constellationDrawRef.current) constellationDrawRef.current(iqStateRef.current);
    if (dopplerDrawRef.current)       dopplerDrawRef.current(dopStateRef.current);

    frameRef.current = requestAnimationFrame(draw);
  }, [signalHistory]);

  // Refs to imperative draw callbacks registered by child canvases
  const heatmapDrawRef      = useRef<((a: Float32Array) => void) | null>(null);
  const constellationDrawRef = useRef<((iq: Float32Array) => void) | null>(null);
  const dopplerDrawRef       = useRef<((d: Float32Array) => void) | null>(null);

  useEffect(() => {
    if (!demoMode) return;
    frameRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frameRef.current);
  }, [draw, demoMode]);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <p className="text-xs text-gray-500 uppercase tracking-wider">
          CSI 신호 시각화{deviceId ? ` — ${deviceId}` : ''}
        </p>
        <span className="text-[10px] font-mono text-cyan-700 border border-cyan-900/40 rounded px-1.5 py-0.5">
          {demoMode ? 'DEMO' : 'LIVE'}
        </span>
      </div>

      {/* Panel row */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* Heatmap */}
        <div className="flex flex-col gap-1.5">
          <span className="text-[10px] text-gray-600 uppercase tracking-widest font-mono">
            CSI AMPLITUDE — {SUBCARRIERS} subcarriers × {TIME_SLOTS} slots
          </span>
          <AnimatedHeatmap registerDraw={(fn) => { heatmapDrawRef.current = fn; }} />
        </div>

        {/* Constellation */}
        <div className="flex flex-col gap-1.5">
          <span className="text-[10px] text-gray-600 uppercase tracking-widest font-mono">
            PHASE CONSTELLATION — {IQ_POINTS} pts I/Q
          </span>
          <AnimatedConstellation registerDraw={(fn) => { constellationDrawRef.current = fn; }} />
        </div>

        {/* Doppler */}
        <div className="flex flex-col gap-1.5">
          <span className="text-[10px] text-gray-600 uppercase tracking-widest font-mono">
            DOPPLER SPECTRUM — {DOPPLER_BARS} bins
          </span>
          <AnimatedDoppler registerDraw={(fn) => { dopplerDrawRef.current = fn; }} />
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Animated canvas wrappers — accept an imperative draw callback register
// These let the parent rAF loop push data directly to the canvases without
// React re-render overhead on every frame.
// ---------------------------------------------------------------------------

function AnimatedHeatmap({ registerDraw }: { registerDraw: (fn: (a: Float32Array) => void) => void }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const historyRef = useRef<Float32Array[]>(
    Array.from({ length: TIME_SLOTS }, () => new Float32Array(SUBCARRIERS)),
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    function draw(amplitude: Float32Array) {
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      // Push new row
      historyRef.current.shift();
      historyRef.current.push(new Float32Array(amplitude));

      const W = canvas.width;
      const H = canvas.height;
      const cellW = W / SUBCARRIERS;
      const cellH = H / TIME_SLOTS;

      ctx.clearRect(0, 0, W, H);

      const history = historyRef.current;
      for (let t = 0; t < TIME_SLOTS; t++) {
        const row = history[t];
        for (let s = 0; s < SUBCARRIERS; s++) {
          const val = row[s] ?? 0;
          ctx.fillStyle = amplitudeColor(val);
          ctx.fillRect(
            Math.floor(s * cellW),
            Math.floor(t * cellH),
            Math.ceil(cellW - 0.5),
            Math.ceil(cellH - 0.5),
          );
        }
      }

      ctx.strokeStyle = 'rgba(51,85,119,0.4)';
      ctx.lineWidth = 1;
      ctx.strokeRect(0.5, 0.5, W - 1, H - 1);

      ctx.fillStyle = '#3a5570';
      ctx.font = '9px monospace';
      ctx.fillText('sc →', 4, H - 4);
    }

    registerDraw(draw);
  }, [registerDraw]);

  return (
    <canvas
      ref={canvasRef}
      width={400}
      height={300}
      className="rounded border border-gray-800 w-full"
      style={{ display: 'block', maxWidth: 400 }}
    />
  );
}

function AnimatedConstellation({ registerDraw }: { registerDraw: (fn: (iq: Float32Array) => void) => void }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    function draw(iq: Float32Array) {
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const W = canvas.width;
      const H = canvas.height;
      const cxC = W / 2;
      const cyC = H / 2;
      const scale = (W / 2) * 0.85;

      ctx.clearRect(0, 0, W, H);
      ctx.fillStyle = '#0a0f1a';
      ctx.fillRect(0, 0, W, H);

      // Guide circles
      ctx.strokeStyle = 'rgba(34,68,85,0.4)';
      ctx.lineWidth = 0.5;
      for (const r of [0.33, 0.66, 1.0]) {
        ctx.beginPath();
        ctx.arc(cxC, cyC, scale * r, 0, Math.PI * 2);
        ctx.stroke();
      }

      // Crosshairs
      ctx.strokeStyle = 'rgba(34,68,85,0.5)';
      ctx.lineWidth = 0.5;
      ctx.beginPath();
      ctx.moveTo(cxC, 4); ctx.lineTo(cxC, H - 4);
      ctx.moveTo(4, cyC); ctx.lineTo(W - 4, cyC);
      ctx.stroke();

      if (iq.length >= IQ_POINTS * 2) {
        let variance = 0;
        let mI = 0; let mQ = 0;
        for (let i = 0; i < IQ_POINTS; i++) { mI += iq[i * 2]; mQ += iq[i * 2 + 1]; }
        mI /= IQ_POINTS; mQ /= IQ_POINTS;
        for (let i = 0; i < IQ_POINTS; i++) {
          variance += (iq[i * 2] - mI) ** 2 + (iq[i * 2 + 1] - mQ) ** 2;
        }
        variance /= IQ_POINTS;
        const activity = Math.min(1, variance / 2);
        const hue = Math.round(120 - activity * 54);
        const lig = Math.round(35 + activity * 30);

        for (let i = 0; i < IQ_POINTS; i++) {
          const re = iq[i * 2];
          const im = iq[i * 2 + 1];
          ctx.beginPath();
          ctx.arc(cxC + re * scale, cyC - im * scale, 2.5, 0, Math.PI * 2);
          ctx.fillStyle = `hsla(${hue},100%,${lig}%,0.8)`;
          ctx.fill();
        }

        ctx.strokeStyle = `hsla(${hue},60%,30%,0.35)`;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(cxC, cyC, scale, 0, Math.PI * 2);
        ctx.stroke();
      }

      ctx.fillStyle = '#4b6a88';
      ctx.font = '9px monospace';
      ctx.fillText('I', W - 10, cyC - 4);
      ctx.fillText('Q', cxC + 4, 10);
    }

    registerDraw(draw);
  }, [registerDraw]);

  return (
    <canvas
      ref={canvasRef}
      width={200}
      height={200}
      className="rounded border border-gray-800"
      style={{ display: 'block' }}
    />
  );
}

function AnimatedDoppler({ registerDraw }: { registerDraw: (fn: (d: Float32Array) => void) => void }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const smoothRef = useRef<Float32Array>(new Float32Array(DOPPLER_BARS));

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    function draw(doppler: Float32Array) {
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const W = canvas.width;
      const H = canvas.height;
      const barSlot = W / DOPPLER_BARS;
      const barW = barSlot * 0.75;
      const gap = barSlot * 0.25;
      const baselineY = H - 16;
      const maxBarH = baselineY - 8;

      ctx.clearRect(0, 0, W, H);
      ctx.fillStyle = '#0a0f1a';
      ctx.fillRect(0, 0, W, H);

      ctx.strokeStyle = 'rgba(51,85,119,0.5)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, baselineY);
      ctx.lineTo(W, baselineY);
      ctx.stroke();

      const smooth = smoothRef.current;
      for (let i = 0; i < DOPPLER_BARS; i++) {
        const target = doppler[i] ?? 0;
        smooth[i] += target > smooth[i]
          ? (target - smooth[i]) * 0.35
          : (target - smooth[i]) * 0.08;
        smooth[i] = Math.max(0.005, smooth[i]);

        const barH = smooth[i] * maxBarH;
        const x = gap / 2 + i * barSlot;
        const y = baselineY - barH;

        const grad = ctx.createLinearGradient(x, y, x, baselineY);
        grad.addColorStop(0, dopplerColor(smooth[i]));
        grad.addColorStop(1, 'rgba(0,20,40,0.4)');
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.roundRect(x, y, barW, barH, [2, 2, 0, 0]);
        ctx.fill();
      }

      ctx.fillStyle = '#4b6a88';
      ctx.font = '8px monospace';
      ctx.textAlign = 'center';
      for (let i = 0; i < DOPPLER_BARS; i += 4) {
        const x = gap / 2 + i * barSlot + barW / 2;
        ctx.fillText(String(i), x, H - 3);
      }
      ctx.textAlign = 'left';
    }

    registerDraw(draw);
  }, [registerDraw]);

  return (
    <canvas
      ref={canvasRef}
      width={300}
      height={150}
      className="rounded border border-gray-800 w-full"
      style={{ display: 'block', maxWidth: 300 }}
    />
  );
}

// ---------------------------------------------------------------------------
// Also export individual panels for ad-hoc use
// ---------------------------------------------------------------------------
export { CsiHeatmap, PhaseConstellation, DopplerSpectrum };
