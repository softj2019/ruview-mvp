import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/Card';
import { TrendingUp, MapPin, Users, Clock, AlertTriangle } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8001';

interface HeatmapEntry {
  zone_id: string;
  dwell_seconds: number;
}

interface HeatmapData {
  heatmap: HeatmapEntry[];
}

interface GaitDevice {
  id: string;
  cadence: number;
  asymmetry: number;
  variability: number;
  fall_risk: number;
}

interface GaitData {
  devices: GaitDevice[];
}

interface QueueData {
  queue_length: number;
  estimated_wait_seconds: number;
  message: string;
}

function formatDwell(seconds: number): string {
  if (seconds < 60) return `${seconds}초`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return s > 0 ? `${m}분 ${s}초` : `${m}분`;
}

function riskColor(score: number): string {
  if (score >= 0.7) return 'text-red-400';
  if (score >= 0.4) return 'text-yellow-400';
  return 'text-green-400';
}

export default function AnalyticsPage() {
  const [heatmap, setHeatmap] = useState<HeatmapData | null>(null);
  const [gait, setGait] = useState<GaitData | null>(null);
  const [queue, setQueue] = useState<QueueData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      const [heatmapRes, gaitRes, queueRes] = await Promise.all([
        fetch(`${API_BASE}/api/analytics/heatmap`),
        fetch(`${API_BASE}/api/gait/analysis`),
        fetch(`${API_BASE}/api/analytics/queue`),
      ]);
      if (!heatmapRes.ok || !gaitRes.ok || !queueRes.ok) throw new Error('API 응답 오류');
      const [heatmapData, gaitData, queueData] = await Promise.all([
        heatmapRes.json(),
        gaitRes.json(),
        queueRes.json(),
      ]);
      setHeatmap(heatmapData);
      setGait(gaitData);
      setQueue(queueData);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : '데이터 로드 실패');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-3">
        <TrendingUp className="h-6 w-6 text-cyan-400" />
        <div>
          <h1 className="text-xl font-semibold text-gray-100">공간 분석</h1>
          <p className="text-sm text-gray-400">존별 재실 히트맵 · 보행 분석 · 대기열 모니터링</p>
        </div>
      </div>

      {loading && (
        <div className="text-center text-gray-400 py-12">데이터 로딩 중...</div>
      )}

      {error && (
        <Card>
          <div className="flex items-center gap-2 text-red-400">
            <AlertTriangle className="h-4 w-4" />
            <span className="text-sm">{error}</span>
          </div>
        </Card>
      )}

      {!loading && (
        <>
          {/* Heatmap */}
          {heatmap && (
            <Card>
              <div className="flex items-center gap-2 mb-4">
                <MapPin className="h-4 w-4 text-gray-400" />
                <h2 className="text-sm font-semibold text-gray-200">존별 체류 시간 히트맵</h2>
              </div>
              {heatmap.heatmap.length === 0 ? (
                <p className="text-sm text-gray-500">데이터 없음</p>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {heatmap.heatmap.map((entry) => {
                    const maxDwell = Math.max(...heatmap.heatmap.map((e) => e.dwell_seconds), 1);
                    const ratio = entry.dwell_seconds / maxDwell;
                    const opacity = Math.max(0.15, ratio);
                    return (
                      <div
                        key={entry.zone_id}
                        className="rounded-lg px-3 py-3 text-center border border-cyan-800/30"
                        style={{ backgroundColor: `rgba(6, 182, 212, ${opacity * 0.3})` }}
                      >
                        <div className="text-xs text-gray-400 truncate">{entry.zone_id}</div>
                        <div className="text-base font-bold text-cyan-300 mt-1">
                          {formatDwell(entry.dwell_seconds)}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </Card>
          )}

          {/* Gait Analysis */}
          {gait && (
            <Card>
              <div className="flex items-center gap-2 mb-4">
                <Users className="h-4 w-4 text-gray-400" />
                <h2 className="text-sm font-semibold text-gray-200">보행 분석</h2>
              </div>
              {gait.devices.length === 0 ? (
                <p className="text-sm text-gray-500">온라인 디바이스 없음</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-xs text-gray-500 border-b border-gray-800">
                        <th className="pb-2 pr-4">디바이스</th>
                        <th className="pb-2 pr-4">케이던스 (steps/min)</th>
                        <th className="pb-2 pr-4">비대칭성</th>
                        <th className="pb-2 pr-4">변동성</th>
                        <th className="pb-2">낙상 위험도</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-800">
                      {gait.devices.map((d) => (
                        <tr key={d.id}>
                          <td className="py-2 pr-4 font-mono text-gray-300">{d.id}</td>
                          <td className="py-2 pr-4 text-gray-300">{d.cadence.toFixed(1)}</td>
                          <td className="py-2 pr-4 text-gray-300">{d.asymmetry.toFixed(3)}</td>
                          <td className="py-2 pr-4 text-gray-300">{d.variability.toFixed(3)}</td>
                          <td className={`py-2 font-semibold ${riskColor(d.fall_risk)}`}>
                            {(d.fall_risk * 100).toFixed(0)}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          )}

          {/* Queue */}
          {queue && (
            <Card>
              <div className="flex items-center gap-2 mb-4">
                <Clock className="h-4 w-4 text-gray-400" />
                <h2 className="text-sm font-semibold text-gray-200">대기열 현황</h2>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-gray-400">대기 인원</p>
                  <div className="text-2xl font-bold text-cyan-400 mt-1">{queue.queue_length}</div>
                </div>
                <div>
                  <p className="text-xs text-gray-400">예상 대기 시간</p>
                  <div className="text-2xl font-bold text-cyan-400 mt-1">
                    {formatDwell(queue.estimated_wait_seconds)}
                  </div>
                </div>
              </div>
              {queue.message && (
                <p className="mt-3 text-xs text-gray-500">{queue.message}</p>
              )}
            </Card>
          )}
        </>
      )}
    </div>
  );
}
