import { useEffect, useRef, useState, useCallback } from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8001';
const POLL_INTERVAL_MS = 1000;

interface NodeInfo {
  id: string;
  x: number;
  y: number;
  amplitude: number;
  phase: number;
}

interface AoAData {
  position: { x: number; y: number };
  confidence: number;
  method: 'triangulation' | 'single_node' | 'fallback';
  contributing_nodes: number;
  active_nodes: number;
  node_data: NodeInfo[];
}

const FLOOR_W = 760;
const FLOOR_H = 420;
const DATA_FLOOR_W = 800;
const DATA_FLOOR_H = 400;

// スケール変換: データ座標(800×400) → Canvas座標(760×420)
function toCanvas(dataX: number, dataY: number): [number, number] {
  return [
    8 + (dataX / DATA_FLOOR_W) * (FLOOR_W - 16),
    8 + (dataY / DATA_FLOOR_H) * (FLOOR_H - 16),
  ];
}

function drawFloorplan(ctx: CanvasRenderingContext2D, W: number, H: number) {
  // 배경
  ctx.fillStyle = '#0f172a';
  ctx.fillRect(0, 0, W, H);

  // 외벽
  ctx.strokeStyle = '#334155';
  ctx.lineWidth = 1.5;
  ctx.strokeRect(8, 8, W - 16, H - 16);

  // 내부 구획선
  const midX = W / 2;
  const midY = H / 2;
  ctx.beginPath();
  ctx.moveTo(midX, 8);
  ctx.lineTo(midX, H - 8);
  ctx.moveTo(8, midY);
  ctx.lineTo(W - 8, midY);
  ctx.stroke();

  // 존 레이블
  ctx.fillStyle = '#475569';
  ctx.font = '11px monospace';
  ctx.fillText('1001', 14, 22);
  ctx.fillText('1003', midX + 6, 22);
  ctx.fillText('1002', 14, midY + 16);
  ctx.fillText('1004', midX + 6, midY + 16);
}

function drawNodes(ctx: CanvasRenderingContext2D, nodes: NodeInfo[]) {
  for (const node of nodes) {
    const [px, py] = toCanvas(node.x, node.y);
    ctx.beginPath();
    ctx.arc(px, py, 6, 0, Math.PI * 2);
    ctx.fillStyle = '#22d3ee';
    ctx.fill();
    ctx.strokeStyle = '#0e7490';
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.fillStyle = '#e2e8f0';
    ctx.font = 'bold 9px monospace';
    ctx.fillText(node.id.replace('node-', 'N'), px + 8, py + 4);
  }
}

function drawPositionMarker(
  ctx: CanvasRenderingContext2D,
  px: number,
  py: number,
  confidence: number,
  pulse: number,
) {
  const [cx, cy] = toCanvas(px, py);

  // 펄스 링
  const pulseR = 14 + pulse * 12;
  const pulseAlpha = (1 - pulse) * 0.4 * confidence;
  ctx.beginPath();
  ctx.arc(cx, cy, pulseR, 0, Math.PI * 2);
  ctx.strokeStyle = `rgba(239,68,68,${pulseAlpha.toFixed(2)})`;
  ctx.lineWidth = 2;
  ctx.stroke();

  // 외곽 원
  ctx.beginPath();
  ctx.arc(cx, cy, 10, 0, Math.PI * 2);
  ctx.fillStyle = `rgba(239,68,68,${(0.25 * confidence).toFixed(2)})`;
  ctx.fill();
  ctx.strokeStyle = '#ef4444';
  ctx.lineWidth = 2;
  ctx.stroke();

  // 중심 점
  ctx.beginPath();
  ctx.arc(cx, cy, 4, 0, Math.PI * 2);
  ctx.fillStyle = '#fca5a5';
  ctx.fill();

  // 좌표 레이블
  ctx.fillStyle = '#fca5a5';
  ctx.font = 'bold 10px monospace';
  ctx.fillText(`(${Math.round(px)}, ${Math.round(py)})`, cx + 13, cy - 6);
}

function confidenceColor(c: number): string {
  if (c >= 0.7) return 'bg-green-500';
  if (c >= 0.4) return 'bg-yellow-500';
  return 'bg-red-500';
}

function methodLabel(m: string): string {
  if (m === 'triangulation') return '삼각측량';
  if (m === 'single_node') return '단일노드';
  return '폴백';
}

function methodBadgeVariant(m: string): 'default' | 'success' | 'warning' | 'danger' | 'info' {
  if (m === 'triangulation') return 'success';
  if (m === 'single_node') return 'warning';
  return 'danger';
}

export default function PositionPage() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);
  const pulseRef = useRef<number>(0);
  const dataRef = useRef<AoAData | null>(null);

  const [data, setData] = useState<AoAData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string>('—');

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/aoa/position`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = (await res.json()) as AoAData;
      setData(json);
      dataRef.current = json;
      setError(null);
      setLastUpdated(new Date().toLocaleTimeString('ko-KR'));
    } catch (e) {
      setError(e instanceof Error ? e.message : '알 수 없는 오류');
    }
  }, []);

  // 폴링
  useEffect(() => {
    void fetchData();
    const id = setInterval(() => void fetchData(), POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [fetchData]);

  // Canvas 렌더 루프
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    canvas.width = FLOOR_W;
    canvas.height = FLOOR_H;

    let lastTs = 0;
    function frame(ts: number) {
      animRef.current = requestAnimationFrame(frame);
      const dt = Math.min((ts - lastTs) / 1000, 0.1);
      lastTs = ts;

      pulseRef.current = (pulseRef.current + dt * 0.7) % 1;

      const ctx = canvas!.getContext('2d');
      if (!ctx) return;

      drawFloorplan(ctx, FLOOR_W, FLOOR_H);

      const d = dataRef.current;
      if (d) {
        drawNodes(ctx, d.node_data);
        if (d.confidence > 0) {
          drawPositionMarker(ctx, d.position.x, d.position.y, d.confidence, pulseRef.current);
        }
      }
    }

    animRef.current = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(animRef.current);
  }, []);

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-4">
      {/* 헤더 */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-bold tracking-tight text-gray-100">
            위치 추정
          </h1>
          <span className="text-xs text-gray-500 font-mono">SpotFi AoA</span>
          {data && (
            <Badge variant={methodBadgeVariant(data.method)} className="text-xs">
              {methodLabel(data.method)}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-500 font-mono">
          {error ? (
            <span className="text-red-400">{error}</span>
          ) : (
            <span>갱신 {lastUpdated}</span>
          )}
          {data && (
            <span className="text-cyan-500">
              활성 노드 {data.active_nodes}
            </span>
          )}
        </div>
      </div>

      <div className="flex gap-4 flex-col xl:flex-row">
        {/* Canvas 영역 */}
        <Card className="bg-gray-900 border-gray-800 p-2 flex-shrink-0">
          <canvas
            ref={canvasRef}
            className="block rounded"
            style={{ width: FLOOR_W, height: FLOOR_H }}
          />
        </Card>

        {/* 정보 패널 */}
        <div className="flex flex-col gap-3 min-w-[220px]">
          {/* 추정 위치 */}
          <Card className="bg-gray-900 border-gray-800 p-4">
            <p className="text-xs font-semibold uppercase tracking-widest text-gray-500 mb-2">
              추정 위치
            </p>
            {data ? (
              <div className="space-y-1">
                <div className="flex justify-between text-sm font-mono">
                  <span className="text-gray-400">X</span>
                  <span className="text-gray-100">{data.position.x.toFixed(1)} px</span>
                </div>
                <div className="flex justify-between text-sm font-mono">
                  <span className="text-gray-400">Y</span>
                  <span className="text-gray-100">{data.position.y.toFixed(1)} px</span>
                </div>
              </div>
            ) : (
              <p className="text-gray-600 text-sm">데이터 없음</p>
            )}
          </Card>

          {/* 신뢰도 게이지 */}
          <Card className="bg-gray-900 border-gray-800 p-4">
            <p className="text-xs font-semibold uppercase tracking-widest text-gray-500 mb-2">
              신뢰도
            </p>
            {data ? (
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-2xl font-bold font-mono text-gray-100">
                    {Math.round(data.confidence * 100)}%
                  </span>
                </div>
                <div className="w-full h-2 bg-gray-700 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${confidenceColor(data.confidence)}`}
                    style={{ width: `${data.confidence * 100}%` }}
                  />
                </div>
              </div>
            ) : (
              <p className="text-gray-600 text-sm">—</p>
            )}
          </Card>

          {/* 추정 방법 / 기여 노드 수 */}
          <Card className="bg-gray-900 border-gray-800 p-4">
            <p className="text-xs font-semibold uppercase tracking-widest text-gray-500 mb-2">
              방법 / 기여 노드
            </p>
            {data ? (
              <div className="space-y-1">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-400">방법</span>
                  <Badge variant={methodBadgeVariant(data.method)} className="text-xs">
                    {methodLabel(data.method)}
                  </Badge>
                </div>
                <div className="flex justify-between text-sm font-mono">
                  <span className="text-gray-400">기여 노드</span>
                  <span className="text-gray-100">{data.contributing_nodes}</span>
                </div>
              </div>
            ) : (
              <p className="text-gray-600 text-sm">—</p>
            )}
          </Card>

          {/* 활성 노드 목록 */}
          <Card className="bg-gray-900 border-gray-800 p-4 flex-1">
            <p className="text-xs font-semibold uppercase tracking-widest text-gray-500 mb-2">
              활성 노드
            </p>
            {data && data.node_data.length > 0 ? (
              <div className="space-y-2">
                {data.node_data.map((n) => (
                  <div
                    key={n.id}
                    className="rounded-md bg-gray-800/50 px-3 py-2 text-xs font-mono"
                  >
                    <div className="flex justify-between mb-0.5">
                      <span className="text-cyan-400 font-bold">{n.id}</span>
                      <span className="text-gray-500">
                        ({n.x}, {n.y})
                      </span>
                    </div>
                    <div className="flex justify-between text-gray-400">
                      <span>amp <span className="text-gray-200">{n.amplitude.toFixed(3)}</span></span>
                      <span>φ <span className="text-gray-200">{n.phase.toFixed(3)}</span></span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-600 text-sm">노드 없음</p>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
