import { useMemo } from 'react';
import { Wifi, MapPin, Users, AlertTriangle, Wind, HeartPulse } from 'lucide-react';
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
  { label: '호흡수 (BPM)', icon: Wind, color: 'text-sky-400', bg: 'bg-sky-500/10', key: 'breathingBpm' as const },
  { label: '심박수 (BPM)', icon: HeartPulse, color: 'text-rose-400', bg: 'bg-rose-500/10', key: 'heartRate' as const },
];

export default function KpiCards() {
  const devices = useDeviceStore((s) => s.devices);
  const zones = useZoneStore((s) => s.zones);
  const events = useEventStore((s) => s.events);

  const values = useMemo(() => {
    const onlineDevices = devices.filter((d) => d.status === 'online');

    // Aggregate breathing and heart rate from online devices
    const breathingValues = onlineDevices
      .map((d) => d.breathing_bpm ?? d.csi_breathing_bpm ?? 0)
      .filter((v) => v > 0);
    const heartValues = onlineDevices
      .map((d) => d.heart_rate ?? d.csi_heart_rate ?? 0)
      .filter((v) => v > 0);

    const avgBreathing = breathingValues.length > 0
      ? Math.round(breathingValues.reduce((a, b) => a + b, 0) / breathingValues.length * 10) / 10
      : 0;
    const avgHeart = heartValues.length > 0
      ? Math.round(heartValues.reduce((a, b) => a + b, 0) / heartValues.length * 10) / 10
      : 0;

    return {
      onlineCount: onlineDevices.length,
      activeZones: zones.filter((z) => z.status === 'active').length,
      presenceCount: zones.reduce((sum, z) => sum + (z.presenceCount ?? 0), 0),
      criticalCount: events.filter((e) => e.severity === 'critical').length,
      breathingBpm: avgBreathing,
      heartRate: avgHeart,
    };
  }, [devices, zones, events]);

  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-6">
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
