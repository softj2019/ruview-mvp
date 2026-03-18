import { useState } from 'react';
import { Settings, Play, Wifi, Monitor } from 'lucide-react';
import { Card, CardHeader, Button, Badge } from '@/components/ui';
import { cn } from '@/lib/utils';

const scenarios = [
  { id: 'idle', label: '대기' },
  { id: 'presence', label: '재실' },
  { id: 'motion', label: '움직임' },
  { id: 'fall', label: '낙상' },
  { id: 'breathing', label: '호흡' },
];

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

export default function SettingsPage() {
  const [activeScenario, setActiveScenario] = useState('idle');
  const [status, setStatus] = useState('');

  const changeScenario = async (scenario: string) => {
    try {
      const res = await fetch(`${API_URL}/api/scenario/${scenario}`, { method: 'POST' });
      const data = await res.json();
      setActiveScenario(data.scenario);
      setStatus(`시나리오 변경: ${data.scenario}`);
    } catch {
      setStatus('시나리오 변경 실패');
    }
  };

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-100 flex items-center gap-2">
          <Settings className="h-5 w-5" /> 설정
        </h1>
        <p className="text-sm text-gray-500 mt-0.5">시뮬레이션 및 연결 설정</p>
      </div>

      <Card>
        <CardHeader>
          <span className="flex items-center gap-2"><Play className="h-4 w-4" /> 시뮬레이션 시나리오</span>
        </CardHeader>
        <div className="flex flex-wrap gap-2">
          {scenarios.map(({ id, label }) => (
            <button
              key={id}
              onClick={() => changeScenario(id)}
              className={cn(
                'rounded-lg border px-4 py-2 text-sm font-medium transition-all',
                activeScenario === id
                  ? 'border-cyan-700 bg-cyan-500/10 text-cyan-400'
                  : 'border-gray-800 bg-gray-900 text-gray-400 hover:border-cyan-800 hover:text-gray-300',
              )}
            >
              {label}
            </button>
          ))}
        </div>
        {status && <p className="mt-3 text-xs text-gray-500">{status}</p>}
      </Card>

      <Card>
        <CardHeader>
          <span className="flex items-center gap-2"><Wifi className="h-4 w-4" /> 연결 정보</span>
        </CardHeader>
        <div className="space-y-2 text-sm">
          <div className="flex items-center justify-between">
            <span className="text-gray-400">WebSocket</span>
            <code className="rounded bg-gray-800 px-2 py-0.5 text-xs text-gray-300">
              {import.meta.env.VITE_WS_URL || 'ws://localhost:8001/ws/events'}
            </code>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-gray-400">API</span>
            <code className="rounded bg-gray-800 px-2 py-0.5 text-xs text-gray-300">{API_URL}</code>
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader>
          <span className="flex items-center gap-2"><Monitor className="h-4 w-4" /> 시스템 정보</span>
        </CardHeader>
        <div className="space-y-2 text-sm">
          <div className="flex items-center justify-between">
            <span className="text-gray-400">모드</span>
            <Badge variant="warning">Mock 시뮬레이션</Badge>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-gray-400">ESP32 타겟</span>
            <span className="text-gray-300">ESP32-S3-DevKitC-1 (배송 중)</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-gray-400">펌웨어</span>
            <span className="text-gray-300">RuView v0.5.0</span>
          </div>
        </div>
      </Card>
    </div>
  );
}
