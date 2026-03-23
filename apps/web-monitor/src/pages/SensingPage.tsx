import { useMemo } from 'react';
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

  if (energy > 5) return { pose: 'Walking', confidence: Math.min(0.95, 0.5 + energy * 0.05) };
  if (energy > 1.5) return { pose: 'Standing', confidence: Math.min(0.9, 0.4 + energy * 0.1) };
  if (br > 0 && hr > 0) return { pose: 'Sitting', confidence: 0.7 };
  return { pose: 'Unknown', confidence: 0 };
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** RSSI sparkline — last 60 data points rendered as a mini line chart. */
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

/** Horizontal bar with label and value. */
function FeatureBar({
  label,
  value,
  max,
  unit,
}: {
  label: string;
  value: number;
  max: number;
  unit?: string;
}) {
  const p = pct(value, max);
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-gray-400">{label}</span>
        <span className="text-gray-300 font-mono">
          {value.toFixed(1)}
          {unit ? ` ${unit}` : ''}
        </span>
      </div>
      <div className="h-2 rounded-full bg-gray-800 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-300"
          style={{ width: `${p}%`, background: barColor(p) }}
        />
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
        {/* Confidence ring via SVG */}
        <svg viewBox="0 0 36 36" className="absolute inset-0 w-full h-full -rotate-90">
          <circle
            cx="18"
            cy="18"
            r="15"
            fill="none"
            stroke="#1f2937"
            strokeWidth="3"
          />
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

/** Per-device sensing card. */
function DeviceSensingCard({ device }: { device: Device }) {
  const zones = useZoneStore((s) => s.zones);
  const signalHistory = useSignalStore((s) => s.history);

  // Build last-60 RSSI readings for this device from signal history
  const rssiHistory = useMemo(() => {
    // signalStore has global signal points; approximate per-device by using all points
    // (in production, filter by device ID in signal point metadata)
    const recent = signalHistory.slice(-60);
    return recent.map((p, i) => ({ idx: i, rssi: p.rssi }));
  }, [signalHistory]);

  // Find zone this device belongs to
  const zone = zones.find((z) => z.id === device.zone_id);
  const presence = zone?.presenceCount ?? 0;
  const motion = motionLevel(presence);

  // Signal features
  const motionEnergy = device.motion_energy ?? 0;
  const breathingBpm = device.csi_breathing_bpm ?? device.breathing_bpm ?? 0;
  const heartRate = device.csi_heart_rate ?? device.heart_rate ?? 0;

  // Pose
  const { pose, confidence } = inferPose(device);

  return (
    <Card className="flex flex-col gap-4">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span
              className="inline-block w-2 h-2 rounded-full"
              style={{
                background: device.status === 'online' ? '#22c55e' : '#ef4444',
                boxShadow:
                  device.status === 'online' ? '0 0 6px #22c55e' : '0 0 6px #ef4444',
              }}
            />
            <span className="text-gray-200 font-medium text-sm">{device.name}</span>
          </div>
          <Badge variant={motion.variant}>{motion.label}</Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
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
          <FeatureBar label="Motion Energy" value={motionEnergy} max={10} />
          <FeatureBar label="Breathing Rate" value={breathingBpm} max={40} unit="BPM" />
          <FeatureBar label="Heart Rate" value={heartRate} max={120} unit="BPM" />
        </div>

        {/* CSI Pose Indicator */}
        <div className="pt-2 border-t border-gray-800">
          <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">CSI Pose</div>
          <PoseIndicator pose={pose} confidence={confidence} />
        </div>
      </CardContent>
    </Card>
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
// Page
// ---------------------------------------------------------------------------

export default function SensingPage() {
  const devices = useDeviceStore((s) => s.devices);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-100">WiFi Sensing</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          CSI signal features, motion classification, and pose estimation per device
        </p>
      </div>

      {/* Zone Presence Overview */}
      <Card variant="glow">
        <CardHeader>Zone Presence Overview</CardHeader>
        <CardContent>
          <ZonePresenceChart />
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
