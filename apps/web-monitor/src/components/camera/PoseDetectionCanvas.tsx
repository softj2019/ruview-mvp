/**
 * PoseDetectionCanvas — COCO 17 keypoint 실시간 스켈레톤 렌더링
 * Phase 2-13 | 참조: ruvnet-RuView/ui/components/PoseDetectionCanvas.js
 */
import { useEffect, useRef, useCallback } from 'react';

// COCO 17 keypoint 인덱스 정의
// 0:코, 1:왼눈, 2:오른눈, 3:왼귀, 4:오른귀,
// 5:왼어깨, 6:오른어깨, 7:왼팔꿈치, 8:오른팔꿈치,
// 9:왼손목, 10:오른손목, 11:왼엉덩이, 12:오른엉덩이,
// 13:왼무릎, 14:오른무릎, 15:왼발목, 16:오른발목

const SKELETON_CONNECTIONS: [number, number][] = [
  [0, 1], [0, 2],   // 코 → 눈
  [1, 3], [2, 4],   // 눈 → 귀
  [5, 6],           // 어깨
  [5, 7], [7, 9],   // 왼팔
  [6, 8], [8, 10],  // 오른팔
  [5, 11], [6, 12], // 몸통
  [11, 12],         // 엉덩이
  [11, 13], [13, 15], // 왼다리
  [12, 14], [14, 16], // 오른다리
];

// keypoint별 색상 팔레트 (COCO 순서)
const KP_COLORS: string[] = [
  '#ff0000', '#ff4500', '#ffa500', '#ffff00', '#adff2f',
  '#00ff00', '#00ff7f', '#00ffff', '#0080ff', '#0000ff',
  '#4000ff', '#8000ff', '#ff00ff', '#ff0080', '#ff0040',
  '#ff8080', '#ffb380',
];

// 연결선 색상 — 신뢰도에 따라 hsl 색상 계산
function confidenceColor(conf: number, alpha = 1): string {
  const hue = conf * 120; // 0=빨강, 60=노랑, 120=녹색
  return `hsla(${hue.toFixed(0)},100%,50%,${alpha.toFixed(2)})`;
}

export interface Person {
  id: string;
  keypoints: Array<{ x: number; y: number; confidence: number }>;
  pose: string;
  confidence: number;
}

interface Props {
  persons: Person[];
  width: number;
  height: number;
  showTrail?: boolean;
}

// 최대 5프레임 trail 저장
const MAX_TRAIL_FRAMES = 5;

// trail 프레임: [person][keypoint] 형태의 2차원 배열
type KeypointXYC = { x: number; y: number; confidence: number };
type PersonKps = KeypointXYC[];
type TrailFrame = PersonKps[];

export default function PoseDetectionCanvas({
  persons,
  width,
  height,
  showTrail = false,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const trailRef = useRef<TrailFrame[]>([]);

  // 좌표 정규화: [0,1] → 픽셀
  const toPixel = useCallback(
    (v: number, dim: number) => v * dim,
    [],
  );

  const drawKeypoints = useCallback(
    (
      ctx: CanvasRenderingContext2D,
      kps: Array<{ x: number; y: number; confidence: number }>,
      alpha: number,
      w: number,
      h: number,
    ) => {
      kps.forEach((kp, idx) => {
        if (kp.confidence < 0.1) return;
        const px = toPixel(kp.x, w);
        const py = toPixel(kp.y, h);
        ctx.globalAlpha = alpha;
        ctx.fillStyle = KP_COLORS[idx % KP_COLORS.length];
        ctx.beginPath();
        ctx.arc(px, py, 4, 0, Math.PI * 2);
        ctx.fill();
      });
    },
    [toPixel],
  );

  const drawSkeleton = useCallback(
    (
      ctx: CanvasRenderingContext2D,
      kps: Array<{ x: number; y: number; confidence: number }>,
      alpha: number,
      w: number,
      h: number,
    ) => {
      SKELETON_CONNECTIONS.forEach(([a, b]) => {
        const kpA = kps[a];
        const kpB = kps[b];
        if (!kpA || !kpB) return;
        if (kpA.confidence < 0.1 || kpB.confidence < 0.1) return;

        const avgConf = (kpA.confidence + kpB.confidence) / 2;
        ctx.globalAlpha = alpha;
        ctx.strokeStyle = confidenceColor(avgConf, alpha);
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(toPixel(kpA.x, w), toPixel(kpA.y, h));
        ctx.lineTo(toPixel(kpB.x, w), toPixel(kpB.y, h));
        ctx.stroke();
      });
    },
    [toPixel],
  );

  const drawLabel = useCallback(
    (
      ctx: CanvasRenderingContext2D,
      person: Person,
      w: number,
      h: number,
    ) => {
      // 바운딩 박스 최상단 keypoint 탐색
      const valid = person.keypoints.filter((kp) => kp.confidence > 0.1);
      if (valid.length === 0) return;
      const minY = Math.min(...valid.map((kp) => kp.y));
      const avgX =
        valid.reduce((s, kp) => s + kp.x, 0) / valid.length;

      const px = toPixel(avgX, w);
      const py = Math.max(0, toPixel(minY, h) - 16);

      ctx.globalAlpha = 0.9;
      ctx.font = '11px monospace';
      ctx.fillStyle = confidenceColor(person.confidence);
      ctx.fillText(
        `${person.pose} ${(person.confidence * 100).toFixed(0)}%`,
        px - 24,
        py,
      );
    },
    [toPixel],
  );

  const render = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, width, height);

    // --- trail 렌더링 (이전 프레임 잔상) ---
    if (showTrail && trailRef.current.length > 1) {
      const total = trailRef.current.length;
      trailRef.current.slice(0, -1).forEach((framePersonsKps, frameIdx) => {
        const frameAlpha = 0.08 + (frameIdx / total) * 0.35;
        const nextFrame = trailRef.current[frameIdx + 1];

        framePersonsKps.forEach((kps, personIdx) => {
          // 잔상 keypoint
          kps.forEach((kp, kpIdx) => {
            if (kp.confidence < 0.1) return;
            const px = toPixel(kp.x, width);
            const py = toPixel(kp.y, height);

            ctx.globalAlpha = frameAlpha * 0.6;
            ctx.fillStyle = KP_COLORS[kpIdx % KP_COLORS.length];
            ctx.beginPath();
            ctx.arc(px, py, 2.5, 0, Math.PI * 2);
            ctx.fill();

            // 다음 프레임 같은 keypoint로 이어지는 선
            const nextKps = nextFrame?.[personIdx];
            if (nextKps) {
              const nkp = nextKps[kpIdx];
              if (nkp && nkp.confidence > 0.1) {
                ctx.globalAlpha = frameAlpha * 0.4;
                ctx.strokeStyle = KP_COLORS[kpIdx % KP_COLORS.length];
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(px, py);
                ctx.lineTo(toPixel(nkp.x, width), toPixel(nkp.y, height));
                ctx.stroke();
              }
            }
          });
        });
      });
    }

    ctx.globalAlpha = 1.0;

    // --- 현재 프레임 렌더링 ---
    persons.forEach((person) => {
      const kps = person.keypoints;
      if (!kps || kps.length === 0) return;

      drawSkeleton(ctx, kps, 1.0, width, height);
      drawKeypoints(ctx, kps, 1.0, width, height);
      drawLabel(ctx, person, width, height);
    });

    ctx.globalAlpha = 1.0;
  }, [persons, width, height, showTrail, toPixel, drawSkeleton, drawKeypoints, drawLabel]);

  // trail 업데이트
  useEffect(() => {
    if (!showTrail) {
      trailRef.current = [];
      return;
    }
    if (persons.length === 0) return;

    const frame: TrailFrame = persons.map((p) =>
      p.keypoints.map((kp) => ({ x: kp.x, y: kp.y, confidence: kp.confidence })),
    );

    trailRef.current = [...trailRef.current, frame].slice(-MAX_TRAIL_FRAMES);
  }, [persons, showTrail]);

  // 렌더링
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
