import { useDeviceStore } from '@/stores/deviceStore';
import { Wifi, WifiOff, Signal, MapPin, Clock } from 'lucide-react';
import { Card, Badge, StatusDot, EmptyState } from '@/components/ui';
import { cn } from '@/lib/utils';

export default function DevicesPage() {
  const devices = useDeviceStore((s) => s.devices);
  const selectedId = useDeviceStore((s) => s.selectedId);
  const selectDevice = useDeviceStore((s) => s.selectDevice);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-100">디바이스 관리</h1>
        <p className="text-sm text-gray-500 mt-0.5">연결된 센서 노드 현황</p>
      </div>
      <div className="overflow-x-auto">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3" style={{ minWidth: 0 }}>
        {devices.map((device) => (
          <Card
            key={device.id}
            className={cn(
              'cursor-pointer transition-all hover:border-cyan-800',
              device.id === selectedId && 'border-cyan-700 shadow-lg shadow-cyan-500/10',
            )}
            onClick={() => selectDevice(device.id === selectedId ? null : device.id)}
          >
            <div className="mb-3 flex items-center gap-3">
              <StatusDot status={device.status === 'online' ? 'online' : 'offline'} />
              {device.status === 'online' ? (
                <Wifi className="h-5 w-5 text-emerald-400" />
              ) : (
                <WifiOff className="h-5 w-5 text-gray-600" />
              )}
              <h3 className="font-medium text-gray-200">{device.name}</h3>
              <Badge variant={device.status === 'online' ? 'success' : 'default'} className="ml-auto mr-1">
                {device.status === 'online' ? '온라인' : '오프라인'}
              </Badge>
            </div>
            <div className="space-y-1.5 text-sm text-gray-400">
              <div className="flex items-center gap-2">
                <Signal className="h-3.5 w-3.5 text-gray-500" />
                <span>신호: {device.signalStrength ?? '--'} dBm</span>
              </div>
              <div className="flex items-center gap-2">
                <MapPin className="h-3.5 w-3.5 text-gray-500" />
                <span>위치: ({device.x}, {device.y})</span>
              </div>
              <div className="flex items-center gap-2">
                <Clock className="h-3.5 w-3.5 text-gray-500" />
                <span>MAC: {device.mac}</span>
              </div>
              <p className="text-xs text-gray-600">펌웨어: {device.firmwareVersion}</p>
              {device.model && (
                <p className="text-xs text-gray-600 font-mono">
                  {device.model} · Flash {device.flashSize} · PSRAM {device.psramSize}
                </p>
              )}
            </div>
          </Card>
        ))}
        {devices.length === 0 && (
          <div className="col-span-full">
            <EmptyState
              icon={Wifi}
              title="연결된 디바이스가 없습니다"
              description="Mock 서버를 시작하거나 ESP32-S3를 연결하세요."
            />
          </div>
        )}
      </div>
      </div>
    </div>
  );
}
