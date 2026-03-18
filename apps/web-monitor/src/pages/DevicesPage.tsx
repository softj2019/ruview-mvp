import { useDeviceStore } from '@/stores/deviceStore';
import { Wifi, WifiOff, Signal, MapPin, Clock } from 'lucide-react';

export default function DevicesPage() {
  const devices = useDeviceStore((s) => s.devices);
  const selectedId = useDeviceStore((s) => s.selectedId);
  const selectDevice = useDeviceStore((s) => s.selectDevice);

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Device Management</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {devices.map((device) => (
          <div
            key={device.id}
            onClick={() => selectDevice(device.id === selectedId ? null : device.id)}
            className={`card cursor-pointer transition-all hover:border-neon-cyan/50 ${
              device.id === selectedId ? 'border-neon-cyan shadow-lg shadow-neon-cyan/10' : ''
            }`}
          >
            <div className="flex items-center gap-3 mb-3">
              {device.status === 'online' ? (
                <Wifi className="w-5 h-5 text-neon-green" />
              ) : (
                <WifiOff className="w-5 h-5 text-gray-500" />
              )}
              <h3 className="font-medium">{device.name}</h3>
              <span className={`ml-auto text-xs px-2 py-0.5 rounded-full ${
                device.status === 'online'
                  ? 'bg-neon-green/10 text-neon-green'
                  : 'bg-gray-500/10 text-gray-500'
              }`}>
                {device.status}
              </span>
            </div>
            <div className="space-y-1.5 text-sm text-gray-400">
              <div className="flex items-center gap-2">
                <Signal className="w-3.5 h-3.5" />
                <span>Signal: {device.signalStrength ?? '--'} dBm</span>
              </div>
              <div className="flex items-center gap-2">
                <MapPin className="w-3.5 h-3.5" />
                <span>Position: ({device.x}, {device.y})</span>
              </div>
              <div className="flex items-center gap-2">
                <Clock className="w-3.5 h-3.5" />
                <span>MAC: {device.mac}</span>
              </div>
              <div className="text-xs text-gray-500">
                FW: {device.firmwareVersion}
              </div>
            </div>
          </div>
        ))}
        {devices.length === 0 && (
          <div className="col-span-full text-center text-gray-500 py-12">
            No devices connected. Start the mock server or connect ESP32-S3.
          </div>
        )}
      </div>
    </div>
  );
}
