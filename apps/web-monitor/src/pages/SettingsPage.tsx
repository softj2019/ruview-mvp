/**
 * SettingsPage — Phase 2-12
 * 임계값/카메라/시스템 설정 + ModelPanel/TrainingPanel 서브탭
 * 참조: ruvnet-RuView/ui/components/SettingsPanel.js
 */
import { useEffect, useState } from 'react';
import { Monitor, Play, Settings, Wifi, Sliders, Camera, Brain, Dumbbell } from 'lucide-react';
import { Badge, Card, CardHeader } from '@/components/ui';
import { cn } from '@/lib/utils';
import { ModelPanel } from '@/components/model/ModelPanel';
import { TrainingPanel } from '@/components/training/TrainingPanel';

const scenarios = [
  { id: 'idle', label: 'Idle' },
  { id: 'presence', label: 'Presence' },
  { id: 'motion', label: 'Motion' },
  { id: 'fall', label: 'Fall' },
  { id: 'breathing', label: 'Breathing' },
];

const TABS = [
  { id: 'general', label: 'General', icon: Settings },
  { id: 'thresholds', label: '임계값', icon: Sliders },
  { id: 'camera', label: '카메라', icon: Camera },
  { id: 'model', label: 'Model', icon: Brain },
  { id: 'training', label: 'Training', icon: Dumbbell },
] as const;

type TabId = (typeof TABS)[number]['id'];

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

// ─── Threshold settings ───────────────────────────────────────────────────────

interface ThresholdSettings {
  fallDetectionThreshold: number;
  presenceThreshold: number;
  weakSignalThreshold: number;
  motionEnergyMin: number;
}

// ─── Camera settings ──────────────────────────────────────────────────────────

interface CameraSettings {
  resolution: '480p' | '720p' | '1080p';
  fps: number;
  blurEnabled: boolean;
  detectionConfidence: number;
}

// ─── Sub-panels ───────────────────────────────────────────────────────────────

function SettingRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-2">
      <span className="text-sm text-gray-400">{label}</span>
      <div className="flex-shrink-0">{children}</div>
    </div>
  );
}

function NumberInput({
  value,
  min,
  max,
  step,
  onChange,
}: {
  value: number;
  min?: number;
  max?: number;
  step?: number;
  onChange: (v: number) => void;
}) {
  return (
    <input
      type="number"
      value={value}
      min={min}
      max={max}
      step={step}
      onChange={(e) => onChange(Number(e.target.value))}
      className="w-24 rounded border border-gray-700 bg-gray-900 px-2 py-1 text-right text-xs text-gray-300 focus:border-cyan-700 focus:outline-none"
    />
  );
}

function RangeWithValue({
  value,
  min,
  max,
  step,
  onChange,
}: {
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <input
        type="range"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-32 accent-cyan-500"
      />
      <span className="w-10 text-right text-xs text-gray-400">{value}</span>
    </div>
  );
}

function ThresholdsPanel({
  settings,
  onChange,
}: {
  settings: ThresholdSettings;
  onChange: (s: ThresholdSettings) => void;
}) {
  const set = <K extends keyof ThresholdSettings>(key: K, val: ThresholdSettings[K]) =>
    onChange({ ...settings, [key]: val });

  return (
    <Card>
      <CardHeader>
        <span className="flex items-center gap-2">
          <Sliders className="h-4 w-4" /> 감지 임계값
        </span>
      </CardHeader>
      <div className="divide-y divide-gray-800/60">
        <SettingRow label="낙상 감지 임계값 (energy)">
          <RangeWithValue
            value={settings.fallDetectionThreshold}
            min={1}
            max={20}
            step={0.5}
            onChange={(v) => set('fallDetectionThreshold', v)}
          />
        </SettingRow>
        <SettingRow label="재실 감지 임계값 (presence_score)">
          <RangeWithValue
            value={settings.presenceThreshold}
            min={0}
            max={1}
            step={0.05}
            onChange={(v) => set('presenceThreshold', v)}
          />
        </SettingRow>
        <SettingRow label="신호 약함 임계값 (RSSI dBm)">
          <NumberInput
            value={settings.weakSignalThreshold}
            min={-100}
            max={-40}
            step={1}
            onChange={(v) => set('weakSignalThreshold', v)}
          />
        </SettingRow>
        <SettingRow label="모션 에너지 최소값">
          <RangeWithValue
            value={settings.motionEnergyMin}
            min={0}
            max={5}
            step={0.1}
            onChange={(v) => set('motionEnergyMin', v)}
          />
        </SettingRow>
      </div>
    </Card>
  );
}

function CameraPanel({
  settings,
  onChange,
}: {
  settings: CameraSettings;
  onChange: (s: CameraSettings) => void;
}) {
  const set = <K extends keyof CameraSettings>(key: K, val: CameraSettings[K]) =>
    onChange({ ...settings, [key]: val });

  return (
    <Card>
      <CardHeader>
        <span className="flex items-center gap-2">
          <Camera className="h-4 w-4" /> 카메라 설정
        </span>
      </CardHeader>
      <div className="divide-y divide-gray-800/60">
        <SettingRow label="해상도">
          <select
            value={settings.resolution}
            onChange={(e) => set('resolution', e.target.value as CameraSettings['resolution'])}
            className="rounded border border-gray-700 bg-gray-900 px-2 py-1 text-xs text-gray-300 focus:border-cyan-700 focus:outline-none"
          >
            <option value="480p">480p</option>
            <option value="720p">720p</option>
            <option value="1080p">1080p</option>
          </select>
        </SettingRow>
        <SettingRow label="FPS">
          <NumberInput
            value={settings.fps}
            min={1}
            max={60}
            step={1}
            onChange={(v) => set('fps', v)}
          />
        </SettingRow>
        <SettingRow label="프라이버시 블러">
          <button
            onClick={() => set('blurEnabled', !settings.blurEnabled)}
            className={cn(
              'h-5 w-9 rounded-full transition-colors',
              settings.blurEnabled ? 'bg-cyan-600' : 'bg-gray-700',
            )}
          >
            <span
              className={cn(
                'block h-4 w-4 translate-x-0.5 rounded-full bg-white shadow transition-transform',
                settings.blurEnabled && 'translate-x-4',
              )}
            />
          </button>
        </SettingRow>
        <SettingRow label="감지 신뢰도 임계값">
          <RangeWithValue
            value={settings.detectionConfidence}
            min={0}
            max={1}
            step={0.05}
            onChange={(v) => set('detectionConfidence', v)}
          />
        </SettingRow>
      </div>
    </Card>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<TabId>('general');
  const [activeScenario, setActiveScenario] = useState('idle');
  const [status, setStatus] = useState('');
  const [mode, setMode] = useState<'hardware' | 'simulation'>('hardware');

  const [thresholds, setThresholds] = useState<ThresholdSettings>({
    fallDetectionThreshold: 8.0,
    presenceThreshold: 0.3,
    weakSignalThreshold: -75,
    motionEnergyMin: 0.5,
  });

  const [cameraSettings, setCameraSettings] = useState<CameraSettings>({
    resolution: '720p',
    fps: 30,
    blurEnabled: true,
    detectionConfidence: 0.4,
  });

  useEffect(() => {
    let ignore = false;
    async function loadHealth() {
      try {
        const res = await fetch(`${API_URL}/health`);
        const data = (await res.json()) as Record<string, unknown>;
        if (!ignore) setMode(data.mode === 'simulation' ? 'simulation' : 'hardware');
      } catch {
        if (!ignore) setMode('hardware');
      }
    }
    void loadHealth();
    return () => { ignore = true; };
  }, []);

  const changeScenario = async (scenario: string) => {
    if (mode !== 'simulation') {
      setStatus('Live hardware mode does not support scenario switching.');
      return;
    }
    try {
      const res = await fetch(`${API_URL}/api/scenario/${scenario}`, { method: 'POST' });
      const data = (await res.json()) as { scenario: string };
      setActiveScenario(data.scenario);
      setStatus(`Scenario changed: ${data.scenario}`);
    } catch {
      setStatus('Scenario change failed.');
    }
  };

  const applyThresholds = async () => {
    try {
      await fetch(`${API_URL}/api/v1/settings/thresholds`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(thresholds),
      });
      setStatus('임계값 설정 저장됨');
    } catch {
      setStatus('임계값 저장 실패');
    }
  };

  const applyCameraSettings = async () => {
    try {
      await fetch(`${API_URL}/api/v1/settings/camera`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cameraSettings),
      });
      setStatus('카메라 설정 저장됨');
    } catch {
      setStatus('카메라 설정 저장 실패');
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="flex items-center gap-2 text-xl font-semibold text-gray-100">
          <Settings className="h-5 w-5" /> Settings
        </h1>
        <p className="mt-0.5 text-sm text-gray-500">Runtime mode, thresholds, and connectivity</p>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 rounded-lg border border-gray-800 bg-gray-900 p-1">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={cn(
              'flex flex-1 items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
              activeTab === id
                ? 'bg-gray-800 text-gray-100'
                : 'text-gray-500 hover:text-gray-300',
            )}
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
          </button>
        ))}
      </div>

      {/* Status toast */}
      {status && (
        <p className="rounded border border-gray-800 bg-gray-900 px-3 py-1.5 text-xs text-gray-400">
          {status}
        </p>
      )}

      {/* General Tab */}
      {activeTab === 'general' && (
        <div className="max-w-2xl space-y-4">
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
      )}

      {/* Thresholds Tab */}
      {activeTab === 'thresholds' && (
        <div className="max-w-2xl space-y-4">
          <ThresholdsPanel settings={thresholds} onChange={setThresholds} />
          <div className="flex justify-end">
            <button
              onClick={() => void applyThresholds()}
              className="rounded border border-cyan-700 bg-cyan-500/10 px-4 py-1.5 text-sm text-cyan-400 hover:bg-cyan-500/20"
            >
              저장
            </button>
          </div>
        </div>
      )}

      {/* Camera Tab */}
      {activeTab === 'camera' && (
        <div className="max-w-2xl space-y-4">
          <CameraPanel settings={cameraSettings} onChange={setCameraSettings} />
          <div className="flex justify-end">
            <button
              onClick={() => void applyCameraSettings()}
              className="rounded border border-cyan-700 bg-cyan-500/10 px-4 py-1.5 text-sm text-cyan-400 hover:bg-cyan-500/20"
            >
              저장
            </button>
          </div>
        </div>
      )}

      {/* Model Tab */}
      {activeTab === 'model' && (
        <div className="max-w-2xl">
          <ModelPanel />
        </div>
      )}

      {/* Training Tab */}
      {activeTab === 'training' && (
        <div className="max-w-2xl">
          <TrainingPanel />
        </div>
      )}
    </div>
  );
}
