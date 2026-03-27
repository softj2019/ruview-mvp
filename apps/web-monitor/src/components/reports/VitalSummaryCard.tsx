import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { cn } from '@/lib/utils';

interface VitalSummaryCardProps {
  zone: string;
  avgBreathing: number;
  avgHeartRate: number;
  fallCount: number;
  presenceHours: number;
  trend: 'up' | 'down' | 'stable';
  sparkline: number[];
}

function getBreathingColor(bpm: number): string {
  if (bpm < 12 || bpm > 20) return 'text-red-400';
  if (bpm < 14 || bpm > 18) return 'text-amber-400';
  return 'text-emerald-400';
}

function getHeartRateColor(bpm: number): string {
  if (bpm < 50 || bpm > 100) return 'text-red-400';
  if (bpm < 55 || bpm > 90) return 'text-amber-400';
  return 'text-emerald-400';
}

function getFallBadge(count: number): string {
  if (count === 0) return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
  if (count === 1) return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
  return 'bg-red-500/10 text-red-400 border-red-500/20';
}

function Sparkline({ data }: { data: number[] }) {
  if (data.length === 0) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const w = 120;
  const h = 32;
  const padY = 2;

  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - padY - ((v - min) / range) * (h - padY * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  const pathD = `M ${points.join(' L ')}`;

  // Area fill
  const areaD = `M 0,${h} L ${pathD.slice(2)} L ${w},${h} Z`;

  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="overflow-visible">
      <defs>
        <linearGradient id="sparkGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#22d3ee" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#22d3ee" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={areaD} fill="url(#sparkGrad)" />
      <path d={pathD} fill="none" stroke="#22d3ee" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

export default function VitalSummaryCard({
  zone,
  avgBreathing,
  avgHeartRate,
  fallCount,
  presenceHours,
  trend,
  sparkline,
}: VitalSummaryCardProps) {
  const TrendIcon = trend === 'up' ? TrendingUp : trend === 'down' ? TrendingDown : Minus;
  const trendColor = trend === 'up' ? 'text-emerald-400' : trend === 'down' ? 'text-red-400' : 'text-gray-400';

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-100">{zone}</h3>
        <div className="flex items-center gap-1.5">
          <TrendIcon className={cn('h-3.5 w-3.5', trendColor)} />
          <span className={cn('text-[10px] font-medium', trendColor)}>
            {trend === 'up' ? '상승' : trend === 'down' ? '하락' : '안정'}
          </span>
        </div>
      </div>

      {/* Vital stats */}
      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-lg bg-gray-800/50 p-2.5">
          <p className="text-[10px] text-gray-500 mb-0.5">호흡수</p>
          <p className={cn('text-lg font-bold font-mono', getBreathingColor(avgBreathing))}>
            {avgBreathing}
          </p>
          <p className="text-[9px] text-gray-600">BPM</p>
        </div>
        <div className="rounded-lg bg-gray-800/50 p-2.5">
          <p className="text-[10px] text-gray-500 mb-0.5">심박수</p>
          <p className={cn('text-lg font-bold font-mono', getHeartRateColor(avgHeartRate))}>
            {avgHeartRate}
          </p>
          <p className="text-[9px] text-gray-600">BPM</p>
        </div>
      </div>

      {/* Sparkline */}
      <div>
        <p className="text-[10px] text-gray-600 mb-1">24시간 호흡수 추이</p>
        <Sparkline data={sparkline} />
      </div>

      {/* Bottom stats */}
      <div className="flex items-center justify-between pt-1 border-t border-gray-800">
        <div>
          <p className="text-[10px] text-gray-500">재실 시간</p>
          <p className="text-sm font-semibold text-gray-200">{presenceHours}h</p>
        </div>
        <div className="text-right">
          <p className="text-[10px] text-gray-500">낙상 이벤트</p>
          <span className={cn('text-xs font-bold px-2 py-0.5 rounded-full border', getFallBadge(fallCount))}>
            {fallCount}건
          </span>
        </div>
      </div>
    </div>
  );
}
