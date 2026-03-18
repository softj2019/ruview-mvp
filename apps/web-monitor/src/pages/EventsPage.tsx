import { useEventStore } from '@/stores/eventStore';
import { AlertTriangle, UserCheck, Move, Footprints, ShieldAlert, WifiOff, SignalLow, DoorOpen } from 'lucide-react';

const iconMap: Record<string, typeof AlertTriangle> = {
  fall_suspected: AlertTriangle,
  fall_confirmed: ShieldAlert,
  presence_detected: UserCheck,
  motion_active: Move,
  stationary_detected: Footprints,
  zone_intrusion: DoorOpen,
  device_offline: WifiOff,
  signal_weak: SignalLow,
};

const severityColors: Record<string, string> = {
  info: 'text-neon-cyan bg-neon-cyan/10',
  warning: 'text-neon-orange bg-neon-orange/10',
  critical: 'text-neon-red bg-neon-red/10',
};

export default function EventsPage() {
  const events = useEventStore((s) => s.events);
  const clearEvents = useEventStore((s) => s.clearEvents);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Event History</h2>
        <div className="flex gap-2">
          <span className="text-sm text-gray-400">{events.length} events</span>
          <button
            onClick={clearEvents}
            className="text-xs px-3 py-1 rounded border border-surface-600 hover:border-neon-red/50 text-gray-400 hover:text-neon-red transition-colors"
          >
            Clear
          </button>
        </div>
      </div>
      <div className="card">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b border-surface-600">
              <th className="pb-2 pl-2">Type</th>
              <th className="pb-2">Severity</th>
              <th className="pb-2">Device</th>
              <th className="pb-2">Zone</th>
              <th className="pb-2">Confidence</th>
              <th className="pb-2 pr-2">Time</th>
            </tr>
          </thead>
          <tbody>
            {events.map((event) => {
              const Icon = iconMap[event.type] || AlertTriangle;
              const sevClass = severityColors[event.severity] || 'text-gray-400';
              return (
                <tr key={event.id} className="border-b border-surface-600/50 hover:bg-surface-700/30">
                  <td className="py-2 pl-2">
                    <div className="flex items-center gap-2">
                      <Icon className="w-4 h-4 shrink-0" />
                      <span>{event.type.replace(/_/g, ' ')}</span>
                    </div>
                  </td>
                  <td>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${sevClass}`}>
                      {event.severity}
                    </span>
                  </td>
                  <td className="text-gray-400">{event.deviceId}</td>
                  <td className="text-gray-400">{event.zone}</td>
                  <td className="text-gray-400">{(event.confidence * 100).toFixed(0)}%</td>
                  <td className="pr-2 text-gray-500 text-xs">
                    {new Date(event.timestamp).toLocaleTimeString()}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {events.length === 0 && (
          <p className="text-center text-gray-500 py-8">No events recorded yet</p>
        )}
      </div>
    </div>
  );
}
