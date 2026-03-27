/**
 * SignalVizPanel — Phase 2-4
 * CSI 실시간 신호 시각화: 진폭 히트맵, 위상 플롯, 도플러 스펙트럼, 모션 에너지
 * 참조: ruvnet-RuView/ui/components/signal-viz.js
 */
import { useRef, useEffect, useCallback } from 'react';
import { useDeviceStore } from '@/stores/deviceStore';
import { Card, CardHeader } from '@/components/ui';

// ---- 상수 ----------------------------------------------------------------

const SUBCARRIERS = 30;
const TIME_SLOTS = 40;
const DOPPLER_BARS = 16;

// ---- 타입 ----------------------------------------------------------------

interface SignalVizData {
  amplitude: Float32Array; // length 30
  phase: Float32Array;     // length 30 (radians)
  doppler: Float32Array;   // length 16
  motionEnergy: number;    // 0–1
}

export interface SignalVizPanelProps {
  deviceId: string;
  width?: number;
  height?: number;
}

// ---- 헬퍼 ----------------------------------------------------------------

/** HSL → RGB (0–255) 변환 */
function hslToRgb(h: number, s: number, l: number): [number, number, number] {
  const a = s * Math.min(l, 1 - l);
  const f = (n: number) => {
    const k = (n + h * 12) % 12;
    return Math.round(255 * (l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1))));
  };
  return [f(0), f(8), f(4)];
}

/** 진폭값(0–1) → 히트맵 색상 (파란→청록→노란→빨간) */
function amplitudeToColor(val: number): [number, number, number] {
  const h = 0.6 - val * 0.6;
  const l = 0.1 + val * 0.5;
  return hslToRgb(h, 0.9, l);
}

/** 도플러 바 색상: 파란→보라 */
function dopplerToColor(val: number): [number, number, number] {
  const h = 0.7 - val * 0.3;
  const l = 0.25 + val * 0.35;
  return hslToRgb(h, 0.8, l);
}

/** 데모 신호 데이터 생성 */
function generateDemoData(elapsed: number): SignalVizData {
  const amplitude = new Float32Array(SUBCARRIERS);
  for (let i = 0; i < SUBCARRIERS; i++) {
    const base = Math.sin(elapsed * 2 + i * 0.3) * 0.3;
    const body = Math.sin(elapsed * 0.8 + i * 0.15) * 0.25;
    const noise = (Math.random() - 0.5) * 0.1;
    amplitude[i] = Math.max(0, Math.min(1, 0.4 + base + body + noise));
  }

  const phase = new Float32Array(SUBCARRIERS);
  for (let i = 0; i < SUBCARRIERS; i++) {
    phase[i] = (i / SUBCARRIERS) * Math.PI * 2 + Math.sin(elapsed * 1.5 + i * 0.2) * 0.8;
  }

  const doppler = new Float32Array(DOPPLER_BARS);
  const centerBin = DOPPLER_BARS / 2 + Math.sin(elapsed * 0.7) * 3;
  for (let i = 0; i < DOPPLER_BARS; i++) {
    const dist = Math.abs(i - centerBin);
    doppler[i] = Math.max(0, Math.min(1,
      Math.exp(-dist * dist * 0.15) * (0.6 + Math.sin(elapsed * 1.2) * 0.3)
      + (Math.random() - 0.5) * 0.05,
    ));
  }

  const motionEnergy = (Math.sin(elapsed * 0.5) + 1) / 2 * 0.7 + 0.15;
  return { amplitude, phase, doppler, motionEnergy };
}

// ---- 렌더러 내부 상태 ----------------------------------------------------

interface RenderState {
  amplitudeHistory: Float32Array[];
  phase: Float32Array;
  doppler: Float32Array;
  motionEnergy: number;
  targetMotionEnergy: number;
  dopplerSmoothed: Float32Array;
  startTime: number;
  animId: number;
}

// ---- 컴포넌트 ------------------------------------------------------------

export default function SignalVizPanel({ deviceId, width = 560, height = 320 }: SignalVizPanelProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stateRef = useRef<RenderState | null>(null);
  const device = useDeviceStore((s) => s.devices.find((d) => d.id === deviceId));

  // 렌더 상태 초기화
  const initState = useCallback((): RenderState => {
    const history: Float32Array[] = [];
    for (let i = 0; i < TIME_SLOTS; i++) history.push(new Float32Array(SUBCARRIERS));
    return {
      amplitudeHistory: history,
      phase: new Float32Array(SUBCARRIERS),
      doppler: new Float32Array(DOPPLER_BARS),
      motionEnergy: 0,
      targetMotionEnergy: 0,
      dopplerSmoothed: new Float32Array(DOPPLER_BARS),
      startTime: performance.now(),
      animId: 0,
    };
  }, []);

  // 디바이스 데이터 → 렌더 상태 업데이트
  useEffect(() => {
    if (!device || !stateRef.current) return;
    const st = stateRef.current;
    // motion_energy를 targetMotionEnergy로 업데이트
    if (device.motion_energy !== undefined) {
      st.targetMotionEnergy = Math.max(0, Math.min(1, device.motion_energy));
    }
  }, [device]);

  // Canvas 렌더 루프
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const state = initState();
    stateRef.current = state;

    let lastTime = performance.now();

    const draw = (now: number) => {
      state.animId = requestAnimationFrame(draw);
      const delta = Math.min((now - lastTime) / 1000, 0.1);
      lastTime = now;
      const elapsed = (now - state.startTime) / 1000;

      // 데모 데이터로 신호 채우기 (실제 디바이스 데이터가 없을 때)
      const demo = generateDemoData(elapsed);

      // 히스토리 시프트 후 새 행 추가
      state.amplitudeHistory.shift();
      state.amplitudeHistory.push(new Float32Array(demo.amplitude));
      state.phase = demo.phase;

      // 도플러 스무딩
      for (let i = 0; i < DOPPLER_BARS; i++) {
        state.dopplerSmoothed[i] += (demo.doppler[i] - state.dopplerSmoothed[i]) * Math.min(1, delta * 8);
      }

      // motionEnergy 스무딩
      const targetEnergy = device?.motion_energy !== undefined ? device.motion_energy : demo.motionEnergy;
      state.targetMotionEnergy = Math.max(0, Math.min(1, targetEnergy));
      state.motionEnergy += (state.targetMotionEnergy - state.motionEnergy) * Math.min(1, delta * 5);

      // ── 캔버스 클리어 ──────────────────────────────────────────────────
      ctx.fillStyle = '#030712';
      ctx.fillRect(0, 0, width, height);

      // 레이아웃 영역 정의
      const pad = 10;
      const labelH = 14;
      const heatmapW = width * 0.46;
      const heatmapH = height * 0.55;
      const phaseH = height * 0.28;
      const rightX = heatmapW + pad * 2;
      const rightW = width - rightX - pad;
      const dopplerH = height * 0.55;

      // ── 진폭 히트맵 ───────────────────────────────────────────────────
      drawHeatmap(ctx, state.amplitudeHistory, pad, labelH + pad, heatmapW, heatmapH);
      ctx.fillStyle = '#4a7a99';
      ctx.font = '10px monospace';
      ctx.fillText('CSI AMPLITUDE', pad, pad + labelH - 2);

      // ── 위상 플롯 ─────────────────────────────────────────────────────
      const phaseY = heatmapH + labelH + pad * 2;
      drawPhasePlot(ctx, state.phase, pad, phaseY + labelH, heatmapW, phaseH);
      ctx.fillStyle = '#4a7a99';
      ctx.fillText('PHASE', pad, phaseY + labelH - 2);

      // ── 도플러 스펙트럼 ───────────────────────────────────────────────
      drawDopplerSpectrum(ctx, state.dopplerSmoothed, rightX, labelH + pad, rightW, dopplerH);
      ctx.fillStyle = '#4a7a99';
      ctx.fillText('DOPPLER SPECTRUM', rightX, pad + labelH - 2);

      // ── 모션 에너지 인디케이터 ────────────────────────────────────────
      const motionY = dopplerH + labelH + pad * 2;
      drawMotionIndicator(ctx, state.motionEnergy, rightX + rightW / 2, motionY + (height - motionY) / 2, elapsed);
      ctx.fillStyle = '#4a7a99';
      ctx.fillText('MOTION', rightX, motionY + labelH - 2);
    };

    state.animId = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(state.animId);
      stateRef.current = null;
    };
  }, [width, height, device, initState]);

  return (
    <Card className="overflow-hidden">
      <CardHeader>신호 시각화 — {deviceId}</CardHeader>
      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        className="block w-full rounded-b-lg"
        style={{ imageRendering: 'pixelated' }}
      />
    </Card>
  );
}

// ---- 드로우 함수들 -------------------------------------------------------

function drawHeatmap(
  ctx: CanvasRenderingContext2D,
  history: Float32Array[],
  x: number, y: number,
  w: number, h: number,
) {
  const cellW = w / SUBCARRIERS;
  const cellH = h / TIME_SLOTS;

  for (let t = 0; t < TIME_SLOTS; t++) {
    const row = history[t];
    for (let s = 0; s < SUBCARRIERS; s++) {
      const val = row[s] ?? 0;
      const [r, g, b] = amplitudeToColor(val);
      ctx.fillStyle = `rgb(${r},${g},${b})`;
      ctx.fillRect(
        x + s * cellW + 0.5,
        y + t * cellH + 0.5,
        cellW * 0.9,
        cellH * 0.9,
      );
    }
  }

  // 테두리
  ctx.strokeStyle = 'rgba(51,85,119,0.5)';
  ctx.lineWidth = 1;
  ctx.strokeRect(x, y, w, h);
}

function drawPhasePlot(
  ctx: CanvasRenderingContext2D,
  phaseData: Float32Array,
  x: number, y: number,
  w: number, h: number,
) {
  // 배경
  ctx.fillStyle = 'rgba(0,8,16,0.5)';
  ctx.fillRect(x, y, w, h);

  // 제로 라인
  ctx.strokeStyle = 'rgba(34,68,51,0.4)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(x, y + h / 2);
  ctx.lineTo(x + w, y + h / 2);
  ctx.stroke();

  // 위상 분산 계산 → 색상 결정
  let mean = 0;
  for (let i = 0; i < SUBCARRIERS; i++) mean += phaseData[i] ?? 0;
  mean /= SUBCARRIERS;
  let variance = 0;
  for (let i = 0; i < SUBCARRIERS; i++) {
    const d = (phaseData[i] ?? 0) - mean;
    variance += d * d;
  }
  variance /= SUBCARRIERS;
  const activity = Math.min(1, variance / 2);
  const hue = Math.round((0.3 - activity * 0.15) * 360);
  const light = Math.round((0.35 + activity * 0.3) * 100);

  // 위상 라인
  ctx.strokeStyle = `hsl(${hue},100%,${light}%)`;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  for (let i = 0; i < SUBCARRIERS; i++) {
    const px = x + (i / (SUBCARRIERS - 1)) * w;
    const phase = phaseData[i] ?? 0;
    const py = y + h / 2 - (phase / Math.PI) * (h / 2);
    if (i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  }
  ctx.stroke();

  // 테두리
  ctx.strokeStyle = 'rgba(51,85,119,0.3)';
  ctx.lineWidth = 1;
  ctx.strokeRect(x, y, w, h);
}

function drawDopplerSpectrum(
  ctx: CanvasRenderingContext2D,
  dopplerData: Float32Array,
  x: number, y: number,
  w: number, h: number,
) {
  const barW = (w / DOPPLER_BARS) * 0.8;
  const gapW = (w / DOPPLER_BARS) * 0.2;

  // 배경
  ctx.fillStyle = 'rgba(0,8,16,0.5)';
  ctx.fillRect(x, y, w, h);

  for (let i = 0; i < DOPPLER_BARS; i++) {
    const val = dopplerData[i] ?? 0;
    const barH = Math.max(1, val * h);
    const bx = x + i * (barW + gapW) + gapW / 2;
    const by = y + h - barH;

    const [r, g, b] = dopplerToColor(val);
    ctx.fillStyle = `rgba(${r},${g},${b},0.75)`;
    ctx.fillRect(bx, by, barW, barH);
  }

  // 베이스 라인
  ctx.strokeStyle = 'rgba(51,85,119,0.5)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(x, y + h);
  ctx.lineTo(x + w, y + h);
  ctx.stroke();

  ctx.strokeRect(x, y, w, h);
}

function drawMotionIndicator(
  ctx: CanvasRenderingContext2D,
  energy: number,
  cx: number, cy: number,
  elapsed: number,
) {
  const radius = 20 + energy * 12;

  // 펄스 링들
  for (let i = 0; i < 3; i++) {
    const phase = (i / 3) * Math.PI * 2 + elapsed * (1 + energy * 3);
    const t = (Math.sin(phase) + 1) / 2;
    const scale = 1 + t * energy * 1.8;
    const opacity = (1 - t) * energy * 0.4;
    ctx.beginPath();
    ctx.arc(cx, cy, radius * scale, 0, Math.PI * 2);
    ctx.strokeStyle = `rgba(0,255,136,${opacity})`;
    ctx.lineWidth = 1.5;
    ctx.stroke();
  }

  // 외부 링
  const ringOpacity = 0.15 + energy * 0.5;
  const ringHue = Math.round((0.3 - energy * 0.15) * 360);
  const ringLight = Math.round((0.4 + energy * 0.3) * 100);
  ctx.beginPath();
  ctx.arc(cx, cy, radius + 4, 0, Math.PI * 2);
  ctx.strokeStyle = `hsla(${ringHue},100%,${ringLight}%,${ringOpacity})`;
  ctx.lineWidth = 3;
  ctx.stroke();

  // 코어 구체 (원)
  const coreR = radius * (0.8 + energy * 0.7) * 0.6;
  const coreHue = Math.round((0.3 - energy * 0.2) * 360);
  const coreLight = Math.round((0.15 + energy * 0.4) * 100);
  const coreOpacity = 0.4 + energy * 0.5;
  const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreR);
  grad.addColorStop(0, `hsla(${coreHue},100%,${coreLight + 20}%,${coreOpacity})`);
  grad.addColorStop(1, `hsla(${coreHue},100%,${coreLight}%,0)`);
  ctx.beginPath();
  ctx.arc(cx, cy, coreR, 0, Math.PI * 2);
  ctx.fillStyle = grad;
  ctx.fill();

  // 에너지 수치 텍스트
  ctx.fillStyle = '#6b9eb0';
  ctx.font = '9px monospace';
  ctx.textAlign = 'center';
  ctx.fillText(`${Math.round(energy * 100)}%`, cx, cy + radius + 18);
  ctx.textAlign = 'left';
}
