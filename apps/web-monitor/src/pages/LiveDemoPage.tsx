import { useEffect, useState, useRef, useCallback } from 'react';
import { Card, CardHeader, CardContent } from '@/components/ui/Card';
import { useDeviceStore } from '@/stores/deviceStore';

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
      <span className="text-[10px] text-gray-500 w-8 text-right">{pct}%</span>
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
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] uppercase tracking-wider text-gray-500">{source}</span>
        <span className="text-[10px] text-gray-600">{label}</span>
      </div>
      <div className="text-center mb-2">
        <span className={`text-lg font-semibold ${poseColors[pose]}`}>
          {poseLabels[pose]}
        </span>
      </div>
      <ConfBar value={confidence} />
    </div>
  );
}

export default function LiveDemoPage() {
  const devices = useDeviceStore((s) => s.devices);
  const [cameraDetections, setCameraDetections] = useState<CameraDetection[]>([]);
  const [cameraTimestamp, setCameraTimestamp] = useState<number>(0);
  const [csiTimestamp, setCsiTimestamp] = useState<number>(Date.now());

  // Track agreement history per device for rolling agreement %
  const agreementHistoryRef = useRef<Map<string, boolean[]>>(new Map());

  // Fetch camera detections periodically
  useEffect(() => {
    let cancelled = false;

    const fetchDetections = async () => {
      try {
        const res = await fetch('/cam/health', { signal: AbortSignal.timeout(3000) });
        if (res.ok) {
          const data = await res.json();
          // Camera is available - try to get detection data
          const ts = Date.now();
          setCameraTimestamp(ts);

          // Attempt to get the latest detections from the camera WS or fallback
          // In a real setup, this would come from a WebSocket; for now we use
          // the health endpoint person_count as a proxy
          const count = data.person_count ?? 0;
          const mockDets: CameraDetection[] = [];
          for (let i = 0; i < count; i++) {
            mockDets.push({
              pose: 'standing', // camera-derived pose will come from real detections
              confidence: 0.7,
            });
          }
          if (!cancelled) setCameraDetections(mockDets);
        }
      } catch {
        // Camera not available
        if (!cancelled) setCameraDetections([]);
      }
    };

    fetchDetections();
    const id = setInterval(fetchDetections, 2000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  // Update CSI timestamp when devices change
  useEffect(() => {
    if (devices.length > 0) {
      setCsiTimestamp(Date.now());
    }
  }, [devices]);

  // Build comparison data
  const comparisons: DevicePoseComparison[] = devices.map((dev) => {
    const csiPose = poseFromEnergy(dev.motion_energy);
    const csiConf = poseConfidence(dev.motion_energy);

    // Try to find a matching camera detection for this device
    // In a real multi-camera setup, we'd match by floor position
    const camDet = cameraDetections.length > 0 ? cameraDetections[0] : null;
    const cameraPose: PoseLabel = camDet?.pose ?? 'unknown';
    const cameraConf = camDet?.confidence ?? 0;

    const agreement = csiPose === cameraPose || cameraPose === 'unknown';

    // Update agreement history
    const history = agreementHistoryRef.current.get(dev.id) ?? [];
    const updatedHistory = [...history, agreement].slice(-20);
    agreementHistoryRef.current.set(dev.id, updatedHistory);

    const agreementPct =
      updatedHistory.length > 0
        ? (updatedHistory.filter(Boolean).length / updatedHistory.length) * 100
        : 0;

    const latencyDiffMs = Math.abs(csiTimestamp - cameraTimestamp);

    return {
      deviceId: dev.id,
      deviceName: dev.name,
      csiPose,
      csiConfidence: csiConf,
      cameraPose,
      cameraConfidence: cameraConf,
      agreement,
      agreementPct: Math.round(agreementPct),
      latencyDiffMs,
    };
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-100">
          라이브 데모
        </h1>
        <p className="text-sm text-gray-500 mt-0.5">
          Signal-Derived vs Camera 포즈 추정 A/B 비교
        </p>
      </div>

      {/* A/B Split View */}
      <div className="grid grid-cols-12 gap-6">
        {/* Left: Signal-Derived (CSI) Pose */}
        <div className="col-span-12 lg:col-span-6">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-cyan-500 animate-pulse" />
                <span>Signal-Derived 포즈</span>
              </div>
            </CardHeader>
            <CardContent>
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
                    cameraDetections.length > 0 ? 'bg-emerald-500 animate-pulse' : 'bg-gray-600'
                  }`}
                />
                <span>Camera 포즈</span>
              </div>
            </CardHeader>
            <CardContent>
              {cameraDetections.length === 0 ? (
                <div className="text-center py-8">
                  <p className="text-xs text-gray-500 mb-1">카메라 감지 없음</p>
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

      {/* Bottom: Side-by-side comparison table */}
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
                    <th className="pb-2 text-xs font-medium text-gray-500">디바이스</th>
                    <th className="pb-2 text-xs font-medium text-gray-500">CSI 포즈</th>
                    <th className="pb-2 text-xs font-medium text-gray-500">CSI 신뢰도</th>
                    <th className="pb-2 text-xs font-medium text-gray-500">Camera 포즈</th>
                    <th className="pb-2 text-xs font-medium text-gray-500">Camera 신뢰도</th>
                    <th className="pb-2 text-xs font-medium text-gray-500">일치</th>
                    <th className="pb-2 text-xs font-medium text-gray-500">일치율</th>
                    <th className="pb-2 text-xs font-medium text-gray-500">지연차 (ms)</th>
                  </tr>
                </thead>
                <tbody>
                  {comparisons.map((cmp) => (
                    <tr key={cmp.deviceId} className="border-b border-gray-800/50">
                      <td className="py-2 text-gray-200">{cmp.deviceName}</td>
                      <td className="py-2">
                        <span className={poseColors[cmp.csiPose]}>
                          {poseLabels[cmp.csiPose]}
                        </span>
                      </td>
                      <td className="py-2">
                        <ConfBar value={cmp.csiConfidence} />
                      </td>
                      <td className="py-2">
                        <span className={poseColors[cmp.cameraPose]}>
                          {poseLabels[cmp.cameraPose]}
                        </span>
                      </td>
                      <td className="py-2">
                        <ConfBar value={cmp.cameraConfidence} />
                      </td>
                      <td className="py-2">
                        <span
                          className={`text-[10px] px-1.5 py-0.5 rounded-full ${
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
