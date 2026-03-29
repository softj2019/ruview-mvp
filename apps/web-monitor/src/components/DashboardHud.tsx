/**
 * DashboardHud — 센싱 상태 HUD 오버레이
 * 참조: ruvnet/ui/components/dashboard-hud.js
 *
 * 연결 상태 / 레이턴시 / 메시지 수 / 업타임 / FPS / 인원 수 / 신뢰도 / 센싱 모드
 * 를 표시하는 React/Tailwind 변환본.
 */

import { useEffect, useState, useRef } from 'react';
import { sensingService, type ConnectionState, type DataSource } from '@/services/sensingService';
import { useDeviceStore } from '@/stores/deviceStore';
import { useSignalStore } from '@/stores/signalStore';

// ---- 타입 -----------------------------------------------------------------------

type SensingMode = 'CSI' | 'RSSI' | 'Mock';

interface HudState {
  connectionStatus: ConnectionState;
  dataSource: DataSource;
  latency: number;
  messageCount: number;
  uptimeSec: number;
  fps: number;
  personCount: number;
  confidence: number;
  sensingMode: SensingMode;
}

// ---- 헬퍼 -----------------------------------------------------------------------

function formatUptime(sec: number): string {
  if (sec < 60) return `${sec}s`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m ${sec % 60}s`;
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  return `${h}h ${m}m`;
}

function connLabel(status: ConnectionState): string {
  const map: Record<ConnectionState, string> = {
    connected: 'Connected',
    disconnected: 'Disconnected',
    connecting: 'Connecting...',
    reconnecting: 'Reconnecting...',
    simulated: 'Simulated',
  };
  return map[status] ?? 'Unknown';
}

// ---- 신뢰도 막대 색상 (0=red → 60=yellow → 120=green, HSL hue) -----------------
function confidenceBarStyle(confidence: number): React.CSSProperties {
  const hue = Math.round(confidence * 120);
  return {
    width: `${confidence * 100}%`,
    background: `hsl(${hue}, 100%, 45%)`,
    transition: 'width 0.3s ease, background 0.3s ease',
  };
}

// ---- 연결 상태 도트 색상 --------------------------------------------------------
function dotClass(status: ConnectionState): string {
  if (status === 'connected') return 'bg-emerald-400 shadow-[0_0_6px_#22c55e]';
  if (status === 'connecting' || status === 'reconnecting')
    return 'bg-amber-400 shadow-[0_0_6px_#f59e0b] animate-pulse';
  if (status === 'simulated') return 'bg-purple-400 shadow-[0_0_6px_#a78bfa]';
  return 'bg-gray-500';
}

// ---- 배너 설정 ------------------------------------------------------------------
function bannerConfig(dataSource: DataSource): { text: string; cls: string } {
  const map: Record<DataSource, { text: string; cls: string }> = {
    live: {
      text: 'REAL DATA — LIVE STREAM',
      cls: 'bg-gradient-to-r from-emerald-900/85 via-emerald-800/85 to-emerald-900/85 border-b border-emerald-500 text-white',
    },
    'server-simulated': {
      text: 'MOCK DATA — DEMO MODE',
      cls: 'bg-gradient-to-r from-amber-900/85 via-amber-800/85 to-amber-900/85 border-b border-amber-500 text-white',
    },
    reconnecting: {
      text: 'RECONNECTING...',
      cls: 'bg-gradient-to-r from-yellow-900/85 via-yellow-800/85 to-yellow-900/85 border-b border-yellow-400 text-white',
    },
    simulated: {
      text: 'MOCK DATA — DEMO MODE',
      cls: 'bg-gradient-to-r from-amber-900/85 via-amber-800/85 to-amber-900/85 border-b border-amber-500 text-white',
    },
  };
  return map[dataSource];
}

// ---- 센싱 모드 배지 ------------------------------------------------------------
function modeBadgeClass(mode: SensingMode): string {
  if (mode === 'CSI')
    return 'bg-blue-900/70 border border-blue-500 text-blue-200';
  if (mode === 'RSSI')
    return 'bg-purple-900/70 border border-purple-500 text-purple-200';
  return 'bg-amber-900/70 border border-amber-500 text-amber-200';
}

// ---- 컴포넌트 ------------------------------------------------------------------

export default function DashboardHud() {
  const devices = useDeviceStore((s) => s.devices);
  const signalHistory = useSignalStore((s) => s.history);

  const [hud, setHud] = useState<HudState>({
    connectionStatus: 'disconnected',
    dataSource: 'reconnecting',
    latency: 0,
    messageCount: 0,
    uptimeSec: 0,
    fps: 0,
    personCount: 0,
    confidence: 0,
    sensingMode: 'Mock',
  });

  // 업타임 카운터 시작 시각
  const startRef = useRef<number | null>(null);
  // 메시지 카운터
  const msgRef = useRef(0);

  // 연결 상태 구독
  useEffect(() => {
    const unsub = sensingService.onStateChange((state) => {
      if (state === 'connected' && startRef.current === null) {
        startRef.current = Date.now();
      }
      if (state !== 'connected') {
        startRef.current = null;
      }
      setHud((prev) => ({
        ...prev,
        connectionStatus: state,
        dataSource: sensingService.dataSource,
      }));
    });
    return unsub;
  }, []);

  // 데이터 구독 → 메시지 수, FPS, 신뢰도, 인원 수 업데이트
  useEffect(() => {
    const unsub = sensingService.onData((data) => {
      msgRef.current += 1;
      const fps = sensingService.getFps();
      const confidence = data.classification?.confidence ?? 0;
      const personCount = data.classification?.presence ? 1 : 0;

      // 서버 소스에서 센싱 모드 추론
      let sensingMode: SensingMode = 'Mock';
      if (sensingService.dataSource === 'live') {
        sensingMode = 'CSI';
      } else if (sensingService.serverSource === 'rssi') {
        sensingMode = 'RSSI';
      }

      setHud((prev) => ({
        ...prev,
        messageCount: msgRef.current,
        fps,
        confidence,
        personCount,
        sensingMode,
        dataSource: sensingService.dataSource,
      }));
    });
    return unsub;
  }, []);

  // 업타임 + 레이턴시 1초마다 갱신
  useEffect(() => {
    const id = setInterval(() => {
      const uptimeSec =
        startRef.current !== null
          ? Math.floor((Date.now() - startRef.current) / 1000)
          : 0;

      // 레이턴시: 마지막 신호 포인트 타임스탬프 기준 (근사값)
      const lastPoint = signalHistory[signalHistory.length - 1];
      const latency =
        lastPoint
          ? Math.min(999, Math.max(0, Date.now() - new Date(lastPoint.time).getTime()))
          : 0;

      setHud((prev) => ({ ...prev, uptimeSec, latency }));
    }, 1000);
    return () => clearInterval(id);
  }, [signalHistory]);

  // Zustand devices에서 인원 수 집계 (n_persons 합산)
  const totalPersons = devices.reduce((acc, d) => acc + (d.n_persons ?? 0), 0);
  const effectivePersonCount = totalPersons > 0 ? totalPersons : hud.personCount;

  const banner = bannerConfig(hud.dataSource);

  return (
    <div className="relative w-full rounded-xl overflow-hidden border border-gray-800 bg-gray-950 font-mono text-[11px] text-cyan-300 select-none">
      {/* 배너 */}
      <div
        className={`w-full text-center py-1.5 text-[12px] font-bold tracking-[3px] uppercase ${banner.cls}`}
      >
        {banner.text}
      </div>

      {/* HUD 본문 — 3열 그리드 */}
      <div className="grid grid-cols-3 gap-3 p-3">
        {/* 왼쪽: 연결 정보 */}
        <div className="space-y-1.5">
          {/* 연결 상태 */}
          <div className="flex items-center gap-1.5">
            <span
              className={`inline-block w-2 h-2 rounded-full flex-shrink-0 ${dotClass(hud.connectionStatus)}`}
            />
            <span className="text-cyan-200 font-bold text-[11px]">
              {connLabel(hud.connectionStatus)}
            </span>
          </div>

          <HudRow label="Latency" value={hud.latency > 0 ? `${hud.latency} ms` : '-- ms'} />
          <HudRow label="Messages" value={hud.messageCount.toLocaleString()} />
          <HudRow label="Uptime" value={formatUptime(hud.uptimeSec)} />
        </div>

        {/* 가운데: 인원 수 + 신뢰도 */}
        <div className="space-y-1.5">
          <div>
            <span className="text-[9px] uppercase tracking-widest text-blue-400/60">Persons</span>
            <div
              className="text-3xl font-bold leading-none mt-0.5"
              style={{ color: effectivePersonCount > 0 ? '#00ff88' : '#475569' }}
            >
              {effectivePersonCount}
            </div>
          </div>

          <div className="space-y-1">
            <div className="flex justify-between text-[9px]">
              <span className="uppercase tracking-widest text-blue-400/60">Confidence</span>
              <span className="text-cyan-200 font-bold">
                {(hud.confidence * 100).toFixed(1)}%
              </span>
            </div>
            {/* 신뢰도 막대 */}
            <div className="h-1.5 rounded-full bg-gray-800 border border-gray-700 overflow-hidden">
              <div className="h-full rounded-full" style={confidenceBarStyle(hud.confidence)} />
            </div>
          </div>
        </div>

        {/* 오른쪽: FPS + 센싱 모드 */}
        <div className="flex flex-col items-end gap-1.5">
          {/* FPS */}
          <div
            className="text-2xl font-bold leading-none"
            style={{
              color:
                hud.fps >= 50 ? '#00ff88' : hud.fps >= 25 ? '#f59e0b' : '#ef4444',
            }}
          >
            {hud.fps > 0 ? `${hud.fps} FPS` : '-- FPS'}
          </div>

          {/* 센싱 모드 배지 */}
          <span
            className={`px-2 py-0.5 rounded text-[10px] font-bold tracking-widest uppercase ${modeBadgeClass(hud.sensingMode)}`}
          >
            {hud.sensingMode}
          </span>

          <span className="text-[9px] text-blue-400/50 tracking-wider">WiFi DensePose</span>
        </div>
      </div>

      {/* 코너 장식 — top-left, top-right, bottom-left, bottom-right */}
      <span className="pointer-events-none absolute top-8 left-1 w-4 h-4 border-t border-l border-blue-400/20" />
      <span className="pointer-events-none absolute top-8 right-1 w-4 h-4 border-t border-r border-blue-400/20" />
      <span className="pointer-events-none absolute bottom-1 left-1 w-4 h-4 border-b border-l border-blue-400/20" />
      <span className="pointer-events-none absolute bottom-1 right-1 w-4 h-4 border-b border-r border-blue-400/20" />
    </div>
  );
}

// ---- 인라인 헬퍼 행 컴포넌트 ---------------------------------------------------

function HudRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-[9px] uppercase tracking-widest text-blue-400/60 min-w-[56px]">
        {label}
      </span>
      <span className="text-cyan-200 font-bold text-[11px]">{value}</span>
    </div>
  );
}
