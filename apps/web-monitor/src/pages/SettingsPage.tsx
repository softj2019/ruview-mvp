import { useState } from 'react';
import { Settings, Play, Wifi, Database, Monitor } from 'lucide-react';

const scenarios = ['idle', 'presence', 'motion', 'fall', 'breathing'];

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

export default function SettingsPage() {
  const [activeScenario, setActiveScenario] = useState('idle');
  const [status, setStatus] = useState('');

  const changeScenario = async (scenario: string) => {
    try {
      const res = await fetch(`${API_URL}/api/scenario/${scenario}`, { method: 'POST' });
      const data = await res.json();
      setActiveScenario(data.scenario);
      setStatus(`Scenario changed to: ${data.scenario}`);
    } catch {
      setStatus('Failed to change scenario');
    }
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <h2 className="text-xl font-semibold flex items-center gap-2">
        <Settings className="w-5 h-5" /> Settings
      </h2>

      {/* Mock Scenario Control */}
      <div className="card">
        <h3 className="text-sm font-medium text-gray-400 mb-3 flex items-center gap-2">
          <Play className="w-4 h-4" /> Simulation Scenario
        </h3>
        <div className="flex flex-wrap gap-2">
          {scenarios.map((s) => (
            <button
              key={s}
              onClick={() => changeScenario(s)}
              className={`px-4 py-2 rounded-lg text-sm transition-all ${
                activeScenario === s
                  ? 'bg-neon-cyan/20 text-neon-cyan border border-neon-cyan/50'
                  : 'bg-surface-700 text-gray-400 border border-surface-600 hover:border-neon-cyan/30'
              }`}
            >
              {s}
            </button>
          ))}
        </div>
        {status && <p className="mt-2 text-xs text-gray-500">{status}</p>}
      </div>

      {/* Connection Info */}
      <div className="card">
        <h3 className="text-sm font-medium text-gray-400 mb-3 flex items-center gap-2">
          <Wifi className="w-4 h-4" /> Connection
        </h3>
        <div className="space-y-2 text-sm text-gray-400">
          <div className="flex justify-between">
            <span>WebSocket</span>
            <code className="text-xs bg-surface-700 px-2 py-0.5 rounded">
              {import.meta.env.VITE_WS_URL || 'ws://localhost:8001/ws/events'}
            </code>
          </div>
          <div className="flex justify-between">
            <span>API</span>
            <code className="text-xs bg-surface-700 px-2 py-0.5 rounded">{API_URL}</code>
          </div>
        </div>
      </div>

      {/* System Info */}
      <div className="card">
        <h3 className="text-sm font-medium text-gray-400 mb-3 flex items-center gap-2">
          <Monitor className="w-4 h-4" /> System
        </h3>
        <div className="space-y-2 text-sm text-gray-400">
          <div className="flex justify-between">
            <span>Mode</span>
            <span className="text-neon-orange">Mock / Simulation</span>
          </div>
          <div className="flex justify-between">
            <span>ESP32 Target</span>
            <span>ESP32-S3-DevKitC-1 (pending)</span>
          </div>
          <div className="flex justify-between">
            <span>Firmware</span>
            <span>RuView v0.5.0</span>
          </div>
        </div>
      </div>
    </div>
  );
}
