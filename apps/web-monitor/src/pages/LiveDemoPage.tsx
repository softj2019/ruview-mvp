/**
 * LiveDemoPage — Phase 2-9
 * Signal-Derived vs Camera 포즈 A/B 비교 + WebSocket 실시간 연결
 * 참조: ruvnet-RuView/ui/components/LiveDemoTab.js
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { useDeviceStore } from '@/stores/deviceStore';
import { useWebSocket } from '@/hooks/useWebSocket';
import PoseDetectionCanvas, { type Person } from '@/components/camera/PoseDetectionCanvas';

// ─── Types ───────────────────────────────────────────────────────────────────

type PoseLabel = 'sitting' | 'standing' | 'walking' | 'fallen' | 'lying' | 'unknown';

interface CameraDetection {
  pose: PoseLabel;
  confidence: number;
  bbox?: number[];
  floor_pos?: { x: number; y: number };
}

interface DevicePoseComparison {
  deviceId: string;
  deviceName: string;
  csiPose: PoseLabel;
  csiConfidence: number;
  cameraPose: PoseLabel;
  cameraConfidence: number;
  agreement: boolean;
  agreementPct: number;
  latencyDiffMs: number;
}

type ConnState = 'disconnected' | 'connecting' | 'connected' | 'error';

// ─── Constants ───────────────────────────────────────────────────────────────

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8001/ws/events';

const poseColors: Record<PoseLabel, string> = {
  sitting: 'text-blue-400',
  standing: 'text-emerald-400',
  walking: 'text-amber-400',
  fallen: 'text-red-400',
  lying: 'text-red-400',
  unknown: 'text-gray-500',
};

const poseLabels: Record<PoseLabel, string> = {
  sitting: '앉음',
  standing: '서있음',
  walking: '걷는중',
  fallen: '넘어짐',
  lying: '누워있음',
  unknown: '미감지',
};

const poseBg: Record<PoseLabel, string> = {
  sitting: 'bg-blue-500/10 border-blue-500/30',
  standing: 'bg-emerald-500/10 border-emerald-500/30',
  walking: 'bg-amber-500/10 border-amber-500/30',
  fallen: 'bg-red-500/10 border-red-500/30',
  lying: 'bg-red-500/10 border-red-500/30',
  unknown: 'bg-gray-500/10 border-gray-500/30',
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

function poseFromEnergy(energy: number | undefined): PoseLabel {
  if (energy == null) return 'unknown';
  if (energy > 8.0) return 'fallen';
  if (energy > 3.0) return 'walking';
  if (energy > 0.5) return 'standing';
  return 'sitting';
}

function poseConfidence(energy: number | undefined): number {
  if (energy == null) return 0;
  return Math.min(1, 0.4 + energy * 0.6);
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function ConfBar({ value, className }: { value: number; className?: string }) {
  const pct = Math.round(value * 100);
  const barColor =
    pct >= 80 ? 'bg-emerald-500' : pct >= 50 ? 'bg-amber-500' : 'bg-red-500';
  return (
    <div className={`flex items-center gap-2 ${className ?? ''}`}>
      <div className="h-1.5 flex-1 rounded-full bg-gray-800">
        <div
          className={`h-full rounded-full transition-all duration-300 ${barColor}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-8 text-right text-[10px] text-gray-500">{pct}%</span>
    </div>
  );
}

function PoseCard({
  label,
  pose,
  confidence,
  source,
}: {
  label: string;
  pose: PoseLabel;
  confidence: number;
  source: string;
}) {
  return (
    <div className={`rounded-lg border p-3 ${poseBg[pose]}`}>
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-wider text-gray-500">{source}</span>
        <span className="text-[10px] text-gray-600">{label}</span>
      </div>
      <div className="mb-2 text-center">
        <span className={`text-lg font-semibold ${poseColors[pose]}`}>
          {poseLabels[pose]}
        </span>
      </div>
      <ConfBar value={confidence} />
    </div>
  );
}

function ConnStateIndicator({ state }: { state: ConnState }) {
  const map: Record<ConnState, { dot: string; label: string; badge: 'success' | 'warning' | 'danger' | 'default' }> = {
    connected: { dot: 'bg-emerald-500 animate-pulse', label: 'Connected', badge: 'success' },
    connecting: { dot: 'bg-amber-500 animate-pulse', label: 'Connecting...', badge: 'warning' },
    disconnected: { dot: 'bg-gray-600', label: 'Disconnected', badge: 'default' },
    error: { dot: 'bg-red-500', label: 'Error', badge: 'danger' },
  };
  const { dot, label, badge } = map[state];
  return (
    <Badge variant={badge}>
      <span className={`mr-1.5 inline-block h-1.5 w-1.5 rounded-full ${dot}`} />
      {label}
    </Badge>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function LiveDemoPage() {
  const devices = useDeviceStore((s) => s.devices);
  const [cameraDetections, setCameraDetections] = useState<CameraDetection[]>([]);
  const [cameraTimestamp, setCameraTimestamp] = useState<number>(0);
  const [csiTimestamp, setCsiTimestamp] = useState<number>(Date.now());
  const [connState, setConnState] = useState<ConnState>('disconnected');
  const [frameCount, setFrameCount] = useState(0);
  const [csiPersons, setCsiPersons] = useState<Person[]>([]);
  const [debugMode, setDebugMode] = useState(false);
  const agreementHistoryRef = useRef<Map<string, boolean[]>>(new Map());

  // ── WebSocket ────────────────────────────────────────────────────────────

  const handleWsMessage = useCallback((data: unknown) => {
    if (typeof data !== 'object' || data === null) return;
    const msg = data as Record<string, unknown>;

    // Device/CSI update events
    if (msg.type === 'device_update' || msg.type === 'csi_frame') {
      setFrameCount((n) => n + 1);
      setCsiTimestamp(Date.now());

      // Build synthetic Person list from device data for PoseDetectionCanvas
      if (Array.isArray(msg.devices)) {
        const persons: Person[] = (msg.devices as Array<Record<string, unknown>>)
          .filter((d) => d.motion_energy != null)
          .map((d, i) => ({
            id: String(d.id ?? i),
            pose: poseFromEnergy(d.motion_energy as number | undefined),
            confidence: poseConfidence(d.motion_energy as number | undefined),
            keypoints: generatePlaceholderKeypoints(),
          }));
        setCsiPersons(persons);
      }
    }

    // Camera detections embedded in WS message
    if (Array.isArray(msg.camera_detections)) {
      const dets = (msg.camera_detections as Array<Record<string, unknown>>).map((d) => ({
        pose: (typeof d.pose === 'string' ? d.pose : 'unknown') as PoseLabel,
        confidence: typeof d.confidence === 'number' ? d.confidence : 0,
        bbox: Array.isArray(d.bbox) ? (d.bbox as number[]) : undefined,
        floor_pos:
          d.floor_pos != null
            ? (d.floor_pos as { x: number; y: number })
            : undefined,
      }));
      setCameraDetections(dets);
      setCameraTimestamp(Date.now());
    }
  }, []);

  useWebSocket({
    url: WS_URL,
    onMessage: handleWsMessage,
    onOpen: () => setConnState('connected'),
    onClose: () => setConnState('disconnected'),
    onError: () => setConnState('error'),
    reconnectInterval: 3000,
    maxReconnectAttempts: 10,
  });

  useEffect(() => {
    setConnState('connecting');
  }, []);

  // ── Camera polling (fallback REST) ────────────────────────────────────────

  useEffect(() => {
    let cancelled = false;

    const fetchDetections = async () => {
      try {
        const res = await fetch('/cam/health', { signal: AbortSignal.timeout(3000) });
        if (res.ok) {
          const data = (await res.json()) as Record<string, unknown>;
          const count = (data.person_count as number | undefined) ?? 0;
          const rawDetections: unknown[] = Array.isArray(data.detections) ? data.detections : [];
          const dets: CameraDetection[] = Array.from({ length: count }, (_, i) => {
            const det = rawDetections[i];
            const hasDet = det != null && typeof det === 'object';
            return {
              pose: (hasDet && typeof (det as Record<string, unknown>).pose === 'string'
                ? (det as Record<string, unknown>).pose as PoseLabel
                : 'unknown'),
              confidence: (hasDet && typeof (det as Record<string, unknown>).confidence === 'number'
                ? (det as Record<string, unknown>).confidence as number
                : 0),
              bbox: hasDet && Array.isArray((det as Record<string, unknown>).bbox)
                ? (det as Record<string, unknown>).bbox as number[]
                : undefined,
              floor_pos: hasDet && (det as Record<string, unknown>).floor_pos != null
                ? (det as Record<string, unknown>).floor_pos as { x: number; y: number }
                : undefined,
            };
          });
          if (!cancelled) {
            setCameraDetections(dets);
            setCameraTimestamp(Date.now());
          }
        }
      } catch {
        if (!cancelled) setCameraDetections([]);
      }
    };

    fetchDetections();
    const id = setInterval(fetchDetections, 2000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  // ── CSI timestamp from device store ──────────────────────────────────────

  useEffect(() => {
    if (devices.length > 0) setCsiTimestamp(Date.now());
  }, [devices]);

  // ── Comparison table ─────────────────────────────────────────────────────

  const comparisons: DevicePoseComparison[] = devices.map((dev) => {
    const csiPose = poseFromEnergy(dev.motion_energy);
    const csiConf = poseConfidence(dev.motion_energy);
    const camDet = cameraDetections.length > 0 ? cameraDetections[0] : null;
    const cameraPose: PoseLabel = camDet?.pose ?? 'unknown';
    const cameraConf = camDet?.confidence ?? 0;
    const agreement = csiPose === cameraPose || cameraPose === 'unknown';
    const history = agreementHistoryRef.current.get(dev.id) ?? [];
    const updatedHistory = [...history, agreement].slice(-20);
    agreementHistoryRef.current.set(dev.id, updatedHistory);
    const agreementPct =
      updatedHistory.length > 0
        ? (updatedHistory.filter(Boolean).length / updatedHistory.length) * 100
        : 0;
    return {
      deviceId: dev.id,
      deviceName: dev.name,
      csiPose,
      csiConfidence: csiConf,
      cameraPose,
      cameraConfidence: cameraConf,
      agreement,
      agreementPct: Math.round(agreementPct),
      latencyDiffMs: Math.abs(csiTimestamp - cameraTimestamp),
    };
  });

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-100">라이브 데모</h1>
          <p className="mt-0.5 text-sm text-gray-500">
            Signal-Derived vs Camera 포즈 추정 A/B 비교
          </p>
        </div>
        <div className="flex items-center gap-3">
          <ConnStateIndicator state={connState} />
          {debugMode && (
            <span className="text-[10px] text-gray-600">
              Frames: {frameCount}
            </span>
          )}
          <button
            onClick={() => setDebugMode((v) => !v)}
            className={`rounded border px-2.5 py-1 text-xs transition-colors ${
              debugMode
                ? 'border-cyan-700 bg-cyan-500/10 text-cyan-400'
                : 'border-gray-800 bg-gray-900 text-gray-500 hover:border-gray-700'
            }`}
          >
            Debug
          </button>
        </div>
      </div>

      {/* A/B Split View */}
      <div className="grid grid-cols-12 gap-6">
        {/* Left: Signal-Derived (CSI) Pose */}
        <div className="col-span-12 lg:col-span-6">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 animate-pulse rounded-full bg-cyan-500" />
                <span>Signal-Derived 포즈</span>
              </div>
            </CardHeader>
            <CardContent>
              {/* PoseDetectionCanvas: CSI 기반 스켈레톤 렌더링 */}
              {csiPersons.length > 0 && (
                <div className="mb-4 overflow-hidden rounded-lg border border-gray-800 bg-black">
                  <PoseDetectionCanvas
                    persons={csiPersons}
                    width={480}
                    height={320}
                    showTrail={debugMode}
                  />
                </div>
              )}
              {devices.length === 0 ? (
                <p className="text-xs text-gray-500">디바이스 데이터 없음</p>
              ) : (
                <div className="space-y-3">
                  {devices.map((dev) => {
                    const pose = poseFromEnergy(dev.motion_energy);
                    const conf = poseConfidence(dev.motion_energy);
                    return (
                      <PoseCard
                        key={dev.id}
                        label={dev.name}
                        pose={pose}
                        confidence={conf}
                        source="CSI"
                      />
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right: Camera-Derived Pose */}
        <div className="col-span-12 lg:col-span-6">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <div
                  className={`h-2 w-2 rounded-full ${
                    cameraDetections.length > 0 ? 'animate-pulse bg-emerald-500' : 'bg-gray-600'
                  }`}
                />
                <span>Camera 포즈</span>
              </div>
            </CardHeader>
            <CardContent>
              {cameraDetections.length === 0 ? (
                <div className="py-8 text-center">
                  <p className="mb-1 text-xs text-gray-500">카메라 감지 없음</p>
                  <p className="text-[10px] text-gray-600">
                    카메라 서비스가 실행 중이 아니거나 인원이 감지되지 않았습니다
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {cameraDetections.map((det, idx) => (
                    <PoseCard
                      key={idx}
                      label={`Person ${idx + 1}`}
                      pose={det.pose}
                      confidence={det.confidence}
                      source="Camera"
                    />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Debug info */}
      {debugMode && (
        <Card>
          <CardHeader>Debug Info</CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-3 text-xs text-gray-500">
              <div>
                <div className="text-[10px] uppercase text-gray-700">WS URL</div>
                <code className="text-gray-400">{WS_URL}</code>
              </div>
              <div>
                <div className="text-[10px] uppercase text-gray-700">Frames</div>
                <span className="text-gray-300">{frameCount}</span>
              </div>
              <div>
                <div className="text-[10px] uppercase text-gray-700">Devices</div>
                <span className="text-gray-300">{devices.length}</span>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Bottom: Comparison table */}
      <Card>
        <CardHeader>비교 테이블</CardHeader>
        <CardContent>
          {comparisons.length === 0 ? (
            <p className="text-xs text-gray-500">디바이스 데이터 없음</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-800 text-left">
                    {[
                      '디바이스', 'CSI 포즈', 'CSI 신뢰도',
                      'Camera 포즈', 'Camera 신뢰도', '일치', '일치율', '지연차 (ms)',
                    ].map((h) => (
                      <th key={h} className="pb-2 text-xs font-medium text-gray-500">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {comparisons.map((cmp) => (
                    <tr key={cmp.deviceId} className="border-b border-gray-800/50">
                      <td className="py-2 text-gray-200">{cmp.deviceName}</td>
                      <td className="py-2">
                        <span className={poseColors[cmp.csiPose]}>{poseLabels[cmp.csiPose]}</span>
                      </td>
                      <td className="py-2">
                        <ConfBar value={cmp.csiConfidence} />
                      </td>
                      <td className="py-2">
                        <span className={poseColors[cmp.cameraPose]}>{poseLabels[cmp.cameraPose]}</span>
                      </td>
                      <td className="py-2">
                        <ConfBar value={cmp.cameraConfidence} />
                      </td>
                      <td className="py-2">
                        <span
                          className={`rounded-full px-1.5 py-0.5 text-[10px] ${
                            cmp.agreement
                              ? 'bg-emerald-500/20 text-emerald-400'
                              : 'bg-red-500/20 text-red-400'
                          }`}
                        >
                          {cmp.agreement ? 'Y' : 'N'}
                        </span>
                      </td>
                      <td className="py-2">
                        <span
                          className={`text-xs ${
                            cmp.agreementPct >= 80
                              ? 'text-emerald-400'
                              : cmp.agreementPct >= 50
                                ? 'text-amber-400'
                                : 'text-red-400'
                          }`}
                        >
                          {cmp.agreementPct}%
                        </span>
                      </td>
                      <td className="py-2 text-xs text-gray-400">
                        {cmp.latencyDiffMs < 1000
                          ? `${cmp.latencyDiffMs}ms`
                          : `${(cmp.latencyDiffMs / 1000).toFixed(1)}s`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ─── Helpers (private) ────────────────────────────────────────────────────────

/** CSI 신호로부터 COCO-17 keypoint placeholder 생성 (시각화용) */
function generatePlaceholderKeypoints(): Person['keypoints'] {
  // 중심(0.5, 0.5) 주변에 서 있는 사람 형태의 기본값
  const pts: [number, number][] = [
    [0.5, 0.15],  // 코
    [0.48, 0.13], [0.52, 0.13], // 눈
    [0.46, 0.14], [0.54, 0.14], // 귀
    [0.42, 0.28], [0.58, 0.28], // 어깨
    [0.38, 0.42], [0.62, 0.42], // 팔꿈치
    [0.36, 0.55], [0.64, 0.55], // 손목
    [0.44, 0.58], [0.56, 0.58], // 엉덩이
    [0.43, 0.75], [0.57, 0.75], // 무릎
    [0.43, 0.90], [0.57, 0.90], // 발목
  ];
  return pts.map(([x, y]) => ({ x, y, confidence: 0.6 }));
}
