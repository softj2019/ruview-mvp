import { useEffect, useState, useRef, useCallback } from 'react';
import { AreaChart, Area, ResponsiveContainer } from 'recharts';
import { Card, CardHeader, CardContent } from '@/components/ui/Card';
import { useDeviceStore } from '@/stores/deviceStore';

type PoseLabel = 'sitting' | 'standing' | 'walking' | 'fallen' | 'unknown';

interface CameraState {
  imgSrc: string | null;
  personCount: number;
  pose: PoseLabel;
  confidence: number;
}

function poseFromEnergy(energy: number | undefined): PoseLabel {
  if (energy == null) return 'unknown';
  if (energy < 0.2) return 'sitting';
  if (energy < 0.6) return 'standing';
  return 'walking';
}

function poseConfidence(energy: number | undefined): number {
  if (energy == null) return 0;
  // Higher energy = more confident detection
  return Math.min(1, 0.4 + energy * 0.6);
}

const poseColors: Record<PoseLabel, string> = {
  sitting: 'text-blue-400',
  standing: 'text-emerald-400',
  walking: 'text-amber-400',
  fallen: 'text-red-400',
  unknown: 'text-gray-500',
};

const poseLabels: Record<PoseLabel, string> = {
  sitting: '앉음',
  standing: '서있음',
  walking: '걷는중',
  fallen: '넘어짐',
  unknown: '미감지',
};

const poseBgColors: Record<PoseLabel, string> = {
  sitting: 'bg-blue-500',
  standing: 'bg-emerald-500',
  walking: 'bg-yellow-500',
  fallen: 'bg-red-500',
  unknown: 'bg-gray-600',
};

interface PoseTrailEntry {
  pose: PoseLabel;
  timestamp: number;
}

interface ConfidenceEntry {
  value: number;
}

function PoseTrailBar({ trail }: { trail: PoseTrailEntry[] }) {
  if (trail.length === 0) return null;
  return (
    <div className="flex items-center gap-0.5 mt-1.5">
      {trail.map((entry, i) => (
        <div
          key={i}
          className={`h-2 flex-1 rounded-sm ${poseBgColors[entry.pose]}`}
          title={`${poseLabels[entry.pose]}`}
        />
      ))}
    </div>
  );
}

function ConfidenceSparkline({ data }: { data: ConfidenceEntry[] }) {
  if (data.length < 2) return null;
  return (
    <div className="mt-1.5" style={{ width: 100, height: 24 }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
          <Area
            type="monotone"
            dataKey="value"
            stroke="#22d3ee"
            fill="#22d3ee"
            fillOpacity={0.15}
            strokeWidth={1}
            dot={false}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function ConfidenceBar({ value, className }: { value: number; className?: string }) {
  return (
    <div className={`h-1.5 w-full rounded-full bg-gray-800 ${className ?? ''}`}>
      <div
        className="h-full rounded-full bg-cyan-500 transition-all duration-300"
        style={{ width: `${Math.round(value * 100)}%` }}
      />
    </div>
  );
}

function EnergyIndicator({ energy }: { energy: number | undefined }) {
  const level = energy ?? 0;
  const bars = 5;
  const filled = Math.round(level * bars);
  return (
    <div className="flex items-end gap-0.5 h-4">
      {Array.from({ length: bars }, (_, i) => (
        <div
          key={i}
          className={`w-1 rounded-sm transition-colors ${
            i < filled ? 'bg-cyan-400' : 'bg-gray-700'
          }`}
          style={{ height: `${((i + 1) / bars) * 100}%` }}
        />
      ))}
    </div>
  );
}

export default function PoseFusionPage() {
  const devices = useDeviceStore((s) => s.devices);

  const [camera, setCamera] = useState<CameraState>({
    imgSrc: null,
    personCount: 0,
    pose: 'unknown',
    confidence: 0,
  });

  // Pose trail: last 10 pose changes per device
  const poseTrailRef = useRef<Map<string, PoseTrailEntry[]>>(new Map());
  const [poseTrails, setPoseTrails] = useState<Map<string, PoseTrailEntry[]>>(new Map());

  // Confidence trend: last 20 values per device
  const confTrendRef = useRef<Map<string, ConfidenceEntry[]>>(new Map());
  const [confTrends, setConfTrends] = useState<Map<string, ConfidenceEntry[]>>(new Map());

  // Track pose changes and confidence for each device
  const prevPosesRef = useRef<Map<string, PoseLabel>>(new Map());

  const updateTrails = useCallback(() => {
    let trailChanged = false;
    let confChanged = false;

    for (const device of devices) {
      const pose = poseFromEnergy(device.motion_energy);
      const conf = poseConfidence(device.motion_energy);
      const prevPose = prevPosesRef.current.get(device.id);

      // Pose trail: only add on change
      if (prevPose !== pose) {
        prevPosesRef.current.set(device.id, pose);
        const trail = poseTrailRef.current.get(device.id) ?? [];
        const updated = [...trail, { pose, timestamp: Date.now() }].slice(-10);
        poseTrailRef.current.set(device.id, updated);
        trailChanged = true;
      }

      // Confidence trend: add every tick
      const trend = confTrendRef.current.get(device.id) ?? [];
      const updatedTrend = [...trend, { value: conf }].slice(-20);
      confTrendRef.current.set(device.id, updatedTrend);
      confChanged = true;
    }

    if (trailChanged) setPoseTrails(new Map(poseTrailRef.current));
    if (confChanged) setConfTrends(new Map(confTrendRef.current));
  }, [devices]);

  useEffect(() => {
    updateTrails();
  }, [updateTrails]);

  // Refresh camera snapshot every 2 seconds
  useEffect(() => {
    let cancelled = false;

    const refresh = async () => {
      try {
        const res = await fetch('/cam/snapshot', { signal: AbortSignal.timeout(5000) });
        if (!res.ok) throw new Error('snapshot failed');
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);

        // Try to get person count / pose from header or separate endpoint
        let personCount = 0;
        let pose: PoseLabel = 'unknown';
        let confidence = 0;

        const countHeader = res.headers.get('X-Person-Count');
        if (countHeader) personCount = parseInt(countHeader, 10) || 0;

        try {
          const detectRes = await fetch('/cam/detect', { signal: AbortSignal.timeout(3000) });
          if (detectRes.ok) {
            const detectData = await detectRes.json();
            personCount = detectData.person_count ?? personCount;
            pose = detectData.pose ?? 'unknown';
            confidence = detectData.confidence ?? 0;
          }
        } catch {
          /* detection endpoint optional */
        }

        if (!cancelled) {
          setCamera((prev) => {
            if (prev.imgSrc) URL.revokeObjectURL(prev.imgSrc);
            return { imgSrc: url, personCount, pose, confidence };
          });
        } else {
          URL.revokeObjectURL(url);
        }
      } catch {
        if (!cancelled) {
          setCamera((prev) => ({ ...prev, imgSrc: null }));
        }
      }
    };

    refresh();
    const id = setInterval(refresh, 2000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  // Cleanup blob URL on unmount
  useEffect(() => {
    return () => {
      setCamera((prev) => {
        if (prev.imgSrc) URL.revokeObjectURL(prev.imgSrc);
        return prev;
      });
    };
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-100">포즈 융합</h1>
        <p className="text-sm text-gray-500 mt-0.5">CSI + Camera 포즈 데이터 융합 뷰</p>
      </div>

      {/* Split view */}
      <div className="grid grid-cols-12 gap-6">
        {/* Left: CSI Data */}
        <div className="col-span-12 lg:col-span-6">
          <Card>
            <CardHeader>CSI 포즈 데이터</CardHeader>
            <CardContent>
              {devices.length === 0 ? (
                <p className="text-xs text-gray-500">디바이스 데이터 없음</p>
              ) : (
                <div className="space-y-3">
                  {devices.map((device) => {
                    const pose = poseFromEnergy(device.motion_energy);
                    const conf = poseConfidence(device.motion_energy);
                    return (
                      <div
                        key={device.id}
                        className="rounded-lg border border-gray-800 bg-gray-900/50 p-3"
                      >
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-gray-200">
                              {device.name}
                            </span>
                            <span
                              className={`text-xs ${
                                device.status === 'online' ? 'text-emerald-400' : 'text-gray-500'
                              }`}
                            >
                              {device.status}
                            </span>
                          </div>
                          <EnergyIndicator energy={device.motion_energy} />
                        </div>

                        <div className="flex items-center justify-between mb-1.5">
                          <span className="text-xs text-gray-500">포즈</span>
                          <span className={`text-xs font-medium ${poseColors[pose]}`}>
                            {poseLabels[pose]}
                          </span>
                        </div>

                        <div className="flex items-center gap-2">
                          <span className="text-[10px] text-gray-600 shrink-0">신뢰도</span>
                          <ConfidenceBar value={conf} />
                          <span className="text-[10px] text-gray-500 shrink-0 w-8 text-right">
                            {Math.round(conf * 100)}%
                          </span>
                        </div>

                        {/* Pose Trail */}
                        {(poseTrails.get(device.id)?.length ?? 0) > 0 && (
                          <div>
                            <span className="text-[10px] text-gray-600">포즈 변화</span>
                            <PoseTrailBar trail={poseTrails.get(device.id)!} />
                          </div>
                        )}

                        {/* Confidence Sparkline */}
                        {(confTrends.get(device.id)?.length ?? 0) >= 2 && (
                          <div className="flex items-center gap-2">
                            <span className="text-[10px] text-gray-600 shrink-0">신뢰도 추이</span>
                            <ConfidenceSparkline data={confTrends.get(device.id)!} />
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right: Camera Data */}
        <div className="col-span-12 lg:col-span-6">
          <Card>
            <CardHeader>카메라 데이터</CardHeader>
            <CardContent>
              {/* Snapshot */}
              <div className="rounded-lg overflow-hidden bg-gray-800 mb-3 aspect-video flex items-center justify-center">
                {camera.imgSrc ? (
                  <img
                    src={camera.imgSrc}
                    alt="Camera snapshot"
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <span className="text-xs text-gray-600">카메라 스냅샷 없음</span>
                )}
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-500">감지 인원</span>
                  <span className="text-sm font-medium text-gray-200">{camera.personCount}명</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-500">카메라 포즈</span>
                  <span className={`text-xs font-medium ${poseColors[camera.pose]}`}>
                    {poseLabels[camera.pose]}
                  </span>
                </div>
                {camera.confidence > 0 && (
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-gray-600 shrink-0">신뢰도</span>
                    <ConfidenceBar value={camera.confidence} />
                    <span className="text-[10px] text-gray-500 shrink-0 w-8 text-right">
                      {Math.round(camera.confidence * 100)}%
                    </span>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Bottom: Fused Result */}
      <Card>
        <CardHeader>융합 결과</CardHeader>
        <CardContent>
          {devices.length === 0 ? (
            <p className="text-xs text-gray-500">디바이스 데이터 없음</p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {devices.map((device) => {
                const csiPose = poseFromEnergy(device.motion_energy);
                const csiConf = poseConfidence(device.motion_energy);
                const camPose = camera.pose;
                const agrees = csiPose === camPose || camPose === 'unknown' || csiPose === 'unknown';

                // Fused confidence: weighted average if both available
                const fusedConf =
                  camPose !== 'unknown' && csiPose !== 'unknown'
                    ? csiConf * 0.5 + camera.confidence * 0.5
                    : csiConf;

                const fusedPose = csiPose !== 'unknown' ? csiPose : camPose;

                return (
                  <div
                    key={device.id}
                    className={`rounded-lg border p-3 ${
                      agrees
                        ? 'border-emerald-800/50 bg-emerald-900/10'
                        : 'border-amber-800/50 bg-amber-900/10'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-gray-200">{device.name}</span>
                      <span
                        className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                          agrees
                            ? 'bg-emerald-500/20 text-emerald-400'
                            : 'bg-amber-500/20 text-amber-400'
                        }`}
                      >
                        {agrees ? '일치' : '불일치'}
                      </span>
                    </div>

                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-gray-500">융합 포즈</span>
                      <span className={`text-xs font-medium ${poseColors[fusedPose]}`}>
                        {poseLabels[fusedPose]}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-gray-600 shrink-0">신뢰도</span>
                      <ConfidenceBar value={fusedConf} />
                      <span className="text-[10px] text-gray-500 shrink-0 w-8 text-right">
                        {Math.round(fusedConf * 100)}%
                      </span>
                    </div>

                    <div className="mt-2 flex items-center gap-3 text-[10px] text-gray-600">
                      <span>
                        CSI: <span className={poseColors[csiPose]}>{poseLabels[csiPose]}</span>
                      </span>
                      <span>
                        CAM: <span className={poseColors[camPose]}>{poseLabels[camPose]}</span>
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
