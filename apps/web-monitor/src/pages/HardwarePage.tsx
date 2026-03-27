import { useState, useEffect, useCallback, useRef } from 'react';
import { Card, CardHeader, CardContent } from '@/components/ui/Card';
import { useDeviceStore, type Device } from '@/stores/deviceStore';
import { useZoneStore } from '@/stores/zoneStore';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Antenna array types
// ---------------------------------------------------------------------------

interface AntennaState {
  id: string;
  type: 'tx' | 'rx';
  row: number;
  col: number;
  active: boolean;
}

function buildDefaultAntennas(): AntennaState[] {
  // 3x3 grid: top row TX (3), bottom two rows RX (6)
  const antennas: AntennaState[] = [];
  for (let col = 0; col < 3; col++) {
    antennas.push({ id: `tx-${col}`, type: 'tx', row: 0, col, active: true });
  }
  for (let row = 1; row < 3; row++) {
    for (let col = 0; col < 3; col++) {
      antennas.push({ id: `rx-${row}-${col}`, type: 'rx', row, col, active: true });
    }
  }
  return antennas;
}

function calcSignalQuality(txActive: number, rxActive: number): number {
  if (txActive === 0 || rxActive === 0) return 0;
  return Math.round((txActive / 3) * 0.4 * 100 + (rxActive / 6) * 0.6 * 100);
}

// ---------------------------------------------------------------------------
// Antenna Array Visualization
// ---------------------------------------------------------------------------

function AntennaArrayPanel({ deviceId }: { deviceId: string | null }) {
  const [antennas, setAntennas] = useState<AntennaState[]>(buildDefaultAntennas());
  const [amplitude, setAmplitude] = useState(0);
  const [phase, setPhase] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const toggleAntenna = useCallback((id: string) => {
    setAntennas((prev) =>
      prev.map((a) => (a.id === id ? { ...a, active: !a.active } : a)),
    );
  }, []);

  const resetAll = useCallback(() => {
    setAntennas(buildDefaultAntennas());
  }, []);

  // Recalculate CSI values whenever antenna state changes
  useEffect(() => {
    const txActive = antennas.filter((a) => a.type === 'tx' && a.active).length;
    const rxActive = antennas.filter((a) => a.type === 'rx' && a.active).length;

    if (txActive === 0 || rxActive === 0) {
      setAmplitude(0);
      setPhase(0);
      return;
    }

    const baseAmp = 0.3 + txActive * 0.1 + rxActive * 0.05;
    const phaseVariation = 0.5 + antennas.filter((a) => a.active).length * 0.1;

    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      setAmplitude(Math.min(0.95, baseAmp + (Math.random() * 0.1 - 0.05)));
      setPhase(0.5 + Math.random() * phaseVariation);
    }, 1000);

    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [antennas]);

  const txActive = antennas.filter((a) => a.type === 'tx' && a.active).length;
  const rxActive = antennas.filter((a) => a.type === 'rx' && a.active).length;
  const quality = calcSignalQuality(txActive, rxActive);

  // Group into rows for SVG grid
  const rows = [0, 1, 2];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-gray-500 uppercase tracking-wider">
          {deviceId ?? '선택된 노드 없음'} — 안테나 배열 (3×3)
        </p>
        <button
          onClick={resetAll}
          className="text-[10px] text-cyan-500 hover:text-cyan-300 transition-colors"
        >
          초기화
        </button>
      </div>

      {/* SVG antenna grid */}
      <svg
        viewBox="0 0 180 180"
        className="w-full max-w-[220px] mx-auto"
        aria-label="Antenna array visualization"
      >
        {/* Row labels */}
        <text x="4" y="34" fontSize="7" fill="#6b7280">TX</text>
        <text x="4" y="94" fontSize="7" fill="#6b7280">RX</text>
        <text x="4" y="154" fontSize="7" fill="#6b7280">RX</text>

        {rows.map((row) =>
          [0, 1, 2].map((col) => {
            const antenna = antennas.find((a) => a.row === row && a.col === col);
            if (!antenna) return null;
            const cx = 40 + col * 50;
            const cy = 30 + row * 60;
            const isTx = antenna.type === 'tx';
            const activeColor = isTx ? '#22d3ee' : '#a78bfa';
            const inactiveColor = '#374151';
            const glowColor = isTx ? '#22d3ee' : '#a78bfa';

            return (
              <g
                key={antenna.id}
                onClick={() => toggleAntenna(antenna.id)}
                style={{ cursor: 'pointer' }}
                role="button"
                aria-pressed={antenna.active}
                aria-label={`${antenna.id} ${antenna.active ? 'active' : 'inactive'}`}
              >
                {/* Glow ring when active */}
                {antenna.active && (
                  <circle
                    cx={cx}
                    cy={cy}
                    r="16"
                    fill="none"
                    stroke={glowColor}
                    strokeWidth="0.5"
                    opacity="0.3"
                  />
                )}
                {/* Main antenna body */}
                <rect
                  x={cx - 11}
                  y={cy - 11}
                  width="22"
                  height="22"
                  rx="4"
                  fill={antenna.active ? activeColor + '22' : '#1f2937'}
                  stroke={antenna.active ? activeColor : inactiveColor}
                  strokeWidth="1.5"
                />
                {/* Antenna mast symbol */}
                <line
                  x1={cx}
                  y1={cy - 5}
                  x2={cx}
                  y2={cy + 5}
                  stroke={antenna.active ? activeColor : '#4b5563'}
                  strokeWidth="1.5"
                />
                <line
                  x1={cx - 6}
                  y1={cy - 1}
                  x2={cx + 6}
                  y2={cy - 1}
                  stroke={antenna.active ? activeColor : '#4b5563'}
                  strokeWidth="1.5"
                />
                {/* Label */}
                <text
                  x={cx}
                  y={cy + 20}
                  textAnchor="middle"
                  fontSize="6"
                  fill={antenna.active ? '#9ca3af' : '#4b5563'}
                >
                  {isTx ? `T${col + 1}` : `R${(antenna.row - 1) * 3 + col + 1}`}
                </text>
              </g>
            );
          }),
        )}
      </svg>

      {/* Array status */}
      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="rounded bg-gray-800 px-2 py-1.5">
          <div className="text-[10px] text-gray-500">Active TX</div>
          <div className="text-sm font-bold text-cyan-400">{txActive} / 3</div>
        </div>
        <div className="rounded bg-gray-800 px-2 py-1.5">
          <div className="text-[10px] text-gray-500">Active RX</div>
          <div className="text-sm font-bold text-purple-400">{rxActive} / 6</div>
        </div>
        <div className="rounded bg-gray-800 px-2 py-1.5">
          <div className="text-[10px] text-gray-500">Quality</div>
          <div
            className={`text-sm font-bold ${
              quality >= 70 ? 'text-emerald-400' : quality >= 40 ? 'text-amber-400' : 'text-red-400'
            }`}
          >
            {quality}%
          </div>
        </div>
      </div>

      {/* CSI Amplitude / Phase */}
      <div className="space-y-2 pt-2 border-t border-gray-800">
        <p className="text-xs text-gray-500 uppercase tracking-wider">CSI 진폭 / 위상</p>
        <div className="space-y-2">
          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-gray-500">Amplitude</span>
              <span className="font-mono text-gray-300">{amplitude.toFixed(2)}</span>
            </div>
            <div className="h-2 rounded-full bg-gray-800 overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{ width: `${amplitude * 100}%`, background: '#22d3ee' }}
              />
            </div>
          </div>
          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-gray-500">Phase</span>
              <span className="font-mono text-gray-300">{phase.toFixed(1)}π</span>
            </div>
            <div className="h-2 rounded-full bg-gray-800 overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{ width: `${Math.min(100, phase * 50)}%`, background: '#a78bfa' }}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Channel Hopping Status
// ---------------------------------------------------------------------------

const CH_SEQUENCE = [1, 6, 11] as const;
const DWELL_MS = 50;

function ChannelHoppingStatus({ deviceOnline }: { deviceOnline: boolean }) {
  const [activeIdx, setActiveIdx] = useState(0);

  useEffect(() => {
    if (!deviceOnline) return;
    const id = setInterval(() => {
      setActiveIdx((prev) => (prev + 1) % CH_SEQUENCE.length);
    }, DWELL_MS);
    return () => clearInterval(id);
  }, [deviceOnline]);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-xs text-gray-500 uppercase tracking-wider">채널 호핑</p>
        <span className="text-[10px] text-gray-500 font-mono">{DWELL_MS}ms dwell</span>
      </div>
      <div className="flex gap-2">
        {CH_SEQUENCE.map((ch, i) => {
          const isActive = deviceOnline && i === activeIdx;
          return (
            <div
              key={ch}
              className={`flex-1 rounded border text-center py-2 transition-all duration-75 ${
                isActive
                  ? 'border-cyan-500 bg-cyan-500/20 text-cyan-300'
                  : 'border-gray-700 bg-gray-800 text-gray-500'
              }`}
            >
              <div className="text-xs font-bold">CH {ch}</div>
              <div className="text-[10px]">{ch === 1 ? '2.412' : ch === 6 ? '2.437' : '2.462'} GHz</div>
              {isActive && (
                <div className="mt-1 flex justify-center">
                  <span
                    className="inline-block w-1.5 h-1.5 rounded-full bg-cyan-400"
                    style={{ boxShadow: '0 0 5px #22d3ee' }}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
      {!deviceOnline && (
        <p className="text-[10px] text-gray-600 text-center">디바이스 오프라인 — 호핑 중지</p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Device Hardware Card
// ---------------------------------------------------------------------------

function DeviceHardwareCard({
  device,
  zoneName,
  isSelected,
  onSelect,
}: {
  device: Device;
  zoneName: string;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const isOnline = device.status === 'online';

  return (
    <Card
      className={`cursor-pointer transition-all ${
        isSelected ? 'border-cyan-700 shadow-lg shadow-cyan-500/10' : 'hover:border-gray-700'
      }`}
      onClick={onSelect}
    >
      <CardHeader>
        <div className="flex items-center gap-2">
          <span
            className={`inline-block h-2.5 w-2.5 rounded-full ${
              isOnline ? 'bg-emerald-400' : 'bg-gray-500'
            }`}
          />
          <span className="text-sm font-medium text-gray-100">{device.name}</span>
          <span
            className={`ml-auto text-[10px] px-1.5 py-0.5 rounded-full ${
              isOnline
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
            <span className="text-xs font-mono text-gray-300">{device.mac}</span>
          </div>

          {/* RSSI */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-gray-500">RSSI</span>
              <span className="text-xs text-gray-300">{rssiLabel(device.signalStrength)}</span>
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
            <span className="text-xs font-mono text-gray-300">{device.firmwareVersion}</span>
          </div>

          {/* Hardware Specs */}
          {device.model && (
            <div className="pt-1 border-t border-gray-800 space-y-2">
              <span className="text-[10px] uppercase tracking-wider text-gray-600">하드웨어</span>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">모델</span>
                <span className="text-xs font-mono text-cyan-400">{device.model}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">칩</span>
                <span className="text-xs font-mono text-gray-300">{device.chipType}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">Flash</span>
                <span className="text-xs font-mono text-gray-300">{device.flashSize}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">PSRAM</span>
                <span className="text-xs font-mono text-gray-300">{device.psramSize}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">ESP-IDF</span>
                <span className="text-xs font-mono text-gray-300">{device.idfVersion}</span>
              </div>
            </div>
          )}

          {/* Position mini-map */}
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
            <span className="text-xs text-gray-400">{formatLastSeen(device.lastSeen)}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function HardwarePage() {
  const devices = useDeviceStore((s) => s.devices);
  const selectedId = useDeviceStore((s) => s.selectedId);
  const selectDevice = useDeviceStore((s) => s.selectDevice);
  const zones = useZoneStore((s) => s.zones);

  const zoneMap = new Map(zones.map((z) => [z.id, z.name]));

  const selectedDevice = devices.find((d) => d.id === selectedId) ?? null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-100">하드웨어</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          디바이스 하드웨어 상태 모니터링 — 안테나 배열 · CSI · 채널 호핑
        </p>
      </div>

      {/* Antenna + CSI panel for selected device */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Antenna Array */}
        <Card variant="glow">
          <CardHeader>안테나 배열 시각화</CardHeader>
          <CardContent>
            <AntennaArrayPanel deviceId={selectedDevice?.name ?? null} />
          </CardContent>
        </Card>

        {/* Channel Hopping */}
        <Card>
          <CardHeader>채널 호핑 상태</CardHeader>
          <CardContent>
            <ChannelHoppingStatus deviceOnline={selectedDevice != null && selectedDevice.status === 'online'} />

            {/* Hint when no device selected */}
            {!selectedDevice && (
              <p className="mt-4 text-[11px] text-gray-600 text-center">
                아래 목록에서 디바이스를 선택하면 해당 노드의 채널 호핑을 표시합니다.
              </p>
            )}

            {selectedDevice && (
              <div className="mt-4 pt-4 border-t border-gray-800 space-y-1.5">
                <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">선택된 노드</p>
                <div className="flex items-center gap-2">
                  <span
                    className={`inline-block w-2 h-2 rounded-full ${
                      selectedDevice.status === 'online' ? 'bg-emerald-400' : 'bg-gray-500'
                    }`}
                  />
                  <span className="text-xs text-gray-200 font-medium">{selectedDevice.name}</span>
                  <span className="text-xs font-mono text-gray-500 ml-auto">{selectedDevice.mac}</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-gray-500">모션 에너지</span>
                  <span className="font-mono text-gray-300">{(selectedDevice.motion_energy ?? 0).toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-gray-500">호흡 BPM</span>
                  <span className="font-mono text-gray-300">
                    {selectedDevice.csi_breathing_bpm ?? selectedDevice.breathing_bpm ?? '--'}
                  </span>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Device list */}
      {devices.length === 0 ? (
        <Card>
          <CardContent>
            <p className="text-xs text-gray-500">등록된 디바이스가 없습니다.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {devices.map((device) => {
            const zoneName = device.zone_id
              ? zoneMap.get(device.zone_id) ?? device.zone_id
              : '미할당';
            return (
              <DeviceHardwareCard
                key={device.id}
                device={device}
                zoneName={zoneName}
                isSelected={device.id === selectedId}
                onSelect={() => selectDevice(device.id === selectedId ? null : device.id)}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
