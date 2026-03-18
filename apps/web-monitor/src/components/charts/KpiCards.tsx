import { useMemo } from 'react';
import { Wifi, MapPin, Users, AlertTriangle } from 'lucide-react';
import { useDeviceStore } from '@/stores/deviceStore';
import { useEventStore } from '@/stores/eventStore';

const kpis = [
  { label: 'Online Devices', icon: Wifi, color: 'text-neon-green', key: 'onlineCount' as const },
  { label: 'Active Zones', icon: MapPin, color: 'text-neon-cyan', key: 'activeZones' as const },
  { label: 'Presence Count', icon: Users, color: 'text-neon-purple', key: 'presenceCount' as const },
  { label: 'Critical Alerts', icon: AlertTriangle, color: 'text-neon-red', key: 'criticalCount' as const },
];

export default function KpiCards() {
  const devices = useDeviceStore((s) => s.devices);
  const events = useEventStore((s) => s.events);

  const values = useMemo(() => ({
    onlineCount: devices.filter((d) => d.status === 'online').length,
    activeZones: devices.length,
    presenceCount: events.filter((e) => e.type === 'presence_detected').length,
    criticalCount: events.filter((e) => e.severity === 'critical').length,
  }), [devices, events]);

  return (
    <div className="grid grid-cols-4 gap-4">
      {kpis.map(({ label, icon: Icon, color, key }) => (
        <div key={key} className="card-glow flex items-center gap-4">
          <Icon className={`w-8 h-8 ${color}`} />
          <div>
            <p className="text-2xl font-bold">{values[key]}</p>
            <p className="text-xs text-gray-400">{label}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
