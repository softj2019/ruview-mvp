import { useEffect, useRef, useState } from 'react';
import { Card, CardHeader, CardContent } from '@/components/ui/Card';
import { useDeviceStore } from '@/stores/deviceStore';

// ──────────────────────────────────────────────
// Types
// ──────────────────────────────────────────────
type PoseClass = 'standing' | 'sitting' | 'lying' | 'walking' | 'exercising' | 'fallen' | 'unknown';

interface Joints {
  left_arm_raise: number;
  right_arm_raise: number;
  left_knee_bend: number;
  right_knee_bend: number;
  torso_lean: number;
}

interface DevicePose {
  pose: PoseClass;
  confidence: number;
  motion_index: number;
  breathing_rate: number;
  doppler_freq: number;
  joints: Joints;
  timestamp: string;
}

interface Keypoint {
  part: string;
  x: number;
  y: number;
  confidence: number;
}

interface KeypointsResponse {
  keypoints: Keypoint[];
  pose: PoseClass;
  confidence: number;
}

// ──────────────────────────────────────────────
// COCO skeleton connections (index into BODY_PARTS order in densepose_head)
// Using part names for clarity
// ──────────────────────────────────────────────
const SKELETON_CONNECTIONS: [string, string][] = [
  ['nose', 'neck'],
  ['neck', 'right_shoulder'],
  ['neck', 'left_shoulder'],
  ['right_shoulder', 'right_elbow'],
  ['right_elbow', 'right_wrist'],
  ['left_shoulder', 'left_elbow'],
  ['left_elbow', 'left_wrist'],
  ['right_shoulder', 'right_hip'],
  ['left_shoulder', 'left_hip'],
  ['right_hip', 'right_knee'],
  ['right_knee', 'right_ankle'],
  ['left_hip', 'left_knee'],
  ['left_knee', 'left_ankle'],
  ['right_hip', 'left_hip'],
  ['nose', 'right_eye'],
  ['nose', 'left_eye'],
  ['right_eye', 'right_ear'],
  ['left_eye', 'left_ear'],
];

// ──────────────────────────────────────────────
// Constants
// ──────────────────────────────────────────────
const POSE_LABELS: Record<PoseClass, string> = {
  standing: '서있음',
  sitting: '앉음',
  lying: '누움',
  walking: '걷는중',
  exercising: '운동중',
  fallen: '낙상',
  unknown: '미감지',
};

const POSE_COLORS: Record<PoseClass, string> = {
  standing: '#60a5fa',   // blue-400
  sitting: '#60a5fa',
  lying: '#60a5fa',
  walking: '#34d399',    // emerald-400
  exercising: '#fb923c', // orange-400
  fallen: '#f87171',     // red-400
  unknown: '#6b7280',    // gray-500
};

const CANVAS_W = 300;
const CANVAS_H = 500;
const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8001';

// ──────────────────────────────────────────────
// Sub-components
// ──────────────────────────────────────────────
function ConfidenceBar({ value }: { value: number }) {
  return (
    <div className="h-2 w-full rounded-full bg-gray-800">
      <div
        className="h-full rounded-full bg-cyan-500 transition-all duration-300"
        style={{ width: `${Math.round(value * 100)}%` }}
      />
    </div>
  );
}

function ReadonlySlider({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-[11px] text-gray-500 w-28 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 rounded-full bg-gray-800 relative">
        <div
          className="absolute left-0 top-0 h-full rounded-full bg-cyan-600"
          style={{ width: `${Math.round(Math.max(0, Math.min(1, value)) * 100)}%` }}
        />
      </div>
      <span className="text-[11px] text-gray-400 w-8 text-right">
        {Math.round(value * 100)}%
      </span>
    </div>
  );
}

function SkeletonCanvas({ keypoints, poseClass }: { keypoints: Keypoint[]; poseClass: PoseClass }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const color = POSE_COLORS[poseClass] ?? '#60a5fa';

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, CANVAS_W, CANVAS_H);

    // Background
    ctx.fillStyle = '#111827';
    ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);

    if (keypoints.length === 0) {
      ctx.fillStyle = '#374151';
      ctx.font = '14px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('감지된 포즈 없음', CANVAS_W / 2, CANVAS_H / 2);
      return;
    }

    const kptMap: Record<string, { x: number; y: number }> = {};
    for (const kpt of keypoints) {
      kptMap[kpt.part] = {
        x: kpt.x * CANVAS_W,
        y: kpt.y * CANVAS_H,
      };
    }

    // Draw skeleton connections
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.globalAlpha = 0.7;
    for (const [a, b] of SKELETON_CONNECTIONS) {
      const pa = kptMap[a];
      const pb = kptMap[b];
      if (!pa || !pb) continue;
      ctx.beginPath();
      ctx.moveTo(pa.x, pa.y);
      ctx.lineTo(pb.x, pb.y);
      ctx.stroke();
    }

    // Draw keypoint circles
    ctx.globalAlpha = 1.0;
    for (const kpt of keypoints) {
      const cx = kpt.x * CANVAS_W;
      const cy = kpt.y * CANVAS_H;
      ctx.beginPath();
      ctx.arc(cx, cy, 4, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.strokeStyle = '#1f2937';
      ctx.lineWidth = 1;
      ctx.stroke();
    }
  }, [keypoints, poseClass, color]);

  return (
    <canvas
      ref={canvasRef}
      width={CANVAS_W}
      height={CANVAS_H}
      className="rounded-lg border border-gray-800"
    />
  );
}

function DevicePoseCard({ deviceName, data }: {
  deviceName: string;
  data: DevicePose | undefined;
}) {
  const pose = (data?.pose ?? 'unknown') as PoseClass;
  const conf = data?.confidence ?? 0;
  const color = POSE_COLORS[pose];

  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-200">{deviceName}</span>
        <span className="text-xs font-semibold" style={{ color }}>
          {POSE_LABELS[pose]}
        </span>
      </div>
      <ConfidenceBar value={conf} />
      <div className="mt-1.5 flex items-center justify-between text-[10px] text-gray-500">
        <span>신뢰도 {Math.round(conf * 100)}%</span>
        <span>모션 {((data?.motion_index ?? 0) * 100).toFixed(0)}%</span>
        <span>도플러 {data?.doppler_freq?.toFixed(1) ?? '0.0'} Hz</span>
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────
// Main page
// ──────────────────────────────────────────────
export default function WifiPosePage() {
  const devices = useDeviceStore((s) => s.devices);

  const [allPoses, setAllPoses] = useState<Record<string, DevicePose>>({});
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>('');
  const [keypointsData, setKeypointsData] = useState<KeypointsResponse>({
    keypoints: [],
    pose: 'unknown',
    confidence: 0,
  });

  // Auto-select first device
  useEffect(() => {
    if (!selectedDeviceId && devices.length > 0) {
      setSelectedDeviceId(devices[0].id);
    }
  }, [devices, selectedDeviceId]);

  // Poll /api/pose/wifi every 1s
  useEffect(() => {
    let cancelled = false;

    const fetchPoses = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/pose/wifi`, {
          signal: AbortSignal.timeout(4000),
        });
        if (!res.ok) return;
        const json = await res.json();
        if (!cancelled) setAllPoses(json.poses ?? {});
      } catch {
        // ignore
      }
    };

    fetchPoses();
    const id = setInterval(fetchPoses, 1000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  // Poll keypoints for selected device
  useEffect(() => {
    if (!selectedDeviceId) return;
    let cancelled = false;

    const fetchKeypoints = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/pose/keypoints/${selectedDeviceId}`, {
          signal: AbortSignal.timeout(4000),
        });
        if (!res.ok) return;
        const json: KeypointsResponse = await res.json();
        if (!cancelled) setKeypointsData(json);
      } catch {
        // ignore
      }
    };

    fetchKeypoints();
    const id = setInterval(fetchKeypoints, 1000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [selectedDeviceId]);

  const selectedPose = (allPoses[selectedDeviceId]?.pose ?? 'unknown') as PoseClass;
  const selectedData = allPoses[selectedDeviceId];
  const joints = selectedData?.joints;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold text-gray-100">WiFi 포즈 추정</h1>
        <p className="text-sm text-gray-500 mt-0.5">CSI 기반 6종 자세 분류 + 관절 각도 근사</p>
      </div>

      {/* Device selector */}
      <div className="flex items-center gap-3">
        <label className="text-sm text-gray-400 shrink-0">디바이스 선택</label>
        <select
          className="bg-gray-900 border border-gray-700 rounded-lg text-sm text-gray-200 px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-cyan-500"
          value={selectedDeviceId}
          onChange={(e) => setSelectedDeviceId(e.target.value)}
        >
          {devices.length === 0 ? (
            <option value="">디바이스 없음</option>
          ) : (
            devices.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} ({d.id})
              </option>
            ))
          )}
        </select>
      </div>

      {/* Main content: skeleton + detail */}
      <div className="grid grid-cols-12 gap-6">
        {/* Left: skeleton canvas */}
        <div className="col-span-12 lg:col-span-5 flex flex-col items-center gap-3">
          <SkeletonCanvas keypoints={keypointsData.keypoints} poseClass={selectedPose} />
          <p className="text-xs text-gray-600">
            {selectedDeviceId
              ? `${selectedDeviceId} — 키포인트 ${keypointsData.keypoints.length}개`
              : '디바이스를 선택하세요'}
          </p>
        </div>

        {/* Right: detail panel */}
        <div className="col-span-12 lg:col-span-7 space-y-4">
          {/* Current pose + confidence */}
          <Card>
            <CardHeader>현재 포즈</CardHeader>
            <CardContent>
              <div className="flex items-center justify-between mb-3">
                <span
                  className="text-3xl font-bold"
                  style={{ color: POSE_COLORS[selectedPose] }}
                >
                  {POSE_LABELS[selectedPose]}
                </span>
                <span className="text-sm text-gray-400">
                  {selectedData ? `${Math.round(selectedData.confidence * 100)}%` : '—'}
                </span>
              </div>
              <ConfidenceBar value={selectedData?.confidence ?? 0} />

              {selectedData && (
                <div className="mt-3 grid grid-cols-3 gap-2 text-center">
                  <div className="rounded bg-gray-800/60 py-2 px-1">
                    <p className="text-[10px] text-gray-500">모션</p>
                    <p className="text-sm font-medium text-gray-200">
                      {(selectedData.motion_index * 100).toFixed(0)}%
                    </p>
                  </div>
                  <div className="rounded bg-gray-800/60 py-2 px-1">
                    <p className="text-[10px] text-gray-500">도플러</p>
                    <p className="text-sm font-medium text-gray-200">
                      {selectedData.doppler_freq.toFixed(1)} Hz
                    </p>
                  </div>
                  <div className="rounded bg-gray-800/60 py-2 px-1">
                    <p className="text-[10px] text-gray-500">호흡</p>
                    <p className="text-sm font-medium text-gray-200">
                      {selectedData.breathing_rate.toFixed(1)} BPM
                    </p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Joint angles */}
          <Card>
            <CardHeader>관절 각도 추정</CardHeader>
            <CardContent>
              {joints ? (
                <div className="space-y-2">
                  <ReadonlySlider label="왼팔 올림" value={joints.left_arm_raise} />
                  <ReadonlySlider label="오른팔 올림" value={joints.right_arm_raise} />
                  <ReadonlySlider label="왼무릎 굽힘" value={joints.left_knee_bend} />
                  <ReadonlySlider label="오른무릎 굽힘" value={joints.right_knee_bend} />
                  <div className="flex items-center gap-3">
                    <span className="text-[11px] text-gray-500 w-28 shrink-0">몸통 기울기</span>
                    <div className="flex-1 h-1.5 rounded-full bg-gray-800 relative">
                      <div
                        className="absolute top-0 h-full rounded-full bg-cyan-600"
                        style={{
                          left: '50%',
                          width: `${Math.abs(joints.torso_lean) * 50}%`,
                          transform: joints.torso_lean < 0 ? 'translateX(-100%)' : 'none',
                        }}
                      />
                    </div>
                    <span className="text-[11px] text-gray-400 w-12 text-right">
                      {joints.torso_lean >= 0 ? '앞' : '뒤'} {Math.abs(Math.round(joints.torso_lean * 100))}%
                    </span>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-gray-600">데이터 없음</p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* All devices pose cards */}
      <div>
        <h2 className="text-sm font-semibold text-gray-400 mb-3">전체 디바이스 포즈</h2>
        {devices.length === 0 ? (
          <p className="text-xs text-gray-600">디바이스 없음</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {devices.map((device) => (
              <DevicePoseCard
                key={device.id}
                deviceName={device.name}
                data={allPoses[device.id]}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
