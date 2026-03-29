import { useMemo, useRef, useEffect, useCallback } from 'react';
import {
  LineChart,
  Line,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Cell,
} from 'recharts';
import { Card, CardHeader, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { useDeviceStore, type Device } from '@/stores/deviceStore';
import { useZoneStore } from '@/stores/zoneStore';
import { useSignalStore } from '@/stores/signalStore';
import { SignalViz } from '@/components/SignalViz';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Map RSSI value to a color. */
function rssiColor(rssi: number): string {
  if (rssi >= -50) return '#22c55e'; // green — excellent
  if (rssi >= -65) return '#84cc16'; // lime — good
  if (rssi >= -75) return '#eab308'; // yellow — fair
  return '#ef4444'; // red — poor
}

/** Classify motion level from zone presenceCount. */
function motionLevel(presenceCount: number): {
  label: string;
  variant: 'default' | 'success' | 'warning';
} {
  if (presenceCount <= 0) return { label: 'ABSENT', variant: 'default' };
  if (presenceCount <= 2) return { label: 'PRESENT', variant: 'success' };
  return { label: 'ACTIVE', variant: 'warning' };
}

/** Clamp a value between 0 and max, returning percentage 0-100. */
function pct(value: number, max: number): number {
  return Math.min(100, Math.max(0, (value / max) * 100));
}

/** Bar fill color based on percentage. */
function barColor(percent: number): string {
  if (percent < 30) return '#3b82f6'; // blue
  if (percent < 70) return '#22c55e'; // green
  return '#f59e0b'; // amber
}

/** Infer CSI pose from device metrics. */
function inferPose(device: Device): { pose: string; confidence: number } {
  const energy = device.motion_energy ?? 0;
  const br = device.csi_breathing_bpm ?? device.breathing_bpm ?? 0;
  const hr = device.csi_heart_rate ?? device.heart_rate ?? 0;
  const presenceBase = device.presence_score ?? 0;

  if (energy > 5) return { pose: 'Walking', confidence: Math.min(0.95, 0.5 + energy * 0.05) };
  if (energy > 1.5) return { pose: 'Standing', confidence: Math.min(0.9, 0.4 + energy * 0.1) };
  if (br > 0 && hr > 0) {
    const vitalConf = Math.min(0.95, 0.3 + (br / 30) * 0.35 + (hr / 100) * 0.3);
    return { pose: 'Sitting', confidence: presenceBase > 0 ? Math.min(0.95, (vitalConf + presenceBase) / 2) : vitalConf };
  }
  return { pose: 'Unknown', confidence: 0 };
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** RSSI sparkline — last 20 data points per device. */
function RssiSparkline({ history }: { history: { idx: number; rssi: number }[] }) {
  if (history.length < 2) {
    return <div className="h-12 flex items-center justify-center text-xs text-gray-600">No data</div>;
  }

  const lastRssi = history[history.length - 1].rssi;
  const color = rssiColor(lastRssi);

  return (
    <ResponsiveContainer width="100%" height={48}>
      <LineChart data={history} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
        <Line
          type="monotone"
          dataKey="rssi"
          stroke={color}
          strokeWidth={1.5}
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

/** Horizontal feature bar with label and value. */
function FeatureBar({
  label,
  value,
  max,
  unit,
  colorOverride,
}: {
  label: string;
  value: number;
  max: number;
  unit?: string;
  colorOverride?: string;
}) {
  const p = pct(value, max);
  const fill = colorOverride ?? barColor(p);
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-gray-400">{label}</span>
        <span className="text-gray-300 font-mono">
          {value.toFixed(2)}
          {unit ? ` ${unit}` : ''}
        </span>
      </div>
      <div className="h-2 rounded-full bg-gray-800 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-300"
          style={{ width: `${p}%`, background: fill }}
        />
      </div>
    </div>
  );
}

/** Classification confidence indicator. */
function ClassificationIndicator({
  motionLabel,
  confidence,
}: {
  motionLabel: string;
  confidence: number;
}) {
  const confPct = Math.round(confidence * 100);

  const labelColor =
    motionLabel === 'ACTIVE'
      ? 'text-amber-400 border-amber-500/30 bg-amber-500/10'
      : motionLabel === 'PRESENT_STILL' || motionLabel === 'PRESENT'
        ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10'
        : 'text-gray-400 border-gray-600/30 bg-gray-700/20';

  return (
    <div className="space-y-2">
      <div className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-bold tracking-widest border ${labelColor}`}>
        {motionLabel}
      </div>
      <div className="space-y-1">
        <div className="flex justify-between text-xs">
          <span className="text-gray-500">Confidence</span>
          <span className="font-mono text-gray-300">{confPct}%</span>
        </div>
        <div className="h-2 rounded-full bg-gray-800 overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-300"
            style={{
              width: `${confPct}%`,
              background: confidence > 0.7 ? '#22c55e' : confidence > 0.4 ? '#eab308' : '#6b7280',
            }}
          />
        </div>
      </div>
    </div>
  );
}

/** Pose indicator with confidence ring. */
function PoseIndicator({ pose, confidence }: { pose: string; confidence: number }) {
  const confPct = Math.round(confidence * 100);
  const poseIcons: Record<string, string> = {
    Walking: '\u{1F6B6}',
    Standing: '\u{1F9CD}',
    Sitting: '\u{1FA91}',
    Unknown: '\u2753',
  };

  return (
    <div className="flex items-center gap-3">
      <div className="relative w-10 h-10">
        <svg viewBox="0 0 36 36" className="absolute inset-0 w-full h-full -rotate-90">
          <circle cx="18" cy="18" r="15" fill="none" stroke="#1f2937" strokeWidth="3" />
          <circle
            cx="18"
            cy="18"
            r="15"
            fill="none"
            stroke={confidence > 0.6 ? '#22c55e' : confidence > 0.3 ? '#eab308' : '#6b7280'}
            strokeWidth="3"
            strokeDasharray={`${confPct * 0.94} 100`}
            strokeLinecap="round"
          />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-sm">
          {poseIcons[pose] ?? '\u2753'}
        </span>
      </div>
      <div>
        <div className="text-sm font-medium text-gray-200">{pose}</div>
        <div className="text-xs text-gray-500">{confPct}% confidence</div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// WiFi Sensing 3D Field — canvas-based Gaussian-splat placeholder
// ---------------------------------------------------------------------------

/**
 * WiFi3DField renders a lightweight canvas-based approximation of a
 * Gaussian-splat signal field.  It animates a set of coloured radial
 * gradients ("splats") whose radii pulse with motion energy.
 */
function WiFi3DField({
  motionEnergy,
  presenceCount,
}: {
  motionEnergy: number;
  presenceCount: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const frameRef = useRef<number>(0);
  const tRef = useRef<number>(0);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const W = canvas.width;
    const H = canvas.height;
    tRef.current += 0.02;
    const t = tRef.current;

    ctx.clearRect(0, 0, W, H);

    // Background grid
    ctx.strokeStyle = 'rgba(34,211,238,0.05)';
    ctx.lineWidth = 0.5;
    const step = 32;
    for (let x = 0; x < W; x += step) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
    }
    for (let y = 0; y < H; y += step) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
    }

    // Splat positions (static per device, vary by presence)
    const splats = [
      { cx: W * 0.25, cy: H * 0.35, hue: 185 },
      { cx: W * 0.70, cy: H * 0.30, hue: 165 },
      { cx: W * 0.50, cy: H * 0.65, hue: 210 },
      { cx: W * 0.20, cy: H * 0.70, hue: 140 },
      { cx: W * 0.80, cy: H * 0.70, hue: 195 },
    ];

    const baseR = 28 + motionEnergy * 6;

    splats.forEach(({ cx, cy, hue }, i) => {
      const r = baseR * (1 + 0.15 * Math.sin(t + i * 1.3));
      const alpha = presenceCount > 0 ? 0.55 : 0.22;
      const grd = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
      grd.addColorStop(0, `hsla(${hue}, 80%, 65%, ${alpha})`);
      grd.addColorStop(0.5, `hsla(${hue}, 70%, 45%, ${alpha * 0.4})`);
      grd.addColorStop(1, `hsla(${hue}, 60%, 30%, 0)`);
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.fillStyle = grd;
      ctx.fill();
    });

    // Scan ring
    if (presenceCount > 0) {
      const ringR = 20 + 60 * ((t * 0.4) % 1);
      const ringAlpha = 1 - (t * 0.4) % 1;
      const cx = W / 2;
      const cy = H / 2;
      ctx.beginPath();
      ctx.arc(cx, cy, ringR, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(34,211,238,${ringAlpha * 0.6})`;
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }

    frameRef.current = requestAnimationFrame(draw);
  }, [motionEnergy, presenceCount]);

  useEffect(() => {
    frameRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frameRef.current);
  }, [draw]);

  return (
    <canvas
      ref={canvasRef}
      width={560}
      height={220}
      className="w-full h-full rounded-lg"
      style={{ display: 'block' }}
    />
  );
}

// ---------------------------------------------------------------------------
// Zone Presence Overview Bar Chart
// ---------------------------------------------------------------------------

function ZonePresenceChart() {
  const zones = useZoneStore((s) => s.zones);

  const data = useMemo(
    () =>
      zones.map((z) => ({
        name: z.name,
        presenceCount: z.presenceCount,
        status: z.status,
      })),
    [zones],
  );

  if (data.length === 0) {
    return (
      <div className="h-32 flex items-center justify-center text-sm text-gray-600">
        No zones configured
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={140}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
        <XAxis dataKey="name" tick={{ fill: '#9ca3af', fontSize: 10 }} axisLine={false} tickLine={false} />
        <YAxis hide allowDecimals={false} />
        <Bar dataKey="presenceCount" radius={[4, 4, 0, 0]}>
          {data.map((entry, idx) => (
            <Cell
              key={idx}
              fill={
                entry.status === 'alert'
                  ? '#ef4444'
                  : entry.presenceCount > 0
                    ? '#22c55e'
                    : '#374151'
              }
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ---------------------------------------------------------------------------
// Per-device sensing card
// ---------------------------------------------------------------------------

function DeviceSensingCard({ device }: { device: Device }) {
  const zones = useZoneStore((s) => s.zones);
  const signalHistory = useSignalStore((s) => s.history);

  // Last 20 RSSI readings for sparkline
  const rssiHistory = useMemo(() => {
    const recent = signalHistory.slice(-20);
    return recent.map((p, i) => ({ idx: i, rssi: p.rssi }));
  }, [signalHistory]);

  const zone = zones.find((z) => z.id === device.zone_id);
  const presence = zone?.presenceCount ?? 0;
  const motion = motionLevel(presence);

  // Signal features
  const motionEnergy = device.motion_energy ?? 0;
  const breathingBpm = device.csi_breathing_bpm ?? device.breathing_bpm ?? 0;
  const heartRate = device.csi_heart_rate ?? device.heart_rate ?? 0;
  const presenceScore = device.presence_score ?? 0;

  // Pose
  const { pose, confidence } = inferPose(device);

  // Derive variance and spectral power approximations from available metrics
  const variance = motionEnergy * 1.2;
  const spectralPower = breathingBpm > 0 ? breathingBpm / 30 : 0;

  return (
    <Card className="flex flex-col gap-4">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span
              className="inline-block w-2 h-2 rounded-full"
              style={{
                background: device.status === 'online' ? '#22c55e' : '#ef4444',
                boxShadow: device.status === 'online' ? '0 0 6px #22c55e' : '0 0 6px #ef4444',
              }}
            />
            <span className="text-gray-200 font-medium text-sm">{device.name}</span>
          </div>
          <Badge variant={motion.variant} className="mr-1">{motion.label}</Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* WiFi 3D Field */}
        <div className="rounded-lg bg-gray-950 border border-gray-800 overflow-hidden" style={{ height: 140 }}>
          <WiFi3DField motionEnergy={motionEnergy} presenceCount={presence} />
        </div>

        {/* RSSI Sparkline */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-gray-500 uppercase tracking-wider">RSSI</span>
            <span className="text-xs font-mono text-gray-300">
              {device.signalStrength != null ? `${device.signalStrength} dBm` : '-- dBm'}
            </span>
          </div>
          <RssiSparkline history={rssiHistory} />
        </div>

        {/* Signal Feature Bars */}
        <div className="space-y-2">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Signal Features</p>
          <FeatureBar label="Variance" value={variance} max={10} />
          <FeatureBar label="Motion Band" value={motionEnergy} max={10} colorOverride="#f59e0b" />
          <FeatureBar label="Breathing Band" value={breathingBpm} max={40} unit="BPM" colorOverride="#22c55e" />
          <FeatureBar label="Spectral Power" value={spectralPower} max={2} colorOverride="#a78bfa" />
        </div>

        {/* Classification Confidence */}
        <div className="pt-2 border-t border-gray-800">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Classification</p>
          <ClassificationIndicator motionLabel={motion.label} confidence={presenceScore > 0 ? presenceScore : confidence} />
        </div>

        {/* CSI Pose Indicator */}
        <div className="pt-2 border-t border-gray-800">
          <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">CSI Pose</div>
          <PoseIndicator pose={pose} confidence={confidence} />
        </div>

        {/* Detail row */}
        <div className="pt-2 border-t border-gray-800 space-y-1">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Details</p>
          <div className="flex justify-between text-xs">
            <span className="text-gray-500">Heart Rate</span>
            <span className="font-mono text-gray-300">{heartRate > 0 ? `${heartRate.toFixed(0)} BPM` : '--'}</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-gray-500">Presence Score</span>
            <span className="font-mono text-gray-300">{(presenceScore * 100).toFixed(0)}%</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function SensingPage() {
  const devices = useDeviceStore((s) => s.devices);
  const signalHistory = useSignalStore((s) => s.history);
  const zones = useZoneStore((s) => s.zones);

  // Aggregate presence across all zones
  const totalPresence = useMemo(() => zones.reduce((acc, z) => acc + z.presenceCount, 0), [zones]);
  const avgRssi = useMemo(() => {
    if (signalHistory.length === 0) return null;
    const last = signalHistory.slice(-10);
    return last.reduce((acc, p) => acc + p.rssi, 0) / last.length;
  }, [signalHistory]);

  // Data source banner state derived from signal history freshness
  const dataSource = signalHistory.length > 0 ? 'LIVE' : 'RECONNECTING';
  const bannerClass =
    dataSource === 'LIVE'
      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
      : 'bg-amber-500/10 text-amber-400 border-amber-500/20';

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-100">WiFi Sensing</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          CSI 신호 특성, 모션 분류, 자세 추정 — 디바이스별 실시간 분석
        </p>
      </div>

      {/* Data source status banner */}
      <div className={`flex items-center gap-2 rounded-lg border px-4 py-2 text-xs font-semibold tracking-widest ${bannerClass}`}>
        <span
          className="inline-block w-2 h-2 rounded-full"
          style={{
            background: dataSource === 'LIVE' ? '#22c55e' : '#f59e0b',
            boxShadow: dataSource === 'LIVE' ? '0 0 6px #22c55e' : '0 0 6px #f59e0b',
          }}
        />
        {dataSource === 'LIVE' ? 'LIVE — ESP32 HARDWARE' : 'RECONNECTING...'}
        {avgRssi != null && (
          <span className="ml-auto font-mono font-normal text-gray-400">
            avg RSSI {avgRssi.toFixed(1)} dBm
          </span>
        )}
        <span className="ml-auto font-mono font-normal text-gray-400">
          {totalPresence} person{totalPresence !== 1 ? 's' : ''} detected
        </span>
      </div>

      {/* Zone Presence Overview */}
      <Card variant="glow">
        <CardHeader>Zone Presence Overview</CardHeader>
        <CardContent>
          <ZonePresenceChart />
        </CardContent>
      </Card>

      {/* CSI Signal Visualization */}
      <Card variant="glow">
        <CardHeader>CSI 신호 분석</CardHeader>
        <CardContent>
          <SignalViz
            deviceId={devices.length > 0 ? devices[0].name : undefined}
            demoMode
          />
        </CardContent>
      </Card>

      {/* About section */}
      <Card>
        <CardHeader>About This Data</CardHeader>
        <CardContent>
          <p className="text-xs text-gray-500 leading-relaxed">
            Metrics are computed from WiFi Channel State Information (CSI).
            With <span className="text-gray-300 font-medium">1 ESP32</span> you get presence
            detection, breathing estimation, and gross motion. Add{' '}
            <span className="text-gray-300 font-medium">3–4+ ESP32 nodes</span> around the room
            for spatial resolution and limb-level tracking.
          </p>
        </CardContent>
      </Card>

      {/* Per-device sensing cards */}
      {devices.length === 0 ? (
        <Card>
          <CardContent>
            <div className="text-center py-8 text-gray-500">
              No devices connected. Waiting for data...
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {devices.map((device) => (
            <DeviceSensingCard key={device.id} device={device} />
          ))}
        </div>
      )}
    </div>
  );
}
