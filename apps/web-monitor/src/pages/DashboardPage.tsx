import { useEffect, useState, useMemo } from 'react';
import KpiCards from '@/components/charts/KpiCards';
import SystemStatus from '@/components/status/SystemStatus';
import FloorView from '@/components/floor/FloorView';
import CameraFeed from '@/components/camera/CameraFeed';
import ObservatoryMini from '@/components/observatory/ObservatoryMini';
import AlertPanel from '@/components/alerts/AlertPanel';
import DeviceList from '@/components/devices/DeviceList';
import SignalChart from '@/components/charts/SignalChart';
import { Card, CardHeader, CardContent } from '@/components/ui/Card';
import { useZoneStore } from '@/stores/zoneStore';
import { useDeviceStore } from '@/stores/deviceStore';
import DashboardHud from '@/components/DashboardHud';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ComponentHealth {
  status: 'healthy' | 'degraded' | 'unhealthy' | 'unknown';
  message: string;
  cpu?: number;
  memory?: number;
}

interface SystemHealth {
  signalAdapter: ComponentHealth;
  apiGateway: ComponentHealth;
  camera: ComponentHealth;
  database: ComponentHealth;
  dataSource: 'live' | 'server-simulated' | 'reconnecting' | 'simulated';
}

// ---------------------------------------------------------------------------
// Health fetch
// ---------------------------------------------------------------------------

const POLL_MS = 15_000;

async function fetchSystemHealth(): Promise<SystemHealth> {
  const defaults: SystemHealth = {
    signalAdapter: { status: 'unknown', message: 'Checking...' },
    apiGateway: { status: 'unknown', message: 'Checking...' },
    camera: { status: 'unknown', message: 'Checking...' },
    database: { status: 'unknown', message: 'Checking...' },
    dataSource: 'reconnecting',
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
      try { apiData = await apiRes.value.json(); } catch { /* noop */ }
    }

    let camOk = false;
    if (camRes.status === 'fulfilled' && camRes.value.ok) camOk = true;

    const isHardware =
      apiData.source === 'esp32' || apiData.mode === 'hardware' || apiData.hardware === true;

    // Parse nested system metrics if present
    const sysMetrics =
      (apiData.system_metrics as Record<string, unknown> | undefined) ??
      (apiData.metrics as Record<string, unknown> | undefined) ??
      {};
    const cpuBlock = sysMetrics.cpu as Record<string, unknown> | undefined;
    const memBlock = sysMetrics.memory as Record<string, unknown> | undefined;
    const cpuPct =
      typeof cpuBlock?.percent === 'number'
        ? cpuBlock.percent
        : typeof sysMetrics.cpu_percent === 'number'
          ? (sysMetrics.cpu_percent as number)
          : undefined;
    const memPct =
      typeof memBlock?.percent === 'number'
        ? memBlock.percent
        : typeof sysMetrics.memory_percent === 'number'
          ? (sysMetrics.memory_percent as number)
          : undefined;

    const dbComponents = apiData.components as Record<string, unknown> | undefined;
    const dbStatus =
      (dbComponents?.database as Record<string, unknown> | undefined)?.status === 'healthy'
        ? 'healthy'
        : apiOk
          ? 'degraded'
          : 'unhealthy';

    return {
      signalAdapter: {
        status: apiOk ? 'healthy' : 'unhealthy',
        message: apiOk ? 'Signal processing active' : 'Unreachable',
        cpu: cpuPct,
        memory: memPct,
      },
      apiGateway: {
        status: apiOk ? 'healthy' : 'unhealthy',
        message: apiOk ? 'REST + WebSocket proxy running' : 'Offline',
      },
      camera: {
        status: camOk ? 'healthy' : 'unhealthy',
        message: camOk ? 'YOLOv8-pose active' : 'Offline',
      },
      database: {
        status: dbStatus as ComponentHealth['status'],
        message: dbStatus === 'healthy' ? 'Supabase connected' : 'Connection degraded',
      },
      dataSource: isHardware ? 'live' : apiOk ? 'server-simulated' : 'simulated',
    };
  } catch {
    return defaults;
  }
}

// ---------------------------------------------------------------------------
// Component Status Card
// ---------------------------------------------------------------------------

type HealthLevel = 'healthy' | 'degraded' | 'unhealthy' | 'unknown';

function statusColor(s: HealthLevel) {
  if (s === 'healthy') return { dot: '#22c55e', text: 'text-emerald-400', glow: '#22c55e' };
  if (s === 'degraded') return { dot: '#f59e0b', text: 'text-amber-400', glow: '#f59e0b' };
  if (s === 'unhealthy') return { dot: '#ef4444', text: 'text-red-400', glow: '#ef4444' };
  return { dot: '#6b7280', text: 'text-gray-400', glow: '#6b7280' };
}

function statusLabel(s: HealthLevel) {
  if (s === 'healthy') return 'HEALTHY';
  if (s === 'degraded') return 'DEGRADED';
  if (s === 'unhealthy') return 'OFFLINE';
  return 'UNKNOWN';
}

function ComponentStatusCard({
  title,
  health,
}: {
  title: string;
  health: ComponentHealth;
}) {
  const c = statusColor(health.status);
  return (
    <div className="rounded-lg border border-gray-800 bg-gray-950 p-3 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-gray-300">{title}</span>
        <div className="flex items-center gap-1.5">
          <span
            className="inline-block w-1.5 h-1.5 rounded-full"
            style={{ background: c.dot, boxShadow: `0 0 5px ${c.glow}` }}
          />
          <span className={`text-[10px] font-bold tracking-wider ${c.text}`}>
            {statusLabel(health.status)}
          </span>
        </div>
      </div>
      <p className="text-[11px] text-gray-500">{health.message}</p>

      {/* CPU/Memory bars (only for Signal Adapter which has process metrics) */}
      {health.cpu != null && (
        <div className="space-y-1 pt-1">
          <div className="flex justify-between text-[10px]">
            <span className="text-gray-600">CPU</span>
            <span className="font-mono text-gray-400">{health.cpu.toFixed(1)}%</span>
          </div>
          <div className="h-1 rounded-full bg-gray-800 overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${Math.min(100, health.cpu)}%`,
                background: health.cpu >= 90 ? '#ef4444' : health.cpu >= 75 ? '#f59e0b' : '#22c55e',
              }}
            />
          </div>
        </div>
      )}
      {health.memory != null && (
        <div className="space-y-1">
          <div className="flex justify-between text-[10px]">
            <span className="text-gray-600">Memory</span>
            <span className="font-mono text-gray-400">{health.memory.toFixed(1)}%</span>
          </div>
          <div className="h-1 rounded-full bg-gray-800 overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${Math.min(100, health.memory)}%`,
                background: health.memory >= 90 ? '#ef4444' : health.memory >= 75 ? '#f59e0b' : '#3b82f6',
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// System Components Health Panel
// ---------------------------------------------------------------------------

function SystemComponentsPanel() {
  const [health, setHealth] = useState<SystemHealth>({
    signalAdapter: { status: 'unknown', message: 'Checking...' },
    apiGateway: { status: 'unknown', message: 'Checking...' },
    camera: { status: 'unknown', message: 'Checking...' },
    database: { status: 'unknown', message: 'Checking...' },
    dataSource: 'reconnecting',
  });

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      const result = await fetchSystemHealth();
      if (!cancelled) setHealth(result);
    };
    poll();
    const id = setInterval(poll, POLL_MS);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  const dsConfig: Record<SystemHealth['dataSource'], { text: string; cls: string }> = {
    live: { text: 'LIVE — ESP32 HARDWARE', cls: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' },
    'server-simulated': { text: 'SIMULATED — NO HARDWARE', cls: 'text-amber-400 bg-amber-500/10 border-amber-500/20' },
    reconnecting: { text: 'RECONNECTING...', cls: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20' },
    simulated: { text: 'OFFLINE — CLIENT FALLBACK', cls: 'text-red-400 bg-red-500/10 border-red-500/20' },
  };
  const ds = dsConfig[health.dataSource];

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <span>시스템 컴포넌트 상태</span>
          <span className={`text-[10px] font-bold tracking-widest rounded-full border px-2 py-0.5 ${ds.cls}`}>
            {ds.text}
          </span>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <ComponentStatusCard title="Signal Adapter" health={health.signalAdapter} />
          <ComponentStatusCard title="API Gateway" health={health.apiGateway} />
          <ComponentStatusCard title="Camera" health={health.camera} />
          <ComponentStatusCard title="Database" health={health.database} />
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Zone Occupancy Summary
// ---------------------------------------------------------------------------

function ZoneOccupancySummary() {
  const zones = useZoneStore((s) => s.zones);
  const devices = useDeviceStore((s) => s.devices);

  const totalPresence = useMemo(() => zones.reduce((a, z) => a + z.presenceCount, 0), [zones]);
  const activeZones = useMemo(() => zones.filter((z) => z.presenceCount > 0).length, [zones]);
  const alertZones = useMemo(() => zones.filter((z) => z.status === 'alert').length, [zones]);
  const onlineDevices = useMemo(() => devices.filter((d) => d.status === 'online').length, [devices]);

  const stats = [
    { label: '총 감지 인원', value: totalPresence, color: 'text-cyan-400' },
    { label: '활성 존', value: `${activeZones} / ${zones.length}`, color: 'text-emerald-400' },
    { label: '알림 존', value: alertZones, color: alertZones > 0 ? 'text-red-400' : 'text-gray-500' },
    { label: '온라인 노드', value: `${onlineDevices} / ${devices.length}`, color: 'text-purple-400' },
  ];

  if (zones.length === 0) return null;

  return (
    <Card variant="glow">
      <CardHeader>존별 점유율 요약</CardHeader>
      <CardContent>
        {/* Summary stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
          {stats.map((s) => (
            <div key={s.label} className="text-center">
              <div className={`text-2xl font-bold ${s.color}`}>{s.value}</div>
              <div className="text-[10px] text-gray-500 mt-0.5">{s.label}</div>
            </div>
          ))}
        </div>

        {/* Per-zone rows */}
        <div className="space-y-2">
          {zones.map((zone) => {
            const occupancyPct = Math.min(100, zone.presenceCount * 33);
            const fill =
              zone.status === 'alert'
                ? '#ef4444'
                : zone.presenceCount > 0
                  ? '#22c55e'
                  : '#374151';
            return (
              <div key={zone.id} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-gray-400">{zone.name}</span>
                  <div className="flex items-center gap-2">
                    {zone.status === 'alert' && (
                      <span className="text-[10px] text-red-400 font-bold">ALERT</span>
                    )}
                    <span className="font-mono text-gray-300">
                      {zone.presenceCount} person{zone.presenceCount !== 1 ? 's' : ''}
                    </span>
                  </div>
                </div>
                <div className="h-1.5 rounded-full bg-gray-800 overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{ width: `${occupancyPct}%`, background: fill }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-100">대시보드</h1>
        <p className="text-sm text-gray-500 mt-0.5">실시간 센싱 모니터링</p>
      </div>

      {/* KPI Cards */}
      <KpiCards />

      {/* Sensing HUD — 연결 상태, FPS, 인원 수, 신뢰도, 모드 (ruvnet dashboard-hud.js) */}
      <DashboardHud />

      {/* System Component Status (ruvnet DashboardTab integration) */}
      <SystemComponentsPanel />

      {/* Zone Occupancy Summary */}
      <ZoneOccupancySummary />

      {/* Legacy SystemStatus */}
      <SystemStatus />

      {/* Floor + Camera + Observatory */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="lg:col-span-5">
          <FloorView />
        </div>
        <div className="lg:col-span-4">
          <CameraFeed />
        </div>
        <div className="lg:col-span-3">
          <ObservatoryMini />
        </div>
      </div>

      {/* Alerts + Devices + Signal */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        <AlertPanel />
        <DeviceList />
        <SignalChart />
      </div>
    </div>
  );
}
