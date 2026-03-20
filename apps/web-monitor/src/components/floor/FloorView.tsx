import { useRef, useMemo } from 'react';
import { useDeviceStore } from '@/stores/deviceStore';
import { useZoneStore } from '@/stores/zoneStore';
import { Card, CardHeader } from '@/components/ui';

const FLOOR_WIDTH = 800;
const FLOOR_HEIGHT = 500;
const HEATMAP_COLS = 20;
const HEATMAP_ROWS = 12;
const CELL_W = FLOOR_WIDTH / HEATMAP_COLS;
const CELL_H = FLOOR_HEIGHT / HEATMAP_ROWS;

function motionColor(intensity: number): string {
  if (intensity < 0.1) return 'transparent';
  const clamped = Math.min(intensity, 1);
  if (clamped < 0.3) return `rgba(34,211,238,${clamped * 0.4})`;
  if (clamped < 0.6) return `rgba(250,204,21,${clamped * 0.5})`;
  return `rgba(239,68,68,${Math.min(clamped * 0.6, 0.7)})`;
}

export default function FloorView() {
  const svgRef = useRef<SVGSVGElement>(null);
  const devices = useDeviceStore((s) => s.devices);
  const zones = useZoneStore((s) => s.zones);
  const presenceCount = zones[0]?.presenceCount ?? 0;

  // Generate CSI heatmap from device motion energy
  const heatmap = useMemo(() => {
    const onlineDevices = devices.filter((d) => d.status === 'online' && (d.motion_energy ?? 0) > 0);
    if (onlineDevices.length === 0) return [];

    const cells: { x: number; y: number; intensity: number }[] = [];
    for (let row = 0; row < HEATMAP_ROWS; row++) {
      for (let col = 0; col < HEATMAP_COLS; col++) {
        const cx = col * CELL_W + CELL_W / 2;
        const cy = row * CELL_H + CELL_H / 2;

        // Sum inverse-distance-weighted motion energy from each device
        let totalWeight = 0;
        let weightedMotion = 0;
        for (const dev of onlineDevices) {
          const dx = cx - dev.x;
          const dy = cy - dev.y;
          const dist = Math.sqrt(dx * dx + dy * dy) + 1;
          const weight = 1 / (dist * dist) * 10000;
          totalWeight += weight;
          weightedMotion += weight * (dev.motion_energy ?? 0);
        }
        const intensity = totalWeight > 0 ? weightedMotion / totalWeight : 0;
        // Normalize to 0-1 range
        const normalized = Math.min(intensity / 5, 1);
        if (normalized > 0.05) {
          cells.push({ x: col * CELL_W, y: row * CELL_H, intensity: normalized });
        }
      }
    }
    return cells;
  }, [devices]);

  // Lines between devices showing signal paths
  const signalPaths = useMemo(() => {
    const online = devices.filter((d) => d.status === 'online');
    const paths: { x1: number; y1: number; x2: number; y2: number; motion: number }[] = [];
    for (let i = 0; i < online.length; i++) {
      for (let j = i + 1; j < online.length; j++) {
        const avgMotion = ((online[i].motion_energy ?? 0) + (online[j].motion_energy ?? 0)) / 2;
        paths.push({
          x1: online[i].x, y1: online[i].y,
          x2: online[j].x, y2: online[j].y,
          motion: avgMotion,
        });
      }
    }
    return paths;
  }, [devices]);

  return (
    <Card variant="glow" className="h-[420px]">
      <CardHeader>
        평면도
        {presenceCount > 0 && (
          <span className="ml-2 text-sm text-emerald-400">
            재실 {presenceCount}명
          </span>
        )}
      </CardHeader>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${FLOOR_WIDTH} ${FLOOR_HEIGHT}`}
        className="h-full w-full"
      >
        {/* Grid */}
        <defs>
          <pattern id="grid" width="50" height="50" patternUnits="userSpaceOnUse">
            <path d="M 50 0 L 0 0 0 50" fill="none" stroke="#1f2937" strokeWidth="0.5" />
          </pattern>
          <radialGradient id="coverage-grad">
            <stop offset="0%" stopColor="#22d3ee" stopOpacity="0.08" />
            <stop offset="100%" stopColor="#22d3ee" stopOpacity="0" />
          </radialGradient>
          <filter id="blur-heat">
            <feGaussianBlur stdDeviation="8" />
          </filter>
        </defs>
        <rect width="100%" height="100%" fill="#030712" />
        <rect width="100%" height="100%" fill="url(#grid)" />

        {/* Zones */}
        {zones.map((zone) => (
          <polygon
            key={zone.id}
            points={zone.polygon.map((p) => `${p.x},${p.y}`).join(' ')}
            fill={zone.status === 'active' ? 'rgba(34,211,238,0.06)' : 'rgba(107,114,128,0.03)'}
            stroke={zone.status === 'active' ? '#22d3ee' : '#374151'}
            strokeWidth="1"
            className="transition-colors duration-500"
          />
        ))}

        {/* CSI Heatmap */}
        <g filter="url(#blur-heat)">
          {heatmap.map((cell, i) => (
            <rect
              key={i}
              x={cell.x}
              y={cell.y}
              width={CELL_W}
              height={CELL_H}
              fill={motionColor(cell.intensity)}
            />
          ))}
        </g>

        {/* Signal paths between devices */}
        {signalPaths.map((path, i) => (
          <line
            key={i}
            x1={path.x1} y1={path.y1}
            x2={path.x2} y2={path.y2}
            stroke={path.motion > 1 ? '#fbbf24' : '#22d3ee'}
            strokeWidth={path.motion > 1 ? 1.5 : 0.8}
            strokeOpacity={Math.min(0.15 + path.motion * 0.1, 0.6)}
            strokeDasharray={path.motion > 1 ? 'none' : '4 4'}
          />
        ))}

        {/* Devices */}
        {devices.map((device) => {
          const motion = device.motion_energy ?? 0;
          const hasMotion = motion > 0.5;
          return (
            <g key={device.id} transform={`translate(${device.x},${device.y})`}>
              <circle r="80" fill="url(#coverage-grad)" />
              {/* Motion ring */}
              {device.status === 'online' && hasMotion && (
                <circle
                  r={12 + motion * 3}
                  fill="none"
                  stroke="#fbbf24"
                  strokeWidth="1"
                  strokeOpacity={Math.min(motion * 0.15, 0.6)}
                  className="animate-ping"
                />
              )}
              <circle
                r="6"
                fill={device.status === 'online' ? (hasMotion ? '#fbbf24' : '#34d399') : '#4b5563'}
                className={device.status === 'online' ? 'animate-pulse' : ''}
              />
              <text y="20" textAnchor="middle" fill="#9ca3af" fontSize="10">
                {device.name}
              </text>
              {device.status === 'online' && (
                <text y="32" textAnchor="middle" fill="#6b7280" fontSize="8">
                  {device.signalStrength}dBm {motion > 0 ? `M:${motion.toFixed(1)}` : ''}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </Card>
  );
}
