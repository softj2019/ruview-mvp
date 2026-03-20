import { useMemo } from 'react';
import { Wifi, MapPin, Users, AlertTriangle } from 'lucide-react';
import { useDeviceStore } from '@/stores/deviceStore';
import { useZoneStore } from '@/stores/zoneStore';
import { useEventStore } from '@/stores/eventStore';
import { Card } from '@/components/ui';
import { cn } from '@/lib/utils';

const kpis = [
  { label: '온라인 디바이스', icon: Wifi, color: 'text-emerald-400', bg: 'bg-emerald-500/10', key: 'onlineCount' as const },
  { label: '활성 존', icon: MapPin, color: 'text-cyan-400', bg: 'bg-cyan-500/10', key: 'activeZones' as const },
  { label: '재실 인원', icon: Users, color: 'text-violet-400', bg: 'bg-violet-500/10', key: 'presenceCount' as const },
  { label: '긴급 알림', icon: AlertTriangle, color: 'text-red-400', bg: 'bg-red-500/10', key: 'criticalCount' as const },
];

export default function KpiCards() {
  const devices = useDeviceStore((s) => s.devices);
  const zones = useZoneStore((s) => s.zones);
  const events = useEventStore((s) => s.events);

  const values = useMemo(() => ({
    onlineCount: devices.filter((d) => d.status === 'online').length,
    activeZones: zones.filter((z) => z.status === 'active').length,
    presenceCount: zones[0]?.presenceCount ?? 0,
    criticalCount: events.filter((e) => e.severity === 'critical').length,
  }), [devices, zones, events]);

  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      {kpis.map(({ label, icon: Icon, color, bg, key }) => (
        <Card key={key} variant="glow">
          <div className="flex items-center gap-4">
            <div className={cn('flex h-10 w-10 items-center justify-center rounded-lg', bg)}>
              <Icon className={cn('h-5 w-5', color)} />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-100">{values[key]}</p>
              <p className="text-xs text-gray-500">{label}</p>
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}
