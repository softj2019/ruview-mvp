import { useState, useRef, useEffect } from 'react';
import { BarChart2, RefreshCw, ExternalLink, Maximize2, Minimize2 } from 'lucide-react';
import SignalChart from '@/components/charts/SignalChart';
// import { Button } from '@/components/ui'; // unused
import { useSignalStore } from '@/stores/signalStore';
import { useDeviceStore } from '@/stores/deviceStore';

const VIZ_URL = '/observatory/index.html';

/* ── 미니 스파크라인 (인라인, 의존 없음) ── */
function Sparkline({
  values,
  color = '#22d3ee',
  height = 40,
}: {
  values: number[];
  color?: string;
  height?: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || values.length < 2) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    const min = Math.min(...values);
    const max = Math.max(...values) || min + 1;
    const scale = (v: number) => h - ((v - min) / (max - min)) * h;
    ctx.beginPath();
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    values.forEach((v, i) => {
      const x = (i / (values.length - 1)) * w;
      const y = scale(v);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.stroke();
  }, [values, color]);
  return <canvas ref={canvasRef} width={200} height={height} className="w-full" />;
}

/* ── KPI 카드 ── */
function VizKpiCard({
  label,
  value,
  unit,
  color,
  sparkValues,
}: {
  label: string;
  value: string | number;
  unit?: string;
  color: string;
  sparkValues: number[];
}) {
  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900 p-3">
      <p className="text-[10px] font-medium uppercase tracking-wider text-gray-500">{label}</p>
      <p className={`mt-1 text-2xl font-bold tabular-nums ${color}`}>
        {value}
        {unit && <span className="ml-1 text-xs font-normal text-gray-500">{unit}</span>}
      </p>
      <div className="mt-2">
        <Sparkline values={sparkValues} color={color.replace('text-', '#').replace('cyan-400', '22d3ee').replace('rose-400', 'fb7185').replace('emerald-400', '34d399').replace('amber-400', 'fbbf24')} />
      </div>
    </div>
  );
}

/* ── 3D 뷰어 패널 ── */
function ThreeDPanel({ fullscreen, onToggle }: { fullscreen: boolean; onToggle: () => void }) {
  const [loaded, setLoaded] = useState(false);
  const [key, setKey] = useState(0);

  return (
    <div
      className={`relative flex flex-col overflow-hidden rounded-xl border border-gray-800 bg-gray-950 ${
        fullscreen ? 'fixed inset-0 z-50' : 'h-[420px]'
      }`}
    >
      {/* 툴바 */}
      <div className="absolute right-3 top-3 z-10 flex gap-1.5">
        <button
          onClick={() => { setLoaded(false); setKey((k) => k + 1); }}
          className="rounded bg-gray-900/80 p-1.5 text-gray-400 hover:text-cyan-400"
          title="새로고침"
        >
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={() => window.open(VIZ_URL, '_blank')}
          className="rounded bg-gray-900/80 p-1.5 text-gray-400 hover:text-cyan-400"
          title="새 탭"
        >
          <ExternalLink className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={onToggle}
          className="rounded bg-gray-900/80 p-1.5 text-gray-400 hover:text-cyan-400"
          title={fullscreen ? '창 모드 (ESC)' : '전체화면'}
        >
          {fullscreen ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
        </button>
      </div>
      {!loaded && (
        <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-gray-950 text-sm text-gray-500">
          <BarChart2 className="mb-2 h-6 w-6 animate-pulse text-cyan-500" />
          <span>3D 시각화 로딩 중...</span>
        </div>
      )}
      <iframe
        key={key}
        src={VIZ_URL}
        className="h-full w-full flex-1 border-0"
        title="3D 신호 시각화"
        onLoad={() => setLoaded(true)}
      />
    </div>
  );
}

export default function VizPage() {
  const history = useSignalStore((s) => s.history);
  const devices = useDeviceStore((s) => s.devices);
  const [fullscreen3D, setFullscreen3D] = useState(false);

  // ESC로 전체화면 해제
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setFullscreen3D(false);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  // 신호 데이터 파생
  const recent = history.slice(-60);
  const rssiValues = recent.map((d) => d.rssi ?? 0);
  const snrValues = recent.map((d) => d.snr ?? 0);
  const brValues = recent.map((d) => d.breathing_rate ?? 0);
  const hrValues = recent.map((d) => d.heart_rate ?? 0);

  const latestHr = [...hrValues].reverse().find((v: number) => v > 0) ?? 0;
  const latestBr = [...brValues].reverse().find((v: number) => v > 0) ?? 0;
  const latestRssi = rssiValues.length > 0 ? rssiValues[rssiValues.length - 1] : 0;
  const onlineCount = devices.filter((d) => d.status === 'online').length;

  if (fullscreen3D) {
    return (
      <ThreeDPanel
        fullscreen
        onToggle={() => setFullscreen3D(false)}
      />
    );
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* 헤더 */}
      <div className="flex items-center gap-3">
        <BarChart2 className="h-5 w-5 text-cyan-400" />
        <div>
          <h1 className="text-lg font-semibold text-gray-100">3D 시각화</h1>
          <p className="text-xs text-gray-500">
            신호 품질 · 생체신호 · 3D 공간 시각화
          </p>
        </div>
      </div>

      {/* KPI 행 */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <VizKpiCard
          label="RSSI"
          value={latestRssi}
          unit="dBm"
          color="text-cyan-400"
          sparkValues={rssiValues.length ? rssiValues : [0]}
        />
        <VizKpiCard
          label="심박수"
          value={latestHr || '--'}
          unit="BPM"
          color="text-rose-400"
          sparkValues={hrValues.length ? hrValues : [0]}
        />
        <VizKpiCard
          label="호흡수"
          value={latestBr || '--'}
          unit="RPM"
          color="text-emerald-400"
          sparkValues={brValues.length ? brValues : [0]}
        />
        <VizKpiCard
          label="노드 온라인"
          value={onlineCount}
          unit={`/ ${devices.length}`}
          color="text-amber-400"
          sparkValues={snrValues.length ? snrValues : [0]}
        />
      </div>

      {/* 메인 레이아웃: 3D 뷰어 + 신호 차트 */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        {/* 3D 패널 — 2/3 너비 */}
        <div className="xl:col-span-2">
          <ThreeDPanel
            fullscreen={false}
            onToggle={() => setFullscreen3D(true)}
          />
        </div>

        {/* 신호 차트 — 1/3 너비 */}
        <div className="flex flex-col gap-4">
          <SignalChart />

          {/* 디바이스 상태 테이블 */}
          <div className="rounded-xl border border-gray-800 bg-gray-900 p-4">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-500">
              ESP32 노드
            </p>
            <div className="space-y-1.5">
              {devices.length === 0 && (
                <p className="text-xs text-gray-600">연결된 노드 없음</p>
              )}
              {devices.map((d) => (
                <div key={d.id} className="flex items-center justify-between text-xs">
                  <span className="text-gray-400">{d.name ?? d.id}</span>
                  <span
                    className={
                      d.status === 'online'
                        ? 'text-emerald-400'
                        : 'text-red-500'
                    }
                  >
                    {d.status === 'online' ? '온라인' : '오프라인'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* 인터랙션 힌트 */}
      <div className="flex flex-wrap items-center gap-3 text-[10px] text-gray-600">
        <span className="font-medium text-gray-500">3D 컨트롤:</span>
        {['[드래그] 회전', '[휠] 줌', '[R] 카메라 초기화', '[D] 데모 모드 토글'].map((h) => (
          <span key={h} className="rounded border border-gray-800 bg-gray-900 px-1.5 py-0.5">
            {h}
          </span>
        ))}
      </div>
    </div>
  );
}
