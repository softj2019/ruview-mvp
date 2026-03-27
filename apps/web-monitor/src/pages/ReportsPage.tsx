import { useState } from 'react';
import { FileDown, Calendar, RefreshCw } from 'lucide-react';
import { Card, CardHeader, CardContent } from '@/components/ui/Card';
import VitalSummaryCard from '@/components/reports/VitalSummaryCard';
import WeeklyChart from '@/components/reports/WeeklyChart';
import { useReportData } from '@/hooks/useReportData';
import { cn } from '@/lib/utils';

type DateRange = 'day' | 'week' | 'month';

const RANGE_OPTIONS: { value: DateRange; label: string }[] = [
  { value: 'day', label: '오늘' },
  { value: 'week', label: '최근 7일' },
  { value: 'month', label: '최근 30일' },
];

function getBreathingStatus(bpm: number): string {
  if (bpm < 12 || bpm > 20) return 'text-red-400';
  if (bpm < 14 || bpm > 18) return 'text-amber-400';
  return 'text-emerald-400';
}

function getHeartStatus(bpm: number): string {
  if (bpm < 50 || bpm > 100) return 'text-red-400';
  if (bpm < 55 || bpm > 90) return 'text-amber-400';
  return 'text-emerald-400';
}

export default function ReportsPage() {
  const [range, setRange] = useState<DateRange>('week');
  const { zones, days, generated } = useReportData(range);

  const handlePrint = () => {
    window.print();
  };

  const totalFalls = zones.reduce((sum, z) => sum + z.fallCount, 0);
  const avgBreathing = Math.round(zones.reduce((sum, z) => sum + z.avgBreathing, 0) / zones.length * 10) / 10;
  const avgHeart = Math.round(zones.reduce((sum, z) => sum + z.avgHeartRate, 0) / zones.length * 10) / 10;
  const totalPresence = Math.round(zones.reduce((sum, z) => sum + z.presenceHours, 0) * 10) / 10;

  return (
    <div className="space-y-6 print:space-y-4">
      {/* Print styles */}
      <style>{`
        @media print {
          body { background: white !important; color: black !important; }
          .no-print { display: none !important; }
          .print-break { page-break-before: always; }
        }
      `}</style>

      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-100">리포트</h1>
          <p className="text-sm text-gray-500 mt-0.5 flex items-center gap-1.5">
            <RefreshCw className="h-3 w-3" />
            생성: {generated}
          </p>
        </div>

        <div className="flex items-center gap-2 no-print flex-wrap">
          {/* Date range selector */}
          <div className="flex rounded-lg border border-gray-700 overflow-hidden">
            {RANGE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setRange(opt.value)}
                className={cn(
                  'px-3 py-1.5 text-xs font-medium transition-colors',
                  range === opt.value
                    ? 'bg-cyan-500/20 text-cyan-400'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800',
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {/* Export button */}
          <button
            onClick={handlePrint}
            className="flex items-center gap-2 rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-xs font-medium text-gray-200 hover:bg-gray-700 transition-colors"
          >
            <FileDown className="h-3.5 w-3.5" />
            PDF 다운로드
          </button>
        </div>
      </div>

      {/* Summary KPI row */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          { label: '평균 호흡수', value: `${avgBreathing} BPM`, cls: getBreathingStatus(avgBreathing) },
          { label: '평균 심박수', value: `${avgHeart} BPM`, cls: getHeartStatus(avgHeart) },
          { label: '총 낙상 이벤트', value: `${totalFalls}건`, cls: totalFalls > 0 ? 'text-red-400' : 'text-emerald-400' },
          { label: '총 재실 시간', value: `${totalPresence}h`, cls: 'text-cyan-400' },
        ].map((kpi) => (
          <div key={kpi.label} className="rounded-xl border border-gray-800 bg-gray-900 p-4 text-center">
            <p className={cn('text-2xl font-bold font-mono', kpi.cls)}>{kpi.value}</p>
            <p className="text-xs text-gray-500 mt-1">{kpi.label}</p>
          </div>
        ))}
      </div>

      {/* Zone vital cards */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Calendar className="h-4 w-4 text-gray-400" />
            <span>존별 바이탈 요약</span>
            <span className="ml-auto text-xs text-gray-500 font-normal">
              {RANGE_OPTIONS.find((o) => o.value === range)?.label} 기준
            </span>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {zones.map((z) => (
              <VitalSummaryCard key={z.zone} {...z} />
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Per-zone stats table */}
      <Card>
        <CardHeader>존별 상세 통계</CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-xs text-gray-500">
                  <th className="pb-2 text-left font-medium">존</th>
                  <th className="pb-2 text-right font-medium">평균 호흡수</th>
                  <th className="pb-2 text-right font-medium">평균 심박수</th>
                  <th className="pb-2 text-right font-medium">낙상 이벤트</th>
                  <th className="pb-2 text-right font-medium">재실 시간</th>
                  <th className="pb-2 text-right font-medium hidden sm:table-cell">추세</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/50">
                {zones.map((z) => (
                  <tr key={z.zone} className="text-gray-300">
                    <td className="py-2.5 font-medium">{z.zone}</td>
                    <td className={cn('py-2.5 text-right font-mono', getBreathingStatus(z.avgBreathing))}>
                      {z.avgBreathing} BPM
                    </td>
                    <td className={cn('py-2.5 text-right font-mono', getHeartStatus(z.avgHeartRate))}>
                      {z.avgHeartRate} BPM
                    </td>
                    <td className="py-2.5 text-right">
                      <span className={cn(
                        'inline-block px-2 py-0.5 rounded-full text-xs font-bold border',
                        z.fallCount === 0
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                          : z.fallCount === 1
                            ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                            : 'bg-red-500/10 text-red-400 border-red-500/20',
                      )}>
                        {z.fallCount}건
                      </span>
                    </td>
                    <td className="py-2.5 text-right text-gray-400">{z.presenceHours}h</td>
                    <td className="py-2.5 text-right hidden sm:table-cell">
                      <span className={cn(
                        'text-xs',
                        z.trend === 'up' ? 'text-emerald-400' : z.trend === 'down' ? 'text-red-400' : 'text-gray-500',
                      )}>
                        {z.trend === 'up' ? '↑ 상승' : z.trend === 'down' ? '↓ 하락' : '— 안정'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Weekly bar chart */}
      <Card>
        <CardHeader>
          {range === 'day' ? '오늘 현황' : range === 'week' ? '주간 낙상/재실 현황' : '월간 낙상/재실 현황'}
        </CardHeader>
        <CardContent>
          <WeeklyChart days={days} />
        </CardContent>
      </Card>
    </div>
  );
}
