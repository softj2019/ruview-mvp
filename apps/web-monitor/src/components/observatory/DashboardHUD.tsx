/**
 * DashboardHUD — 실시간 관측소 오버레이 HUD
 * Phase 2-14 | 참조: ruvnet-RuView/ui/components/dashboard-hud.js
 * 's' 키로 표시/숨김 토글
 */
import { useEffect, useRef, useState } from 'react';

type SensingMode = 'signal' | 'model' | 'simulated';

interface Props {
  fps: number;
  connected: boolean;
  personCount: number;
  confidence: number;   // 0.0 ~ 1.0
  mode: SensingMode;
  visible?: boolean;
}

// FPS 색상 등급
function fpsClass(fps: number): string {
  if (fps >= 50) return 'text-emerald-400';
  if (fps >= 25) return 'text-amber-400';
  return 'text-red-400';
}

// 신뢰도 → hsl 색상 (빨강→노랑→녹색)
function confColor(conf: number): string {
  const hue = Math.round(conf * 120);
  return `hsl(${hue},100%,45%)`;
}

// 모드 배지 스타일
const MODE_STYLES: Record<SensingMode, { label: string; cls: string }> = {
  signal: {
    label: 'Signal-Derived',
    cls: 'bg-blue-900/70 border border-blue-500 text-blue-200',
  },
  model: {
    label: 'Model Inference',
    cls: 'bg-purple-900/70 border border-purple-500 text-purple-200',
  },
  simulated: {
    label: 'SIMULATED',
    cls: 'bg-amber-900/70 border border-amber-500 text-amber-200',
  },
};

// 연결 상태 뱃지
function ConnectionBadge({ connected }: { connected: boolean }) {
  return (
    <div className="flex items-center gap-1.5">
      <span
        className={`inline-block w-2 h-2 rounded-full ${
          connected
            ? 'bg-emerald-400 shadow-[0_0_6px_#34d399] animate-pulse'
            : 'bg-gray-600'
        }`}
      />
      <span
        className={`text-xs font-bold tracking-wide ${
          connected ? 'text-emerald-300' : 'text-gray-500'
        }`}
      >
        {connected ? 'Connected' : 'Disconnected'}
      </span>
    </div>
  );
}

export default function DashboardHUD({
  fps,
  connected,
  personCount,
  confidence,
  mode,
  visible: visibleProp = true,
}: Props) {
  const [visible, setVisible] = useState(visibleProp);
  const prevVisibleProp = useRef(visibleProp);

  // prop이 바뀌면 반영
  useEffect(() => {
    if (prevVisibleProp.current !== visibleProp) {
      prevVisibleProp.current = visibleProp;
      setVisible(visibleProp);
    }
  }, [visibleProp]);

  // 's' 키 토글
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 's' || e.key === 'S') {
        // 입력 필드에서는 무시
        const tag = (e.target as HTMLElement).tagName;
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
        setVisible((v) => !v);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  if (!visible) return null;

  const modeStyle = MODE_STYLES[mode];
  const confPct = Math.round(confidence * 100);
  const isReal = mode !== 'simulated';

  return (
    <div
      className="absolute inset-0 pointer-events-none z-50 font-mono"
      aria-hidden="true"
    >
      {/* 상단 배너 — 데이터 소스 표시 */}
      <div
        className={`absolute top-0 left-0 right-0 text-center py-1.5 text-xs font-bold tracking-[0.2em] uppercase z-[110] ${
          isReal
            ? 'bg-gradient-to-r from-emerald-900/85 via-emerald-800/85 to-emerald-900/85 border-b border-emerald-500 text-white'
            : 'bg-gradient-to-r from-amber-900/85 via-amber-800/85 to-amber-900/85 border-b border-amber-500 text-white'
        }`}
      >
        {isReal ? 'Live Stream' : 'Demo Mode — Simulated Data'}
      </div>

      {/* 코너 브래킷 장식 */}
      <span className="absolute top-9 left-1 w-5 h-5 border-t border-l border-blue-500/30" />
      <span className="absolute top-9 right-1 w-5 h-5 border-t border-r border-blue-500/30" />
      <span className="absolute bottom-1 left-1 w-5 h-5 border-b border-l border-blue-500/30" />
      <span className="absolute bottom-1 right-1 w-5 h-5 border-b border-r border-blue-500/30" />

      {/* 좌상단 — 연결 정보 */}
      <div className="absolute top-10 left-3 flex flex-col gap-1">
        <ConnectionBadge connected={connected} />
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-[9px] uppercase tracking-widest text-blue-900 min-w-[60px]">
            Persons
          </span>
          <span
            className="text-sm font-bold leading-none"
            style={{ color: personCount > 0 ? '#34d399' : '#475569' }}
          >
            {personCount}
          </span>
        </div>
      </div>

      {/* 우상단 — FPS */}
      <div className="absolute top-10 right-3 flex flex-col items-end gap-0.5">
        <span className={`text-2xl font-bold leading-none tabular-nums ${fpsClass(fps)}`}>
          {fps}
        </span>
        <span className="text-[9px] text-blue-900 tracking-widest uppercase">FPS</span>
      </div>

      {/* 좌하단 — 신뢰도 */}
      <div className="absolute bottom-3 left-3 flex flex-col gap-1 min-w-[130px]">
        <div className="flex items-center justify-between">
          <span className="text-[9px] text-blue-900 uppercase tracking-widest">Confidence</span>
          <span
            className="text-xs font-bold tabular-nums"
            style={{ color: confColor(confidence) }}
          >
            {confPct}%
          </span>
        </div>
        {/* 신뢰도 바 */}
        <div className="h-1.5 w-full rounded-full bg-gray-900/80 border border-gray-800 overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-300"
            style={{
              width: `${confPct}%`,
              background: confColor(confidence),
            }}
          />
        </div>
      </div>

      {/* 우하단 — 센싱 모드 */}
      <div className="absolute bottom-3 right-3 flex flex-col items-end gap-1">
        <span
          className={`px-2 py-0.5 rounded text-[10px] font-bold tracking-wider uppercase ${modeStyle.cls}`}
        >
          {modeStyle.label}
        </span>
        <span className="text-[9px] text-blue-900 tracking-widest">WiFi CSI</span>
      </div>

      {/* 하단 중앙 — 키 힌트 */}
      <div className="absolute bottom-12 left-1/2 -translate-x-1/2 text-[9px] text-gray-700 tracking-widest text-center opacity-60">
        [S] toggle HUD
      </div>
    </div>
  );
}
