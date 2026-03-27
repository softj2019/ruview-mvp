/**
 * PoseDetectionCanvas — COCO-17 keypoint 스켈레톤 풀 렌더러
 * Phase 5-3 | 포즈 트레일, 퍼-퍼슨 색상, 신뢰도 배지 포함
 */
import { useEffect, useRef, useCallback } from 'react';
import type { PoseData, Keypoint17 } from '@/types/pose';

export type { PoseData, Keypoint17 };

// ─────────────────────────────────────────────────────────────────────────────
// COCO-17 keypoint 인덱스
// 0:nose, 1:left_eye, 2:right_eye, 3:left_ear, 4:right_ear,
// 5:left_shoulder, 6:right_shoulder, 7:left_elbow, 8:right_elbow,
// 9:left_wrist, 10:right_wrist, 11:left_hip, 12:right_hip,
// 13:left_knee, 14:right_knee, 15:left_ankle, 16:right_ankle
// ─────────────────────────────────────────────────────────────────────────────

const SKELETON_CONNECTIONS: [number, number][] = [
  [0, 1],   // nose → left_eye
  [0, 2],   // nose → right_eye
  [1, 3],   // left_eye → left_ear
  [2, 4],   // right_eye → right_ear
  [5, 6],   // left_shoulder → right_shoulder
  [5, 7],   // left_shoulder → left_elbow
  [6, 8],   // right_shoulder → right_elbow
  [7, 9],   // left_elbow → left_wrist
  [8, 10],  // right_elbow → right_wrist
  [5, 11],  // left_shoulder → left_hip
  [6, 12],  // right_shoulder → right_hip
  [11, 12], // left_hip → right_hip
  [11, 13], // left_hip → left_knee
  [12, 14], // right_hip → right_knee
  [13, 15], // left_knee → left_ankle
  [14, 16], // right_knee → right_ankle
  // neck (optional — index 17 이면 스킵됨)
  [0, 5],   // nose → left_shoulder (neck proxy)
  [0, 6],   // nose → right_shoulder
];

/** 퍼-퍼슨 6색 팔레트 */
const PERSON_COLORS: string[] = [
  '#38bdf8', // sky-400
  '#f472b6', // pink-400
  '#4ade80', // green-400
  '#fb923c', // orange-400
  '#a78bfa', // violet-400
  '#facc15', // yellow-400
];

function personColor(personId: string): string {
  let hash = 0;
  for (let i = 0; i < personId.length; i++) {
    hash = (hash * 31 + personId.charCodeAt(i)) >>> 0;
  }
  return PERSON_COLORS[hash % PERSON_COLORS.length];
}

function confidenceHsl(conf: number, alpha = 1): string {
  const hue = conf * 120; // 0=red, 60=yellow, 120=green
  return `hsla(${hue.toFixed(0)},100%,55%,${alpha.toFixed(2)})`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Props
// ─────────────────────────────────────────────────────────────────────────────

interface Props {
  poses: PoseData[];
  width: number;
  height: number;
  showSkeleton?: boolean;
  showConfidence?: boolean;
  trailLength?: number;
  colorByPerson?: boolean;
}

// ─────────────────────────────────────────────────────────────────────────────
// Trail 타입
// ─────────────────────────────────────────────────────────────────────────────

type TrailEntry = { kps: Keypoint17[]; ts: number };
type TrailMap = Map<string, TrailEntry[]>;

// ─────────────────────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────────────────────

export function PoseDetectionCanvas({
  poses,
  width,
  height,
  showSkeleton = true,
  showConfidence = true,
  trailLength = 15,
  colorByPerson = true,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const trailMapRef = useRef<TrailMap>(new Map());

  // 정규화 좌표 → 픽셀 (x: [0,1]→width, y: [0,1]→height)
  const px = useCallback((v: number, dim: number) => v * dim, []);

  // ── Trail 업데이트 ────────────────────────────────────────────────────────
  useEffect(() => {
    const now = Date.now();
    const map = trailMapRef.current;
    const seen = new Set<string>();

    poses.forEach((pose) => {
      seen.add(pose.personId);
      const history = map.get(pose.personId) ?? [];
      history.push({ kps: pose.keypoints, ts: now });
      if (history.length > trailLength) history.splice(0, history.length - trailLength);
      map.set(pose.personId, history);
    });

    // 사라진 사람 정리
    for (const id of map.keys()) {
      if (!seen.has(id)) map.delete(id);
    }
  }, [poses, trailLength]);

  // ── Canvas 렌더 ───────────────────────────────────────────────────────────
  const render = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, width, height);
    const CONF_THRESH = 0.3;

    poses.forEach((pose) => {
      const kps = pose.keypoints;
      if (!kps || kps.length === 0) return;
      const color = colorByPerson ? personColor(pose.personId) : '#38bdf8';

      // ── Trail ────────────────────────────────────────────────────────────
      const history = trailMapRef.current.get(pose.personId) ?? [];
      const histLen = history.length;
      if (histLen > 1) {
        history.slice(0, -1).forEach((frame, fi) => {
          const alpha = 0.08 + (fi / histLen) * 0.3;
          frame.kps.forEach((kp) => {
            if (kp.score < CONF_THRESH) return;
            ctx.globalAlpha = alpha;
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(px(kp.x, width), px(kp.y, height), 2, 0, Math.PI * 2);
            ctx.fill();
          });
        });
      }

      ctx.globalAlpha = 1.0;

      // ── Skeleton lines ───────────────────────────────────────────────────
      if (showSkeleton) {
        SKELETON_CONNECTIONS.forEach(([a, b]) => {
          const kpA = kps[a];
          const kpB = kps[b];
          if (!kpA || !kpB) return;
          if (kpA.score < CONF_THRESH || kpB.score < CONF_THRESH) return;

          const avgConf = (kpA.score + kpB.score) / 2;
          ctx.globalAlpha = 0.85;
          ctx.strokeStyle = colorByPerson ? color : confidenceHsl(avgConf);
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.moveTo(px(kpA.x, width), px(kpA.y, height));
          ctx.lineTo(px(kpB.x, width), px(kpB.y, height));
          ctx.stroke();
        });
      }

      ctx.globalAlpha = 1.0;

      // ── Keypoints ────────────────────────────────────────────────────────
      kps.forEach((kp) => {
        if (kp.score < CONF_THRESH) return;
        ctx.fillStyle = colorByPerson ? color : confidenceHsl(kp.score);
        ctx.beginPath();
        ctx.arc(px(kp.x, width), px(kp.y, height), 4, 0, Math.PI * 2);
        ctx.fill();
      });

      // ── Confidence badge ─────────────────────────────────────────────────
      if (showConfidence) {
        // 토르소 중심 (left_shoulder=5, right_shoulder=6, left_hip=11, right_hip=12)
        const torsoIdx = [5, 6, 11, 12];
        const valid = torsoIdx.map((i) => kps[i]).filter((k) => k && k.score >= CONF_THRESH);
        if (valid.length > 0) {
          const cx = valid.reduce((s, k) => s + k.x, 0) / valid.length;
          const cy = valid.reduce((s, k) => s + k.y, 0) / valid.length;
          const bx = px(cx, width);
          const by = px(cy, height);

          const label = `${pose.personId} ${(pose.confidence * 100).toFixed(0)}%`;
          ctx.font = 'bold 11px monospace';
          const tw = ctx.measureText(label).width;

          ctx.globalAlpha = 0.7;
          ctx.fillStyle = '#0f172a';
          ctx.fillRect(bx - tw / 2 - 4, by - 9, tw + 8, 16);

          ctx.globalAlpha = 1.0;
          ctx.fillStyle = color;
          ctx.fillText(label, bx - tw / 2, by + 3);
        }
      }

      // ── BBox ─────────────────────────────────────────────────────────────
      if (pose.bbox) {
        const [bx, by, bw, bh] = pose.bbox;
        ctx.globalAlpha = 0.4;
        ctx.strokeStyle = color;
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 3]);
        ctx.strokeRect(px(bx, width), px(by, height), px(bw, width), px(bh, height));
        ctx.setLineDash([]);
      }
    });

    ctx.globalAlpha = 1.0;
  }, [poses, width, height, showSkeleton, showConfidence, colorByPerson, px]);

  useEffect(() => {
    render();
  }, [render]);

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      className="block rounded-lg bg-gray-950"
      style={{ width, height }}
    />
  );
}

export default PoseDetectionCanvas;
