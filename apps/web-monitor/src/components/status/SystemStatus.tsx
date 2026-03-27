import { useEffect, useState } from 'react';
import { Card, CardHeader, CardContent } from '@/components/ui/Card';
import { StatusDot } from '@/components/ui/StatusDot';

interface HealthStatus {
  signalAdapter: boolean;
  camera: boolean;
  cloudflareBridge: boolean;
  dataSource: 'ESP32 Hardware' | 'Demo Mode';
  uptime: number; // seconds
  activeModality: string;
}

const POLL_INTERVAL = 10_000;

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}h ${m}m`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

async function fetchHealth(): Promise<HealthStatus> {
  const defaults: HealthStatus = {
    signalAdapter: false,
    camera: false,
    cloudflareBridge: false,
    dataSource: 'Demo Mode',
    uptime: 0,
    activeModality: 'unknown',
  };

  try {
    const [apiRes, camRes] = await Promise.allSettled([
      fetch('/health', { signal: AbortSignal.timeout(5000) }),
      fetch('/cam/health', { signal: AbortSignal.timeout(5000) }),
    ]);

    let apiOk = false;
    let apiData: Record<string, unknown> = {};
    if (apiRes.status === 'fulfilled' && apiRes.value.ok) {
      apiOk = true;
      try {
        apiData = await apiRes.value.json();
      } catch {
        /* ignore parse error */
      }
    }

    let camOk = false;
    if (camRes.status === 'fulfilled' && camRes.value.ok) {
      camOk = true;
    }

    const isHardware =
      apiData.source === 'esp32' ||
      apiData.mode === 'hardware' ||
      apiData.hardware === true;

    return {
      signalAdapter: apiOk,
      camera: camOk,
      cloudflareBridge: apiOk, // bridge is healthy if API responds
      dataSource: isHardware ? 'ESP32 Hardware' : 'Demo Mode',
      uptime: typeof apiData.uptime === 'number' ? apiData.uptime : defaults.uptime,
      activeModality: typeof apiData.active_modality === 'string' ? apiData.active_modality : 'unknown',
    };
  } catch {
    return defaults;
  }
}

interface StatusRowProps {
  label: string;
  online: boolean;
}

function StatusRow({ label, online }: StatusRowProps) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-xs text-gray-400">{label}</span>
      <div className="flex items-center gap-1.5">
        <StatusDot status={online ? 'online' : 'offline'} pulse={online} />
        <span className={`text-xs ${online ? 'text-emerald-400' : 'text-gray-500'}`}>
          {online ? 'Connected' : 'Offline'}
        </span>
      </div>
    </div>
  );
}

export default function SystemStatus() {
  const [health, setHealth] = useState<HealthStatus>({
    signalAdapter: false,
    camera: false,
    cloudflareBridge: false,
    dataSource: 'Demo Mode',
    uptime: 0,
    activeModality: 'unknown',
  });

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      const result = await fetchHealth();
      if (!cancelled) setHealth(result);
    };

    poll();
    const id = setInterval(poll, POLL_INTERVAL);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return (
    <Card>
      <CardHeader>시스템 상태</CardHeader>
      <CardContent>
        <div className="space-y-0.5">
          <StatusRow label="Signal Adapter" online={health.signalAdapter} />
          <StatusRow label="Camera" online={health.camera} />
          <StatusRow label="Cloudflare Bridge" online={health.cloudflareBridge} />
        </div>

        <div className="mt-3 flex items-center justify-between border-t border-gray-800 pt-3">
          <span className="text-xs text-gray-500">데이터 소스</span>
          <span
            className={`text-xs font-medium ${
              health.dataSource === 'ESP32 Hardware' ? 'text-cyan-400' : 'text-amber-400'
            }`}
          >
            {health.dataSource}
          </span>
        </div>

        <div className="mt-1.5 flex items-center justify-between">
          <span className="text-xs text-gray-500">모달리티</span>
          <span className={`text-xs font-medium ${
            health.activeModality === 'camera+csi' ? 'text-emerald-400'
            : health.activeModality === 'camera+csi_degraded' ? 'text-amber-400'
            : 'text-cyan-400'
          }`}>
            {health.activeModality === 'camera+csi' ? 'Camera+CSI'
             : health.activeModality === 'camera+csi_degraded' ? 'Camera+CSI (저조도)'
             : 'CSI Only'}
          </span>
        </div>

        {health.uptime > 0 && (
          <div className="mt-1.5 flex items-center justify-between">
            <span className="text-xs text-gray-500">Uptime</span>
            <span className="text-xs text-gray-300">{formatUptime(health.uptime)}</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
