import { useRef, useState, useCallback } from 'react';
import { useDeviceStore } from '@/stores/deviceStore';
import { useZoneStore } from '@/stores/zoneStore';

const FLOOR_WIDTH = 800;
const FLOOR_HEIGHT = 600;

export default function FloorView() {
  const svgRef = useRef<SVGSVGElement>(null);
  const [viewBox, setViewBox] = useState(`0 0 ${FLOOR_WIDTH} ${FLOOR_HEIGHT}`);
  const devices = useDeviceStore((s) => s.devices);
  const zones = useZoneStore((s) => s.zones);

  return (
    <div className="card-glow h-[400px] relative">
      <h3 className="text-sm font-medium text-gray-400 mb-2">Floor Plan</h3>
      <svg
        ref={svgRef}
        viewBox={viewBox}
        className="w-full h-full"
        style={{ background: 'radial-gradient(circle, #12121A 0%, #0A0A0F 100%)' }}
      >
        {/* Grid */}
        <defs>
          <pattern id="grid" width="50" height="50" patternUnits="userSpaceOnUse">
            <path d="M 50 0 L 0 0 0 50" fill="none" stroke="#222230" strokeWidth="0.5" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#grid)" />

        {/* Zones */}
        {zones.map((zone) => (
          <polygon
            key={zone.id}
            points={zone.polygon.map((p) => `${p.x},${p.y}`).join(' ')}
            fill={zone.status === 'active' ? 'rgba(0,240,255,0.1)' : 'rgba(100,100,100,0.05)'}
            stroke={zone.status === 'active' ? '#00F0FF' : '#333'}
            strokeWidth="1"
          />
        ))}

        {/* Devices */}
        {devices.map((device) => (
          <g key={device.id} transform={`translate(${device.x},${device.y})`}>
            {/* Coverage arc */}
            <circle
              r="80"
              fill={device.status === 'online' ? 'rgba(0,255,136,0.05)' : 'rgba(100,100,100,0.02)'}
              stroke={device.status === 'online' ? '#00FF8844' : '#33333344'}
              strokeWidth="0.5"
            />
            {/* Device marker */}
            <circle
              r="6"
              fill={device.status === 'online' ? '#00FF88' : '#666'}
              className={device.status === 'online' ? 'animate-pulse-slow' : ''}
            />
            <text y="18" textAnchor="middle" className="fill-gray-400 text-[10px]">
              {device.name}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}
