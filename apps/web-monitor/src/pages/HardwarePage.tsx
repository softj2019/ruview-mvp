import { Card, CardHeader, CardContent } from '@/components/ui/Card';
import { useDeviceStore } from '@/stores/deviceStore';
import { useZoneStore } from '@/stores/zoneStore';

function rssiColor(rssi: number | null): string {
  if (rssi == null) return 'bg-gray-600';
  if (rssi > -60) return 'bg-emerald-500';
  if (rssi > -75) return 'bg-yellow-500';
  if (rssi > -90) return 'bg-red-500';
  return 'bg-red-700';
}

function rssiLabel(rssi: number | null): string {
  if (rssi == null) return 'N/A';
  return `${rssi} dBm`;
}

function rssiPercent(rssi: number | null): number {
  if (rssi == null) return 0;
  // Map -100..-30 to 0..100
  return Math.max(0, Math.min(100, ((rssi + 100) / 70) * 100));
}

function formatLastSeen(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString('ko-KR', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return iso;
  }
}

export default function HardwarePage() {
  const devices = useDeviceStore((s) => s.devices);
  const zones = useZoneStore((s) => s.zones);

  const zoneMap = new Map(zones.map((z) => [z.id, z.name]));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-100">하드웨어</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          디바이스 하드웨어 상태 모니터링
        </p>
      </div>

      {devices.length === 0 ? (
        <Card>
          <CardContent>
            <p className="text-xs text-gray-500">등록된 디바이스가 없습니다.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {devices.map((device) => {
            const zoneName = device.zone_id ? zoneMap.get(device.zone_id) ?? device.zone_id : '미할당';

            return (
              <Card key={device.id}>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-block h-2.5 w-2.5 rounded-full ${
                        device.status === 'online' ? 'bg-emerald-400' : 'bg-gray-500'
                      }`}
                    />
                    <span className="text-sm font-medium text-gray-100">
                      {device.name}
                    </span>
                    <span
                      className={`ml-auto text-[10px] px-1.5 py-0.5 rounded-full ${
                        device.status === 'online'
                          ? 'bg-emerald-500/20 text-emerald-400'
                          : 'bg-gray-500/20 text-gray-400'
                      }`}
                    >
                      {device.status}
                    </span>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2.5">
                    {/* MAC */}
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-500">MAC</span>
                      <span className="text-xs font-mono text-gray-300">
                        {device.mac}
                      </span>
                    </div>

                    {/* RSSI Signal */}
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-gray-500">RSSI</span>
                        <span className="text-xs text-gray-300">
                          {rssiLabel(device.signalStrength)}
                        </span>
                      </div>
                      <div className="h-1.5 w-full rounded-full bg-gray-800">
                        <div
                          className={`h-full rounded-full transition-all duration-300 ${rssiColor(device.signalStrength)}`}
                          style={{ width: `${rssiPercent(device.signalStrength)}%` }}
                        />
                      </div>
                    </div>

                    {/* Zone */}
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-500">존</span>
                      <span className="text-xs text-gray-300">{zoneName}</span>
                    </div>

                    {/* Firmware */}
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-500">펌웨어</span>
                      <span className="text-xs font-mono text-gray-300">
                        {device.firmwareVersion}
                      </span>
                    </div>

                    {/* Position + mini-map */}
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-500">위치</span>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-300">
                          ({device.x.toFixed(1)}, {device.y.toFixed(1)})
                        </span>
                        <svg
                          width="32"
                          height="32"
                          viewBox="0 0 100 100"
                          className="rounded border border-gray-700 bg-gray-800/50"
                        >
                          <circle
                            cx={Math.max(5, Math.min(95, device.x))}
                            cy={Math.max(5, Math.min(95, device.y))}
                            r="5"
                            fill="#22d3ee"
                          />
                        </svg>
                      </div>
                    </div>

                    {/* Last Seen */}
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-500">마지막 감지</span>
                      <span className="text-xs text-gray-400">
                        {formatLastSeen(device.lastSeen)}
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
