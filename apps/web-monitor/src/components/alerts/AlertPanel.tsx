import { useMemo } from 'react';
import { useEventStore } from '@/stores/eventStore';
import { AlertTriangle, UserCheck, Move, Footprints } from 'lucide-react';
import { Card, CardHeader, Badge } from '@/components/ui';
import { cn } from '@/lib/utils';

const eventIcons: Record<string, typeof AlertTriangle> = {
  fall_suspected: AlertTriangle,
  fall_confirmed: AlertTriangle,
  presence_detected: UserCheck,
  motion_active: Move,
  stationary_detected: Footprints,
};

const eventVariant: Record<string, 'info' | 'warning' | 'danger' | 'success'> = {
  fall_suspected: 'warning',
  fall_confirmed: 'danger',
  presence_detected: 'success',
  motion_active: 'info',
  stationary_detected: 'default' as 'info',
};

const eventColors: Record<string, string> = {
  fall_suspected: 'text-amber-400',
  fall_confirmed: 'text-red-400',
  presence_detected: 'text-emerald-400',
  motion_active: 'text-cyan-400',
  stationary_detected: 'text-violet-400',
};

export default function AlertPanel() {
  const events = useEventStore((s) => s.events);
  const recentEvents = useMemo(() => events.slice(0, 10), [events]);

  return (
    <Card className="h-[280px] overflow-y-auto">
      <CardHeader>최근 이벤트</CardHeader>
      <div className="space-y-2">
        {recentEvents.length === 0 ? (
          <p className="py-8 text-center text-sm text-gray-600">이벤트 없음</p>
        ) : (
          recentEvents.map((event) => {
            const Icon = eventIcons[event.type] || AlertTriangle;
            const color = eventColors[event.type] || 'text-gray-400';
            return (
              <div key={event.id} className="flex items-center gap-3 rounded-lg px-2 py-1.5 text-sm hover:bg-gray-800/50">
                <Icon className={cn('h-4 w-4 shrink-0', color)} />
                <span className="truncate text-gray-300">{event.type.replace(/_/g, ' ')}</span>
                <Badge variant={eventVariant[event.type] || 'default'} className="ml-auto shrink-0">
                  {event.zone}
                </Badge>
              </div>
            );
          })
        )}
      </div>
    </Card>
  );
}
