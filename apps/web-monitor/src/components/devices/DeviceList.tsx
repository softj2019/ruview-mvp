import { useDeviceStore } from '@/stores/deviceStore';
import { Wifi, WifiOff, Signal } from 'lucide-react';

export default function DeviceList() {
  const devices = useDeviceStore((s) => s.devices);

  return (
    <div className="card h-[250px] overflow-y-auto">
      <h3 className="text-sm font-medium text-gray-400 mb-3">Devices</h3>
      <div className="space-y-2">
        {devices.length === 0 ? (
          <p className="text-gray-500 text-sm">No devices registered</p>
        ) : (
          devices.map((device) => (
            <div key={device.id} className="flex items-center gap-3 text-sm">
              {device.status === 'online' ? (
                <Wifi className="w-4 h-4 text-neon-green shrink-0" />
              ) : (
                <WifiOff className="w-4 h-4 text-gray-500 shrink-0" />
              )}
              <span>{device.name}</span>
              <div className="ml-auto flex items-center gap-1 text-xs text-gray-500">
                <Signal className="w-3 h-3" />
                {device.signalStrength ?? '--'} dBm
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
