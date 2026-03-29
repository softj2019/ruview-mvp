import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Moon, AlertTriangle, Activity } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8001';

interface DeviceSleepInfo {
  id: string;
  sleep_stage: string;
  apnea: boolean;
}

interface SleepStatus {
  sleep_stage: string;
  apnea_events_last_hour: number;
  devices: DeviceSleepInfo[];
}

interface SleepReport {
  stage_distribution: Record<string, number>;
  total_apnea_events: number;
}

const STAGE_LABELS: Record<string, string> = {
  wake: '각성',
  light: '얕은 수면',
  deep: '깊은 수면',
  rem: 'REM 수면',
  unknown: '알 수 없음',
};

const STAGE_COLORS: Record<string, string> = {
  wake: 'text-yellow-400',
  light: 'text-blue-400',
  deep: 'text-indigo-400',
  rem: 'text-purple-400',
  unknown: 'text-gray-500',
};

const STAGE_BADGE_VARIANT: Record<string, 'default' | 'warning' | 'success' | 'danger'> = {
  wake: 'warning',
  light: 'default',
  deep: 'success',
  rem: 'default',
  unknown: 'default',
};

export default function SleepPage() {
  const [status, setStatus] = useState<SleepStatus | null>(null);
  const [report, setReport] = useState<SleepReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      const [statusRes, reportRes] = await Promise.all([
        fetch(`${API_BASE}/api/sleep/status`),
        fetch(`${API_BASE}/api/sleep/report`),
      ]);
      if (!statusRes.ok || !reportRes.ok) throw new Error('API 응답 오류');
      const [statusData, reportData] = await Promise.all([statusRes.json(), reportRes.json()]);
      setStatus(statusData);
      setReport(reportData);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : '데이터 로드 실패');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-3">
        <Moon className="h-6 w-6 text-indigo-400" />
        <div>
          <h1 className="text-xl font-semibold text-gray-100">수면 모니터</h1>
          <p className="text-sm text-gray-400">CSI 기반 비접촉 수면 단계 분석 및 무호흡 감지</p>
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

      {status && !loading && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Card>
              <p className="text-xs text-gray-400 mb-1">현재 수면 단계</p>
              <div className={`text-2xl font-bold ${STAGE_COLORS[status.sleep_stage] ?? 'text-gray-300'}`}>
                {STAGE_LABELS[status.sleep_stage] ?? status.sleep_stage}
              </div>
            </Card>
            <Card>
              <p className="text-xs text-gray-400 mb-1">최근 1시간 무호흡 이벤트</p>
              <div className={`text-2xl font-bold ${status.apnea_events_last_hour > 0 ? 'text-red-400' : 'text-green-400'}`}>
                {status.apnea_events_last_hour}
              </div>
            </Card>
            <Card>
              <p className="text-xs text-gray-400 mb-1">온라인 디바이스</p>
              <div className="text-2xl font-bold text-cyan-400">{status.devices.length}</div>
            </Card>
          </div>

          <Card>
            <div className="flex items-center gap-2 mb-4">
              <Activity className="h-4 w-4 text-gray-400" />
              <h2 className="text-sm font-semibold text-gray-200">디바이스별 수면 상태</h2>
            </div>
            {status.devices.length === 0 ? (
              <p className="text-sm text-gray-500">온라인 디바이스 없음</p>
            ) : (
              <div className="space-y-2">
                {status.devices.map((d) => (
                  <div key={d.id} className="flex items-center justify-between rounded-lg bg-gray-800/50 px-3 py-2">
                    <span className="text-sm text-gray-300 font-mono">{d.id}</span>
                    <div className="flex items-center gap-2">
                      <Badge variant={STAGE_BADGE_VARIANT[d.sleep_stage] ?? 'default'}>
                        {STAGE_LABELS[d.sleep_stage] ?? d.sleep_stage}
                      </Badge>
                      {d.apnea && <Badge variant="danger">무호흡</Badge>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {report && (
            <Card>
              <h2 className="text-sm font-semibold text-gray-200 mb-4">수면 단계 분포</h2>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {Object.entries(report.stage_distribution).map(([stage, count]) => (
                  <div key={stage} className="rounded-lg bg-gray-800/50 px-3 py-2 text-center">
                    <div className={`text-lg font-bold ${STAGE_COLORS[stage] ?? 'text-gray-300'}`}>{count}</div>
                    <div className="text-xs text-gray-400 mt-0.5">{STAGE_LABELS[stage] ?? stage}</div>
                  </div>
                ))}
              </div>
              <div className="mt-3 text-xs text-gray-500">
                총 무호흡 이벤트:{' '}
                <span className="text-red-400 font-medium">{report.total_apnea_events}</span>
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
