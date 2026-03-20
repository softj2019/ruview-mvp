import { useEffect, useState } from 'react';
import { Monitor, Play, Settings, Wifi } from 'lucide-react';
import { Badge, Card, CardHeader } from '@/components/ui';
import { cn } from '@/lib/utils';

const scenarios = [
  { id: 'idle', label: 'Idle' },
  { id: 'presence', label: 'Presence' },
  { id: 'motion', label: 'Motion' },
  { id: 'fall', label: 'Fall' },
  { id: 'breathing', label: 'Breathing' },
];

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

export default function SettingsPage() {
  const [activeScenario, setActiveScenario] = useState('idle');
  const [status, setStatus] = useState('');
  const [mode, setMode] = useState<'hardware' | 'simulation'>('hardware');

  useEffect(() => {
    let ignore = false;

    async function loadHealth() {
      try {
        const res = await fetch(`${API_URL}/health`);
        const data = await res.json();
        if (!ignore) {
          setMode(data.mode === 'simulation' ? 'simulation' : 'hardware');
        }
      } catch {
        if (!ignore) {
          setMode('hardware');
        }
      }
    }

    void loadHealth();
    return () => {
      ignore = true;
    };
  }, []);

  const changeScenario = async (scenario: string) => {
    if (mode !== 'simulation') {
      setStatus('Live hardware mode does not support scenario switching.');
      return;
    }

    try {
      const res = await fetch(`${API_URL}/api/scenario/${scenario}`, { method: 'POST' });
      const data = await res.json();
      setActiveScenario(data.scenario);
      setStatus(`Scenario changed: ${data.scenario}`);
    } catch {
      setStatus('Scenario change failed.');
    }
  };

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="flex items-center gap-2 text-xl font-semibold text-gray-100">
          <Settings className="h-5 w-5" /> Settings
        </h1>
        <p className="mt-0.5 text-sm text-gray-500">Runtime mode and connectivity</p>
      </div>

      <Card>
        <CardHeader>
          <span className="flex items-center gap-2">
            <Play className="h-4 w-4" /> Scenario Controls
          </span>
        </CardHeader>
        <div className="flex flex-wrap gap-2">
          {scenarios.map(({ id, label }) => (
            <button
              key={id}
              onClick={() => changeScenario(id)}
              disabled={mode !== 'simulation'}
              className={cn(
                'rounded-lg border px-4 py-2 text-sm font-medium transition-all disabled:cursor-not-allowed disabled:opacity-50',
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
          <span className="flex items-center gap-2">
            <Wifi className="h-4 w-4" /> Connection Info
          </span>
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
          <span className="flex items-center gap-2">
            <Monitor className="h-4 w-4" /> System Info
          </span>
        </CardHeader>
        <div className="space-y-2 text-sm">
          <div className="flex items-center justify-between">
            <span className="text-gray-400">Mode</span>
            <Badge variant={mode === 'simulation' ? 'warning' : 'success'}>
              {mode === 'simulation' ? 'Simulation' : 'Hardware Live'}
            </Badge>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-gray-400">ESP32</span>
            <span className="text-gray-300">
              {mode === 'simulation' ? 'Mock devices' : 'ESP32-S3 operational nodes'}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-gray-400">Firmware</span>
            <span className="text-gray-300">
              {mode === 'simulation' ? 'Simulation backend' : 'RuView live firmware'}
            </span>
          </div>
        </div>
      </Card>
    </div>
  );
}
