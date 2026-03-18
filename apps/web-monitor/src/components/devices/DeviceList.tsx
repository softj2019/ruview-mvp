import { useDeviceStore } from '@/stores/deviceStore';
import { Wifi, WifiOff, Signal } from 'lucide-react';
import { Card, CardHeader, StatusDot } from '@/components/ui';

export default function DeviceList() {
  const devices = useDeviceStore((s) => s.devices);

  return (
    <Card className="h-[280px] overflow-y-auto">
      <CardHeader>디바이스</CardHeader>
      <div className="space-y-2">
        {devices.length === 0 ? (
          <p className="py-8 text-center text-sm text-gray-600">등록된 디바이스 없음</p>
        ) : (
          devices.map((device) => (
            <div key={device.id} className="flex items-center gap-3 rounded-lg px-2 py-1.5 text-sm hover:bg-gray-800/50">
              <StatusDot status={device.status === 'online' ? 'online' : 'offline'} />
              {device.status === 'online' ? (
                <Wifi className="h-4 w-4 text-emerald-400 shrink-0" />
              ) : (
                <WifiOff className="h-4 w-4 text-gray-600 shrink-0" />
              )}
              <span className="text-gray-300">{device.name}</span>
              <div className="ml-auto flex items-center gap-1 text-xs text-gray-500">
                <Signal className="h-3 w-3" />
                {device.signalStrength ?? '--'} dBm
              </div>
            </div>
          ))
        )}
      </div>
    </Card>
  );
}
