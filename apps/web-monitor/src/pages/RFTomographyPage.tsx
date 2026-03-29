import { useEffect, useRef, useState, useCallback } from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8001';

interface Node {
  id: string;
  x: number;
  y: number;
  nx: number;
  ny: number;
}

interface TomographyData {
  grid: number[][];
  rows: number;
  cols: number;
  max_value: number;
  mean_value: number;
  occupied_cells: number;
  node_count: number;
  nodes?: Node[];
  error?: string;
}

// 파란→초록→노란→빨간 컬러맵 (heat)
function heatColor(v: number): [number, number, number] {
  const t = Math.max(0, Math.min(1, v));
  if (t < 0.25) {
    return [0, Math.round(t * 4 * 255), 255];
  } else if (t < 0.5) {
    return [0, 255, Math.round((1 - (t - 0.25) * 4) * 255)];
  } else if (t < 0.75) {
    return [Math.round((t - 0.5) * 4 * 255), 255, 0];
  } else {
    return [255, Math.round((1 - (t - 0.75) * 4) * 255), 0];
  }
}

function drawHeatmap(
  canvas: HTMLCanvasElement,
  data: TomographyData,
  opacity: number,
) {
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const W = canvas.width;
  const H = canvas.height;
  ctx.clearRect(0, 0, W, H);

  // --- 배경 평면도 (4 zone 단순 외곽선) ---
  ctx.strokeStyle = '#334155';
  ctx.lineWidth = 1.5;
  // 전체 외벽
  ctx.strokeRect(8, 8, W - 16, H - 16);
  // 내부 구획선
  const midX = W / 2;
  const midY = H / 2;
  ctx.beginPath();
  ctx.moveTo(midX, 8); ctx.lineTo(midX, H - 8);  // 세로 중간
  ctx.moveTo(8, midY); ctx.lineTo(W - 8, midY);    // 가로 중간
  ctx.stroke();

  // 존 레이블
  ctx.fillStyle = '#475569';
  ctx.font = '11px monospace';
  ctx.fillText('1001', 14, 22);
  ctx.fillText('1003', midX + 6, 22);
  ctx.fillText('1002', 14, midY + 16);
  ctx.fillText('1004', midX + 6, midY + 16);

  // --- 히트맵 격자 ---
  const { grid, rows, cols } = data;
  const cellW = (W - 16) / cols;
  const cellH = (H - 16) / rows;

  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const v = grid[r]?.[c] ?? 0;
      if (v < 0.01) continue;
      const [red, green, blue] = heatColor(v);
      ctx.fillStyle = `rgba(${red},${green},${blue},${(opacity * v * 0.85).toFixed(2)})`;
      ctx.fillRect(8 + c * cellW, 8 + r * cellH, cellW, cellH);
    }
  }

  // --- 노드 마커 ---
  if (data.nodes) {
    for (const node of data.nodes) {
      const px = 8 + node.nx * (W - 16);
      const py = 8 + node.ny * (H - 16);
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

  // 컬러 범례 (우측)
  const legX = W - 22;
  const legH = H - 60;
  const legY = 30;
  const grad = ctx.createLinearGradient(0, legY, 0, legY + legH);
  grad.addColorStop(0, 'rgba(255,0,0,0.9)');
  grad.addColorStop(0.33, 'rgba(255,255,0,0.9)');
  grad.addColorStop(0.66, 'rgba(0,255,0,0.9)');
  grad.addColorStop(1, 'rgba(0,0,255,0.9)');
  ctx.fillStyle = grad;
  ctx.fillRect(legX, legY, 12, legH);
  ctx.strokeStyle = '#475569';
  ctx.lineWidth = 1;
  ctx.strokeRect(legX, legY, 12, legH);
  ctx.fillStyle = '#94a3b8';
  ctx.font = '9px monospace';
  ctx.fillText('高', legX + 1, legY - 4);
  ctx.fillText('低', legX + 1, legY + legH + 10);
}

export default function RFTomographyPage() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [data, setData] = useState<TomographyData | null>(null);
  const [rows, setRows] = useState(20);
  const [cols, setCols] = useState(20);
  const [lambda, setLambda] = useState(0.10);
  const [opacity, setOpacity] = useState(0.85);
  const [interval, setInterval_] = useState(2000);
  const [paused, setPaused] = useState(false);
  const [lastFetch, setLastFetch] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(
        `${API_BASE}/api/rf-tomography?rows=${rows}&cols=${cols}&lambda_reg=${lambda}`,
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json: TomographyData = await res.json();
      setData(json);
      setLastFetch(Date.now());
      setError(json.error ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message : '연결 오류');
    }
  }, [rows, cols, lambda]);

  // 첫 로드
  useEffect(() => { fetchData(); }, [fetchData]);

  // 폴링
  useEffect(() => {
    if (paused) return;
    const id = window.setInterval(fetchData, interval);
    return () => window.clearInterval(id);
  }, [fetchData, interval, paused]);

  // Canvas 렌더링
  useEffect(() => {
    if (!canvasRef.current || !data) return;
    drawHeatmap(canvasRef.current, data, opacity);
  }, [data, opacity]);

  const elapsed = lastFetch ? ((Date.now() - lastFetch) / 1000).toFixed(1) : '—';

  return (
    <div className="p-6 space-y-5">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-100">RF 토모그래피 히트맵</h1>
          <p className="text-sm text-gray-400 mt-0.5">
            벽 반사 CSI 파장 기반 공간 점유도 재구성 — ISTA L1 알고리즘
          </p>
        </div>
        <div className="flex items-center gap-2">
          {error ? (
            <Badge variant="danger">{error}</Badge>
          ) : data ? (
            <Badge variant="success">노드 {data.node_count}개 활성</Badge>
          ) : (
            <Badge variant="default">로딩...</Badge>
          )}
          <button
            onClick={() => setPaused((p) => !p)}
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-gray-800 hover:bg-gray-700 text-gray-200 transition-colors"
          >
            {paused ? '▶ 재개' : '⏸ 일시정지'}
          </button>
          <button
            onClick={fetchData}
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-cyan-900/50 hover:bg-cyan-800/60 text-cyan-300 transition-colors"
          >
            새로고침
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_280px] gap-5">
        {/* 메인 캔버스 */}
        <Card className="p-4">
          <canvas
            ref={canvasRef}
            width={760}
            height={420}
            className="w-full rounded-lg bg-gray-950 border border-gray-800"
            style={{ imageRendering: 'pixelated' }}
          />
          <div className="mt-2 flex justify-between text-xs text-gray-500">
            <span>격자: {rows}×{cols} ({rows * cols}px)</span>
            <span>최종 갱신: {elapsed}초 전</span>
          </div>
        </Card>

        {/* 제어 패널 */}
        <div className="space-y-4">
          {/* 통계 */}
          <Card className="p-4 space-y-3">
            <h3 className="text-sm font-medium text-gray-300">재구성 결과</h3>
            <StatRow label="점유 셀" value={data ? `${data.occupied_cells} / ${rows * cols}` : '—'} />
            <StatRow label="최대 강도" value={data ? data.max_value.toFixed(4) : '—'} />
            <StatRow label="평균 강도" value={data ? data.mean_value.toFixed(4) : '—'} />
            <StatRow label="활성 노드" value={data ? `${data.node_count}개` : '—'} />
          </Card>

          {/* 파라미터 */}
          <Card className="p-4 space-y-4">
            <h3 className="text-sm font-medium text-gray-300">파라미터</h3>

            <SliderRow
              label="격자 해상도"
              value={rows}
              min={5} max={40} step={5}
              display={`${rows}×${cols}`}
              onChange={(v) => { setRows(v); setCols(v); }}
            />
            <SliderRow
              label="λ 정규화"
              value={lambda * 100}
              min={1} max={50} step={1}
              display={lambda.toFixed(2)}
              onChange={(v) => setLambda(v / 100)}
            />
            <SliderRow
              label="히트맵 불투명도"
              value={Math.round(opacity * 100)}
              min={20} max={100} step={5}
              display={`${Math.round(opacity * 100)}%`}
              onChange={(v) => setOpacity(v / 100)}
            />
            <SliderRow
              label="갱신 주기"
              value={interval / 1000}
              min={1} max={10} step={1}
              display={`${interval / 1000}초`}
              onChange={(v) => setInterval_(v * 1000)}
            />
          </Card>

          {/* 알고리즘 정보 */}
          <Card className="p-4 space-y-2">
            <h3 className="text-sm font-medium text-gray-300">알고리즘</h3>
            <p className="text-xs text-gray-500 leading-relaxed">
              <span className="text-cyan-400">ISTA</span> (Iterative Shrinkage-Thresholding) 기반
              RF 토모그래피. 각 TX-RX 쌍의 첫 번째 Fresnel 영역 픽셀에 가중치를 부여,
              L1 정규화로 희소 점유도 격자를 재구성합니다.
            </p>
            <p className="text-xs text-gray-500 leading-relaxed">
              벽 반사(다중경로) 신호가 강할수록 해당 격자 셀 값이 높아집니다.
            </p>
            <div className="pt-1 border-t border-gray-800 text-[10px] text-gray-600 space-y-0.5">
              <div>참조: Beck & Teboulle (2009) FISTA</div>
              <div>참조: Kaltiokallio et al. (2012) RSS Localization</div>
            </div>
          </Card>

          {/* 노드 위치 */}
          {data?.nodes && data.nodes.length > 0 && (
            <Card className="p-4 space-y-2">
              <h3 className="text-sm font-medium text-gray-300">활성 노드</h3>
              <div className="space-y-1">
                {data.nodes.map((n) => (
                  <div key={n.id} className="flex justify-between text-xs">
                    <span className="text-cyan-400">{n.id}</span>
                    <span className="text-gray-400">
                      ({n.x.toFixed(0)}, {n.y.toFixed(0)})
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between text-xs">
      <span className="text-gray-400">{label}</span>
      <span className="text-gray-200 font-mono">{value}</span>
    </div>
  );
}

function SliderRow({
  label, value, min, max, step, display, onChange,
}: {
  label: string; value: number; min: number; max: number; step: number;
  display: string; onChange: (v: number) => void;
}) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-gray-400">
        <span>{label}</span>
        <span className="text-gray-200 font-mono">{display}</span>
      </div>
      <input
        type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full h-1.5 rounded-full bg-gray-700 accent-cyan-400 cursor-pointer"
      />
    </div>
  );
}
