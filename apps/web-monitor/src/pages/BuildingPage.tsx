import { useMemo } from 'react';
import MultiFloorView from '@/components/floor/MultiFloorView';
import AlertPanel from '@/components/alerts/AlertPanel';
import { Card, CardHeader, CardContent } from '@/components/ui/Card';
import { useZoneStore } from '@/stores/zoneStore';
import { useDeviceStore } from '@/stores/deviceStore';
import { useEventStore } from '@/stores/eventStore';
import { cn } from '@/lib/utils';

/**
 * BuildingPage — Phase 8-2
 *
 * 멀티층 건물 뷰 + 전체 건물 통계 대시보드.
 * 라우트: /building
 */

// ── 집계 카드 ────────────────────────────────────────────────────────────────

interface StatCardProps {
  label: string;
  value: string | number;
  sub?: string;
  accent?: 'cyan' | 'emerald' | 'orange' | 'red' | 'violet';
}

const ACCENT_CLASSES: Record<NonNullable<StatCardProps['accent']>, string> = {
  cyan:    'text-cyan-400',
  emerald: 'text-emerald-400',
  orange:  'text-orange-400',
  red:     'text-red-400',
  violet:  'text-violet-400',
};

function StatCard({ label, value, sub, accent = 'cyan' }: StatCardProps) {
  return (
    <Card className="flex flex-col gap-1 p-4">
      <p className="text-xs text-gray-500 uppercase tracking-wider">{label}</p>
      <p className={cn('text-3xl font-bold tabular-nums', ACCENT_CLASSES[accent])}>
        {value}
      </p>
      {sub && <p className="text-xs text-gray-600">{sub}</p>}
    </Card>
  );
}

// ── 존 상태 테이블 ────────────────────────────────────────────────────────────

function ZoneTable() {
  const zones = useZoneStore((s) => s.zones);

  if (zones.length === 0) {
    return (
      <p className="py-6 text-center text-sm text-gray-600">존 데이터 없음</p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-800 text-left text-xs text-gray-500 uppercase tracking-wider">
            <th className="pb-2 pr-4">구역</th>
            <th className="pb-2 pr-4">층</th>
            <th className="pb-2 pr-4">상태</th>
            <th className="pb-2 pr-4 text-right">재실</th>
            <th className="pb-2 text-right">최근 활동</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-800/50">
          {zones.map((zone) => (
            <tr key={zone.id} className="hover:bg-gray-800/30 transition-colors">
              <td className="py-2 pr-4 text-gray-200 font-medium">{zone.name}</td>
              <td className="py-2 pr-4 text-gray-400">{zone.floor ?? '1F'}</td>
              <td className="py-2 pr-4">
                <span
                  className={cn(
                    'inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold',
                    zone.status === 'active'  && 'bg-emerald-900/60 text-emerald-400',
                    zone.status === 'alert'   && 'bg-red-900/60 text-red-400',
                    zone.status === 'inactive'&& 'bg-gray-800 text-gray-500',
                  )}
                >
                  {zone.status}
                </span>
              </td>
              <td className="py-2 pr-4 text-right">
                <span
                  className={cn(
                    'font-bold',
                    zone.presenceCount > 0 ? 'text-emerald-400' : 'text-gray-600',
                  )}
                >
                  {zone.presenceCount}명
                </span>
              </td>
              <td className="py-2 text-right text-gray-600 text-xs">
                {zone.lastActivity
                  ? new Date(zone.lastActivity).toLocaleTimeString('ko-KR', {
                      hour: '2-digit',
                      minute: '2-digit',
                    })
                  : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── 페이지 ────────────────────────────────────────────────────────────────────

export default function BuildingPage() {
  const zones   = useZoneStore((s) => s.zones);
  const devices = useDeviceStore((s) => s.devices);
  const events  = useEventStore((s) => s.events);

  // 전체 건물 통계
  const stats = useMemo(() => {
    const totalPresence = zones.reduce((s, z) => s + (z.presenceCount ?? 0), 0);
    const onlineDevices = devices.filter((d) => d.status === 'online').length;
    const alertZones    = zones.filter((z) => z.status === 'alert').length;
    const fallEvents    = events.filter(
      (e) => e.type === 'fall_confirmed' || e.type === 'fall_suspected',
    ).length;
    return { totalPresence, onlineDevices, alertZones, fallEvents };
  }, [zones, devices, events]);

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* 페이지 헤더 */}
      <div>
        <h1 className="text-xl font-semibold text-gray-100">건물 관제</h1>
        <p className="mt-0.5 text-sm text-gray-500">
          멀티층 재실 현황 및 낙상 감지 통합 뷰
        </p>
      </div>

      {/* 전체 통계 카드 */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard
          label="전체 재실"
          value={stats.totalPresence}
          sub="명 (전층 합산)"
          accent="emerald"
        />
        <StatCard
          label="온라인 노드"
          value={stats.onlineDevices}
          sub={`/ ${devices.length}대`}
          accent="cyan"
        />
        <StatCard
          label="경보 구역"
          value={stats.alertZones}
          sub="active alert zones"
          accent={stats.alertZones > 0 ? 'red' : 'cyan'}
        />
        <StatCard
          label="낙상 이벤트"
          value={stats.fallEvents}
          sub="오늘 감지 건수"
          accent={stats.fallEvents > 0 ? 'orange' : 'cyan'}
        />
      </div>

      {/* 멀티플로어 뷰 */}
      <Card variant="glow">
        <CardHeader>층별 평면도</CardHeader>
        <CardContent>
          <MultiFloorView defaultFloor="1F" />
        </CardContent>
      </Card>

      {/* 하단: 존 테이블 + 이벤트 패널 */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>구역 현황</CardHeader>
          <ZoneTable />
        </Card>

        <AlertPanel />
      </div>
    </div>
  );
}
