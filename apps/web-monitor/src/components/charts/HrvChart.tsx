import { cn } from '@/lib/utils';

interface HrvChartProps {
  deviceId: string;
  sdnn: number;     // ms
  rmssd: number;    // ms
  pnn50: number;    // %
  arrhythmia: boolean;
  className?: string;
}

interface MeterProps {
  label: string;
  value: number;
  max: number;
  unit: string;
  color: string;
  subLabel?: string;
}

function Meter({ label, value, max, unit, color, subLabel }: MeterProps) {
  const pct = Math.min((value / max) * 100, 100);
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between items-baseline">
        <span className="text-xs text-gray-400">{label}</span>
        <span className={`text-sm font-bold font-mono ${color}`}>
          {value.toFixed(1)}
          <span className="text-xs font-normal text-gray-500 ml-0.5">{unit}</span>
        </span>
      </div>
      <div className="w-full h-2 rounded-full bg-gray-800 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${color.replace('text-', 'bg-')}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {subLabel && (
        <p className="text-[10px] text-gray-600">{subLabel}</p>
      )}
    </div>
  );
}

function sdnnColor(sdnn: number): string {
  return sdnn >= 30 ? 'text-green-400' : 'text-red-400';
}

function rmssdColor(rmssd: number): string {
  return rmssd >= 20 ? 'text-green-400' : 'text-red-400';
}

function pnn50Color(pnn50: number): string {
  return pnn50 > 50 ? 'text-yellow-400' : 'text-green-400';
}

export default function HrvChart({
  deviceId,
  sdnn,
  rmssd,
  pnn50,
  arrhythmia,
  className,
}: HrvChartProps) {
  return (
    <div className={cn('space-y-3', className)}>
      {/* 디바이스 ID + 부정맥 경고 */}
      <div className="flex items-center justify-between">
        <span className="text-xs font-mono text-gray-400">{deviceId}</span>
        {arrhythmia && (
          <span className="inline-flex items-center gap-1 rounded-full bg-red-900/40 border border-red-700/40 px-2 py-0.5 text-xs text-red-400 font-medium animate-pulse">
            ⚠ 부정맥 의심
          </span>
        )}
      </div>

      {/* SDNN 게이지 */}
      <Meter
        label="SDNN"
        value={sdnn}
        max={100}
        unit="ms"
        color={sdnnColor(sdnn)}
        subLabel={sdnn >= 30 ? '정상 (≥30ms)' : '낮음 — 자율신경 기능 저하 가능성'}
      />

      {/* RMSSD 게이지 */}
      <Meter
        label="RMSSD"
        value={rmssd}
        max={80}
        unit="ms"
        color={rmssdColor(rmssd)}
        subLabel={rmssd >= 20 ? '정상 (≥20ms)' : '낮음 — 부교감 활성 저하 가능성'}
      />

      {/* PNN50 게이지 */}
      <Meter
        label="PNN50"
        value={pnn50}
        max={100}
        unit="%"
        color={pnn50Color(pnn50)}
        subLabel={pnn50 > 50 ? '높음 (>50%) — 주의' : '정상 범위'}
      />

      {/* 요약 행 */}
      <div className="flex justify-between pt-1 border-t border-gray-800 text-[10px] text-gray-600">
        <span>SDNN: 정상 30~100ms</span>
        <span>RMSSD: 정상 20~80ms</span>
        <span>PNN50: &lt;50% 권장</span>
      </div>
    </div>
  );
}
