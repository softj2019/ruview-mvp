import { useRef, useMemo, useState, useCallback } from 'react';
import { useDeviceStore, type Device } from '@/stores/deviceStore';
import { useZoneStore } from '@/stores/zoneStore';
import { Card, CardHeader } from '@/components/ui';

const FLOOR_WIDTH = 800;
const FLOOR_HEIGHT = 400;
const HEATMAP_COLS = 20;
const HEATMAP_ROWS = 10;
const CELL_W = FLOOR_WIDTH / HEATMAP_COLS;
const CELL_H = FLOOR_HEIGHT / HEATMAP_ROWS;

// Room definitions: 1001-1004, left to right
const ROOMS = [
  { id: '1001', x: 20, y: 20, w: 190, h: 360, label: '1001' },
  { id: '1002', x: 210, y: 20, w: 190, h: 360, label: '1002' },
  { id: '1003', x: 400, y: 20, w: 190, h: 360, label: '1003' },
  { id: '1004', x: 590, y: 20, w: 190, h: 360, label: '1004' },
];

// Door positions (bottom of each room)
const DOORS = [
  { x: 100, y: 380, w: 30 },
  { x: 290, y: 380, w: 30 },
  { x: 480, y: 380, w: 30 },
  { x: 670, y: 380, w: 30 },
];

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
  const updateDevice = useDeviceStore((s) => s.updateDevice);
  const zones = useZoneStore((s) => s.zones);
  const presenceCount = zones[0]?.presenceCount ?? 0;

  // Drag state
  const [dragging, setDragging] = useState<string | null>(null);
  const dragOffset = useRef({ dx: 0, dy: 0 });

  const svgPoint = useCallback((clientX: number, clientY: number) => {
    const svg = svgRef.current;
    if (!svg) return { x: 0, y: 0 };
    const pt = svg.createSVGPoint();
    pt.x = clientX;
    pt.y = clientY;
    const ctm = svg.getScreenCTM();
    if (!ctm) return { x: 0, y: 0 };
    const svgP = pt.matrixTransform(ctm.inverse());
    return { x: svgP.x, y: svgP.y };
  }, []);

  const handlePointerDown = useCallback((e: React.PointerEvent, device: Device) => {
    e.preventDefault();
    const p = svgPoint(e.clientX, e.clientY);
    dragOffset.current = { dx: device.x - p.x, dy: device.y - p.y };
    setDragging(device.id);
    (e.target as Element).setPointerCapture(e.pointerId);
  }, [svgPoint]);

  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (!dragging) return;
    const p = svgPoint(e.clientX, e.clientY);
    const nx = Math.max(20, Math.min(FLOOR_WIDTH - 20, p.x + dragOffset.current.dx));
    const ny = Math.max(20, Math.min(FLOOR_HEIGHT - 20, p.y + dragOffset.current.dy));
    updateDevice(dragging, { x: Math.round(nx), y: Math.round(ny) });
  }, [dragging, svgPoint, updateDevice]);

  const handlePointerUp = useCallback(() => {
    if (dragging) {
      // Persist new position to signal-adapter
      const dev = devices.find((d) => d.id === dragging);
      if (dev) {
        fetch(`/api/devices/${dev.id}/position`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ x: dev.x, y: dev.y }),
        }).catch(() => {});
      }
    }
    setDragging(null);
  }, [dragging, devices]);

  // CSI heatmap
  const heatmap = useMemo(() => {
    const onlineDevices = devices.filter((d) => d.status === 'online' && (d.motion_energy ?? 0) > 0);
    if (onlineDevices.length === 0) return [];
    const cells: { x: number; y: number; intensity: number }[] = [];
    for (let row = 0; row < HEATMAP_ROWS; row++) {
      for (let col = 0; col < HEATMAP_COLS; col++) {
        const cx = col * CELL_W + CELL_W / 2;
        const cy = row * CELL_H + CELL_H / 2;
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
        const normalized = Math.min(intensity / 5, 1);
        if (normalized > 0.05) {
          cells.push({ x: col * CELL_W, y: row * CELL_H, intensity: normalized });
        }
      }
    }
    return cells;
  }, [devices]);

  // Signal paths
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
        className="h-full w-full select-none"
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerUp}
      >
        <defs>
          <pattern id="grid" width="50" height="50" patternUnits="userSpaceOnUse">
            <path d="M 50 0 L 0 0 0 50" fill="none" stroke="#1a2332" strokeWidth="0.5" />
          </pattern>
          <radialGradient id="coverage-grad">
            <stop offset="0%" stopColor="#22d3ee" stopOpacity="0.06" />
            <stop offset="100%" stopColor="#22d3ee" stopOpacity="0" />
          </radialGradient>
          <filter id="blur-heat">
            <feGaussianBlur stdDeviation="8" />
          </filter>
        </defs>

        {/* Background */}
        <rect width="100%" height="100%" fill="#080c14" />
        <rect width="100%" height="100%" fill="url(#grid)" />

        {/* Outer wall */}
        <rect x="15" y="15" width={FLOOR_WIDTH - 30} height={FLOOR_HEIGHT - 30}
          fill="none" stroke="#374151" strokeWidth="2" rx="2" />

        {/* Rooms */}
        {ROOMS.map((room) => (
          <g key={room.id}>
            <rect
              x={room.x} y={room.y} width={room.w} height={room.h}
              fill="rgba(30,41,59,0.3)"
              stroke="#334155"
              strokeWidth="1.5"
              rx="1"
            />
            <text
              x={room.x + room.w / 2}
              y={room.y + room.h / 2}
              textAnchor="middle"
              dominantBaseline="middle"
              fill="#475569"
              fontSize="16"
              fontWeight="600"
            >
              {room.label}
            </text>
          </g>
        ))}

        {/* Doors */}
        {DOORS.map((door, i) => (
          <g key={i}>
            <rect
              x={door.x} y={door.y - 3} width={door.w} height="6"
              fill="#1e293b" stroke="#4b5563" strokeWidth="1" rx="1"
            />
            <line
              x1={door.x + door.w / 2} y1={door.y + 3}
              x2={door.x + door.w / 2} y2={door.y + 12}
              stroke="#4b5563" strokeWidth="0.5" strokeDasharray="2 2"
            />
          </g>
        ))}

        {/* CSI Heatmap */}
        <g filter="url(#blur-heat)">
          {heatmap.map((cell, i) => (
            <rect
              key={i}
              x={cell.x} y={cell.y}
              width={CELL_W} height={CELL_H}
              fill={motionColor(cell.intensity)}
            />
          ))}
        </g>

        {/* Signal paths */}
        {signalPaths.map((path, i) => (
          <line
            key={i}
            x1={path.x1} y1={path.y1}
            x2={path.x2} y2={path.y2}
            stroke={path.motion > 1 ? '#fbbf24' : '#22d3ee'}
            strokeWidth={path.motion > 1 ? 1.5 : 0.8}
            strokeOpacity={Math.min(0.15 + path.motion * 0.1, 0.5)}
            strokeDasharray={path.motion > 1 ? 'none' : '4 4'}
          />
        ))}

        {/* Devices (draggable) */}
        {devices.map((device) => {
          const motion = device.motion_energy ?? 0;
          const hasMotion = motion > 0.5;
          const breathBpm = device.breathing_bpm;
          const isBreathing = (breathBpm ?? 0) > 5;
          const isDragging = dragging === device.id;
          return (
            <g
              key={device.id}
              transform={`translate(${device.x},${device.y})`}
              style={{ cursor: isDragging ? 'grabbing' : 'grab' }}
              onPointerDown={(e) => handlePointerDown(e, device)}
            >
              {/* Coverage area */}
              <circle r="70" fill="url(#coverage-grad)" />

              {/* Breathing detection */}
              {device.status === 'online' && isBreathing && (
                <>
                  <circle r="18" fill="rgba(244,63,94,0.1)" stroke="#f43f5e"
                    strokeWidth="1" strokeOpacity="0.4" className="animate-pulse" />
                  <circle r="3.5" fill="#f43f5e" className="animate-ping" opacity="0.6" />
                </>
              )}

              {/* Motion ring */}
              {device.status === 'online' && hasMotion && !isBreathing && (
                <circle r={10 + motion * 2} fill="none" stroke="#fbbf24"
                  strokeWidth="1" strokeOpacity={Math.min(motion * 0.15, 0.6)}
                  className="animate-ping" />
              )}

              {/* Node dot */}
              <circle
                r={isDragging ? 8 : 5}
                fill={device.status === 'online'
                  ? (isBreathing ? '#f43f5e' : hasMotion ? '#fbbf24' : '#34d399')
                  : '#4b5563'}
                stroke={isDragging ? '#fff' : 'none'}
                strokeWidth={isDragging ? 2 : 0}
                className={device.status === 'online' && !isDragging ? 'animate-pulse' : ''}
              />

              {/* Label */}
              <text y="-12" textAnchor="middle" fill="#94a3b8" fontSize="9" fontWeight="500">
                {device.name?.replace('ESP32 ', '')}
              </text>

              {/* Status text */}
              {device.status === 'online' && (
                <text y="18" textAnchor="middle" fill="#64748b" fontSize="7.5">
                  {isBreathing ? `${breathBpm?.toFixed(0)} BPM` : `${device.signalStrength}dBm`}
                </text>
              )}
              {device.status === 'offline' && (
                <text y="18" textAnchor="middle" fill="#ef4444" fontSize="7.5">
                  offline
                </text>
              )}

              {/* Person count indicator */}
              {device.status === 'online' && (device.n_persons ?? 0) > 0 && (
                <>
                  {Array.from({ length: Math.min(device.n_persons ?? 0, 8) }).map((_, pi) => {
                    const angle = (pi / Math.min(device.n_persons ?? 1, 8)) * Math.PI * 2 - Math.PI / 2;
                    const r = 35;
                    const px = Math.cos(angle) * r;
                    const py = Math.sin(angle) * r;
                    return (
                      <g key={pi} transform={`translate(${px},${py})`}>
                        <circle r="6" fill="rgba(139,92,246,0.2)" stroke="#8b5cf6" strokeWidth="0.8" />
                        <circle r="2" fill="#8b5cf6" cy="-2" />
                        <line x1="0" y1="0" x2="0" y2="4" stroke="#8b5cf6" strokeWidth="1" />
                      </g>
                    );
                  })}
                  <g transform="translate(20,-20)">
                    <rect x="-8" y="-6" width="16" height="12" rx="3" fill="#8b5cf6" opacity="0.9" />
                    <text textAnchor="middle" dominantBaseline="middle" fill="#fff" fontSize="8" fontWeight="bold">
                      {device.n_persons}
                    </text>
                  </g>
                </>
              )}

              {/* Coordinates (while dragging) */}
              {isDragging && (
                <text y="28" textAnchor="middle" fill="#fbbf24" fontSize="7">
                  ({device.x}, {device.y})
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </Card>
  );
}
