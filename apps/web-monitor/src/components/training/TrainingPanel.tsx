/**
 * TrainingPanel — Phase 2-11
 * CSI 녹음 관리 + 훈련 진행 상태 + PCK 메트릭 차트
 * 참조: ruvnet-RuView/ui/components/TrainingPanel.js
 */
import { useEffect, useState, useCallback, useRef } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import { Card, CardHeader } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

interface Recording {
  id: string;
  name?: string;
  frame_count?: number;
  file_size_bytes?: number;
  started_at?: string;
  ended_at?: string;
}

interface TrainingStatus {
  active: boolean;
  epoch?: number;
  total_epochs?: number;
  train_loss?: number;
  val_pck?: number;
  val_oks?: number;
  lr?: number;
  best_pck?: number;
  best_epoch?: number;
  patience_remaining?: number;
  eta_secs?: number;
  phase?: string;
}

interface ChartPoint {
  epoch: number;
  loss?: number;
  pck?: number;
}

function fmtBytes(b: number): string {
  if (b < 1024) return `${b} B`;
  if (b < 1_048_576) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1_048_576).toFixed(1)} MB`;
}

function fmtEta(s: number): string {
  if (s < 60) return `${Math.round(s)}s`;
  if (s < 3600) return `${Math.round(s / 60)}m`;
  return `${(s / 3600).toFixed(1)}h`;
}

interface TrainConfig {
  epochs: number;
  batch_size: number;
  learning_rate: number;
  patience: number;
  base_model: string;
  lora_profile_name: string;
}

export function TrainingPanel() {
  const [recordings, setRecordings] = useState<Recording[]>([]);
  const [status, setStatus] = useState<TrainingStatus | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [chartData, setChartData] = useState<ChartPoint[]>([]);
  const [config, setConfig] = useState<TrainConfig>({
    epochs: 100,
    batch_size: 32,
    learning_rate: 0.0003,
    patience: 15,
    base_model: '',
    lora_profile_name: '',
  });
  const evtRef = useRef<EventSource | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [recRes, statRes] = await Promise.allSettled([
        fetch(`${API_URL}/api/v1/train/recordings`).then((r) => r.json()),
        fetch(`${API_URL}/api/v1/train/status`).then((r) => r.json()),
      ]);
      const recs: Recording[] = recRes.status === 'fulfilled' ? (recRes.value ?? []) : [];
      const stat: TrainingStatus | null =
        statRes.status === 'fulfilled' ? statRes.value : null;
      if (stat && !stat.active) setChartData([]);
      setRecordings(recs);
      setStatus(stat);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, []);

  // SSE progress stream
  const connectStream = useCallback(() => {
    if (evtRef.current) return;
    const es = new EventSource(`${API_URL}/api/v1/train/progress`);
    evtRef.current = es;
    es.onmessage = (ev) => {
      try {
        const d: Partial<TrainingStatus> = JSON.parse(ev.data);
        setStatus((prev) => ({ ...(prev ?? { active: true }), ...d }));
        setChartData((prev) => {
          const epoch = d.epoch ?? prev.length + 1;
          const existing = prev.find((p) => p.epoch === epoch);
          if (existing) return prev;
          return [
            ...prev,
            { epoch, loss: d.train_loss, pck: d.val_pck },
          ];
        });
      } catch {/* ignore */}
    };
    es.onerror = () => { es.close(); evtRef.current = null; };
  }, []);

  const disconnectStream = useCallback(() => {
    evtRef.current?.close();
    evtRef.current = null;
  }, []);

  useEffect(() => {
    void refresh();
    return () => disconnectStream();
  }, [refresh, disconnectStream]);

  const startRecording = async () => {
    setLoading(true);
    setError(null);
    try {
      await fetch(`${API_URL}/api/v1/train/recordings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_name: `rec_${Date.now()}`, label: 'pose' }),
      });
      setIsRecording(true);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? `Recording failed: ${e.message}` : 'Recording failed');
    } finally {
      setLoading(false);
    }
  };

  const stopRecording = async () => {
    setLoading(true);
    setError(null);
    try {
      await fetch(`${API_URL}/api/v1/train/recordings/stop`, { method: 'POST' });
      setIsRecording(false);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? `Stop failed: ${e.message}` : 'Stop failed');
    } finally {
      setLoading(false);
    }
  };

  const deleteRecording = async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      await fetch(`${API_URL}/api/v1/train/recordings/${id}`, { method: 'DELETE' });
      setSelectedIds((prev) => { const s = new Set(prev); s.delete(id); return s; });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? `Delete failed: ${e.message}` : 'Delete failed');
    } finally {
      setLoading(false);
    }
  };

  const startTraining = async () => {
    setLoading(true);
    setError(null);
    setChartData([]);
    connectStream();
    try {
      await fetch(`${API_URL}/api/v1/train/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          dataset_ids: Array.from(selectedIds),
          config: {
            epochs: config.epochs,
            batch_size: config.batch_size,
            learning_rate: config.learning_rate,
            patience: config.patience,
            ...(config.base_model ? { base_model: config.base_model } : {}),
          },
        }),
      });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? `Training failed: ${e.message}` : 'Training failed');
      disconnectStream();
    } finally {
      setLoading(false);
    }
  };

  const stopTraining = async () => {
    setLoading(true);
    setError(null);
    try {
      await fetch(`${API_URL}/api/v1/train/stop`, { method: 'POST' });
      disconnectStream();
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? `Stop failed: ${e.message}` : 'Stop failed');
    } finally {
      setLoading(false);
    }
  };

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const s = new Set(prev);
      s.has(id) ? s.delete(id) : s.add(id);
      return s;
    });
  };

  const isActive = status?.active ?? false;
  const isCompleted = !isActive && chartData.length > 0;
  const pct = status?.total_epochs ? Math.round(((status.epoch ?? 0) / status.total_epochs) * 100) : 0;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <span>Training</span>
          <Badge variant={isActive ? 'success' : isCompleted ? 'info' : 'default'}>
            {isActive ? 'Training' : isCompleted ? 'Completed' : 'Idle'}
          </Badge>
        </div>
      </CardHeader>

      {error && (
        <div className="mb-3 rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-400">
          {error}
        </div>
      )}

      {/* CSI Recordings */}
      <div className="mb-4">
        <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-gray-600">
          CSI Recordings
        </div>
        {recordings.length === 0 && !loading && (
          <p className="py-3 text-center text-xs text-gray-600">
            Start recording CSI data to train a model
          </p>
        )}
        <div className="space-y-1.5">
          {recordings.map((rec) => {
            const parts: string[] = [];
            if (rec.frame_count != null) parts.push(`${rec.frame_count} frames`);
            if (rec.file_size_bytes != null) parts.push(fmtBytes(rec.file_size_bytes));
            if (rec.started_at && rec.ended_at) {
              const dur = Math.round(
                (new Date(rec.ended_at).getTime() - new Date(rec.started_at).getTime()) / 1000,
              );
              parts.push(`${dur}s`);
            }
            return (
              <div
                key={rec.id}
                className="flex items-center justify-between rounded border border-gray-800 bg-gray-900/50 px-2 py-1.5"
              >
                <label className="flex cursor-pointer items-center gap-2">
                  <input
                    type="checkbox"
                    checked={selectedIds.has(rec.id)}
                    onChange={() => toggleSelect(rec.id)}
                    className="h-3.5 w-3.5 rounded border-gray-600 bg-gray-800 accent-cyan-500"
                  />
                  <div>
                    <div className="text-xs font-medium text-gray-300">{rec.name ?? rec.id}</div>
                    <div className="text-[10px] text-gray-600">{parts.join(' / ')}</div>
                  </div>
                </label>
                <button
                  onClick={() => deleteRecording(rec.id)}
                  disabled={loading}
                  className="text-[11px] text-gray-600 hover:text-red-400 disabled:opacity-50"
                >
                  Delete
                </button>
              </div>
            );
          })}
        </div>
        <div className="mt-2">
          {isRecording ? (
            <button
              onClick={stopRecording}
              disabled={loading}
              className="rounded border border-red-500/30 bg-red-500/10 px-3 py-1 text-xs text-red-400 hover:bg-red-500/20 disabled:opacity-50"
            >
              Stop Recording
            </button>
          ) : (
            <button
              onClick={startRecording}
              disabled={loading}
              className="rounded border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-xs text-red-400 hover:bg-red-500/20 disabled:opacity-50"
            >
              Start Recording
            </button>
          )}
        </div>
      </div>

      {/* Training Progress */}
      {isActive && (
        <div className="mb-4 border-t border-gray-800 pt-4">
          <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-gray-600">
            Training Progress
          </div>
          <div className="mb-1 h-1.5 overflow-hidden rounded-full bg-gray-800">
            <div
              className="h-full rounded-full bg-gradient-to-r from-cyan-600 to-violet-600 transition-all duration-300"
              style={{ width: `${pct}%` }}
            />
          </div>
          <p className="mb-3 text-center text-[10px] text-gray-600">
            Epoch {status?.epoch ?? 0} / {status?.total_epochs ?? '?'} ({pct}%)
          </p>

          {chartData.length > 1 && (
            <div className="mb-3 h-40">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                  <XAxis dataKey="epoch" tick={{ fontSize: 9, fill: '#6b7280' }} />
                  <YAxis tick={{ fontSize: 9, fill: '#6b7280' }} />
                  <Tooltip
                    contentStyle={{ background: '#111827', border: '1px solid #374151', fontSize: 11 }}
                  />
                  <Legend wrapperStyle={{ fontSize: 10 }} />
                  <Line type="monotone" dataKey="loss" stroke="#f87171" dot={false} name="Loss" />
                  <Line type="monotone" dataKey="pck" stroke="#34d399" dot={false} name="PCK" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          <div className="mb-3 grid grid-cols-4 gap-1.5">
            {[
              { label: 'Loss', value: status?.train_loss?.toFixed(4) },
              { label: 'PCK', value: status?.val_pck != null ? `${(status.val_pck * 100).toFixed(1)}%` : undefined },
              { label: 'OKS', value: status?.val_oks?.toFixed(3) },
              { label: 'LR', value: status?.lr?.toExponential(1) },
              { label: 'Best PCK', value: status?.best_pck != null ? `${(status.best_pck * 100).toFixed(1)}%` : undefined },
              { label: 'Patience', value: status?.patience_remaining?.toString() },
              { label: 'ETA', value: status?.eta_secs != null ? fmtEta(status.eta_secs) : undefined },
              { label: 'Phase', value: status?.phase },
            ].map(({ label, value }) => (
              <div key={label} className="rounded border border-gray-800 bg-gray-900/50 p-1.5">
                <div className="text-[9px] uppercase text-gray-600">{label}</div>
                <div className="text-xs font-medium text-gray-300">{value ?? '--'}</div>
              </div>
            ))}
          </div>

          <button
            onClick={stopTraining}
            disabled={loading}
            className="rounded border border-red-500/30 bg-red-500/10 px-3 py-1 text-xs text-red-400 hover:bg-red-500/20 disabled:opacity-50"
          >
            Stop Training
          </button>
        </div>
      )}

      {/* Completed Summary */}
      {isCompleted && !isActive && (
        <div className="mb-4 border-t border-gray-800 pt-4">
          <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-gray-600">
            Training Complete
          </div>
          <div className="mb-3 grid grid-cols-2 gap-1.5">
            {[
              { label: 'Final Loss', value: chartData[chartData.length - 1]?.loss?.toFixed(4) },
              { label: 'Best PCK', value: status?.best_pck != null ? `${(status.best_pck * 100).toFixed(1)}%` : undefined },
              { label: 'Best Epoch', value: status?.best_epoch?.toString() },
              { label: 'Total Epochs', value: chartData.length.toString() },
            ].map(({ label, value }) => (
              <div key={label} className="rounded border border-gray-800 bg-gray-900/50 p-2">
                <div className="text-[9px] uppercase text-gray-600">{label}</div>
                <div className="text-sm font-medium text-gray-300">{value ?? '--'}</div>
              </div>
            ))}
          </div>
          <button
            onClick={() => { setChartData([]); setStatus(null); }}
            className="rounded border border-gray-700 bg-gray-800 px-3 py-1 text-xs text-gray-400 hover:bg-gray-700"
          >
            New Training
          </button>
        </div>
      )}

      {/* Training Config (shown when idle) */}
      {!isActive && !isCompleted && (
        <div className="border-t border-gray-800 pt-4">
          <div className="mb-3 text-[10px] font-semibold uppercase tracking-wider text-gray-600">
            Training Configuration
          </div>
          <div className="mb-3 space-y-2">
            {(
              [
                { label: 'Epochs', key: 'epochs', type: 'number' },
                { label: 'Batch Size', key: 'batch_size', type: 'number' },
                { label: 'Learning Rate', key: 'learning_rate', type: 'text' },
                { label: 'Early Stop Patience', key: 'patience', type: 'number' },
              ] as const
            ).map(({ label, key, type }) => (
              <div key={key} className="flex items-center justify-between gap-2">
                <label className="text-xs text-gray-500">{label}</label>
                <input
                  type={type}
                  value={config[key]}
                  onChange={(e) =>
                    setConfig((prev) => ({
                      ...prev,
                      [key]: type === 'number' ? Number(e.target.value) : e.target.value,
                    }))
                  }
                  className="w-28 rounded border border-gray-700 bg-gray-900 px-2 py-1 text-xs text-gray-300 focus:border-cyan-700 focus:outline-none"
                />
              </div>
            ))}
            <div className="flex items-center justify-between gap-2">
              <label className="text-xs text-gray-500">Base Model (opt.)</label>
              <input
                type="text"
                value={config.base_model}
                onChange={(e) => setConfig((prev) => ({ ...prev, base_model: e.target.value }))}
                placeholder="model id"
                className="w-28 rounded border border-gray-700 bg-gray-900 px-2 py-1 text-xs text-gray-400 placeholder-gray-700 focus:border-cyan-700 focus:outline-none"
              />
            </div>
            <div className="flex items-center justify-between gap-2">
              <label className="text-xs text-gray-500">LoRA Profile (opt.)</label>
              <input
                type="text"
                value={config.lora_profile_name}
                onChange={(e) => setConfig((prev) => ({ ...prev, lora_profile_name: e.target.value }))}
                placeholder="profile name"
                className="w-28 rounded border border-gray-700 bg-gray-900 px-2 py-1 text-xs text-gray-400 placeholder-gray-700 focus:border-cyan-700 focus:outline-none"
              />
            </div>
          </div>

          <div className="flex gap-2">
            <button
              onClick={startTraining}
              disabled={loading}
              className="rounded border border-emerald-500/30 bg-emerald-500/10 px-3 py-1.5 text-xs text-emerald-400 hover:bg-emerald-500/20 disabled:opacity-50"
            >
              Start Training
            </button>
          </div>
        </div>
      )}
    </Card>
  );
}
