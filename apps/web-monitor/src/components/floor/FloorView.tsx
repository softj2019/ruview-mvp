import { useRef } from 'react';
import { useDeviceStore } from '@/stores/deviceStore';
import { useZoneStore } from '@/stores/zoneStore';
import { Card, CardHeader } from '@/components/ui';

const FLOOR_WIDTH = 800;
const FLOOR_HEIGHT = 500;

export default function FloorView() {
  const svgRef = useRef<SVGSVGElement>(null);
  const devices = useDeviceStore((s) => s.devices);
  const zones = useZoneStore((s) => s.zones);

  return (
    <Card variant="glow" className="h-[420px]">
      <CardHeader>평면도</CardHeader>
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
        </defs>
        <rect width="100%" height="100%" fill="#030712" />
        <rect width="100%" height="100%" fill="url(#grid)" />

        {/* Zones */}
        {zones.map((zone) => (
          <polygon
            key={zone.id}
            points={zone.polygon.map((p) => `${p.x},${p.y}`).join(' ')}
            fill={zone.status === 'active' ? 'rgba(34,211,238,0.08)' : 'rgba(107,114,128,0.03)'}
            stroke={zone.status === 'active' ? '#22d3ee' : '#374151'}
            strokeWidth="1"
            className="transition-colors duration-500"
          />
        ))}

        {/* Devices */}
        {devices.map((device) => (
          <g key={device.id} transform={`translate(${device.x},${device.y})`}>
            <circle r="80" fill="url(#coverage-grad)" />
            <circle
              r="6"
              fill={device.status === 'online' ? '#34d399' : '#4b5563'}
              className={device.status === 'online' ? 'animate-pulse' : ''}
            />
            <text y="20" textAnchor="middle" fill="#9ca3af" fontSize="10">
              {device.name}
            </text>
          </g>
        ))}
      </svg>
    </Card>
  );
}
