import { useEventStore } from '@/stores/eventStore';
import { AlertTriangle, UserCheck, Move, Footprints, ShieldAlert, WifiOff, SignalLow, DoorOpen } from 'lucide-react';
import { Card, Badge, Button, EmptyState } from '@/components/ui';

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

const severityVariant: Record<string, 'info' | 'warning' | 'danger'> = {
  info: 'info',
  warning: 'warning',
  critical: 'danger',
};

export default function EventsPage() {
  const events = useEventStore((s) => s.events);
  const clearEvents = useEventStore((s) => s.clearEvents);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-100">이벤트 기록</h1>
          <p className="text-sm text-gray-500 mt-0.5">{events.length}개 이벤트</p>
        </div>
        <Button variant="danger" size="sm" onClick={clearEvents}>
          초기화
        </Button>
      </div>
      <Card>
        {events.length === 0 ? (
          <EmptyState icon={AlertTriangle} title="기록된 이벤트가 없습니다" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-left text-gray-500">
                  <th className="pb-3 pl-2 font-medium">유형</th>
                  <th className="pb-3 font-medium">심각도</th>
                  <th className="pb-3 font-medium">디바이스</th>
                  <th className="pb-3 font-medium">존</th>
                  <th className="pb-3 font-medium">신뢰도</th>
                  <th className="pb-3 pr-2 font-medium">시간</th>
                </tr>
              </thead>
              <tbody>
                {events.map((event) => {
                  const Icon = iconMap[event.type] || AlertTriangle;
                  return (
                    <tr key={event.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                      <td className="py-2.5 pl-2">
                        <div className="flex items-center gap-2">
                          <Icon className="h-4 w-4 shrink-0 text-gray-400" />
                          <span className="text-gray-300">{event.type.replace(/_/g, ' ')}</span>
                        </div>
                      </td>
                      <td>
                        <Badge variant={severityVariant[event.severity] || 'default'}>
                          {event.severity === 'critical' ? '긴급' : event.severity === 'warning' ? '경고' : '정보'}
                        </Badge>
                      </td>
                      <td className="text-gray-400">{event.deviceId}</td>
                      <td className="text-gray-400">{event.zone}</td>
                      <td className="text-gray-400">{(event.confidence * 100).toFixed(0)}%</td>
                      <td className="pr-2 text-xs text-gray-500">
                        {new Date(event.timestamp).toLocaleTimeString()}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
