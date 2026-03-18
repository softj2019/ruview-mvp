import { useEventStore } from '@/stores/eventStore';
import { AlertTriangle, UserCheck, Move, Footprints } from 'lucide-react';

const eventIcons: Record<string, typeof AlertTriangle> = {
  fall_suspected: AlertTriangle,
  fall_confirmed: AlertTriangle,
  presence_detected: UserCheck,
  motion_active: Move,
  stationary_detected: Footprints,
};

const eventColors: Record<string, string> = {
  fall_suspected: 'text-neon-orange',
  fall_confirmed: 'text-neon-red',
  presence_detected: 'text-neon-green',
  motion_active: 'text-neon-cyan',
  stationary_detected: 'text-neon-purple',
};

export default function AlertPanel() {
  const events = useEventStore((s) => s.events.slice(0, 10));

  return (
    <div className="card h-[250px] overflow-y-auto">
      <h3 className="text-sm font-medium text-gray-400 mb-3">Recent Events</h3>
      <div className="space-y-2">
        {events.length === 0 ? (
          <p className="text-gray-500 text-sm">No events yet</p>
        ) : (
          events.map((event) => {
            const Icon = eventIcons[event.type] || AlertTriangle;
            const color = eventColors[event.type] || 'text-gray-400';
            return (
              <div key={event.id} className="flex items-center gap-3 text-sm">
                <Icon className={`w-4 h-4 ${color} shrink-0`} />
                <span className="truncate">{event.type.replace(/_/g, ' ')}</span>
                <span className="ml-auto text-xs text-gray-500">{event.zone}</span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
