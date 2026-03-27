/**
 * ModelPanel — Phase 2-10
 * 모델 라이브러리: 목록, 로드/언로드, LoRA 프로필 선택
 * 참조: ruvnet-RuView/ui/components/ModelPanel.js
 */
import { useEffect, useState, useCallback } from 'react';
import { Card, CardHeader } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

interface ModelInfo {
  id: string;
  filename?: string;
  version?: string;
  size_bytes?: number;
  pck_score?: number;
  lora_profiles?: string[];
}

interface ActiveModelInfo {
  model_id: string;
  avg_inference_ms?: number;
  frames_processed?: number;
}

function fmtBytes(b: number): string {
  if (b < 1024) return `${b} B`;
  if (b < 1_048_576) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1_048_576).toFixed(1)} MB`;
}

export function ModelPanel() {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [activeModel, setActiveModel] = useState<ActiveModelInfo | null>(null);
  const [loraProfiles, setLoraProfiles] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [listRes, activeRes] = await Promise.allSettled([
        fetch(`${API_URL}/api/v1/models`).then((r) => r.json()),
        fetch(`${API_URL}/api/v1/models/active`).then((r) => r.json()),
      ]);
      const list: ModelInfo[] =
        listRes.status === 'fulfilled' ? (listRes.value?.models ?? []) : [];
      const active: ActiveModelInfo | null =
        activeRes.status === 'fulfilled' && activeRes.value?.model_id
          ? activeRes.value
          : null;
      let lora: string[] = [];
      if (active) {
        try {
          const lr = await fetch(`${API_URL}/api/v1/models/${active.model_id}/lora`);
          lora = (await lr.json())?.profiles ?? [];
        } catch {
          /* lora unavailable */
        }
      }
      setModels(list);
      setActiveModel(active);
      setLoraProfiles(lora);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const loadModel = async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      await fetch(`${API_URL}/api/v1/models/${id}/load`, { method: 'POST' });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? `Load failed: ${e.message}` : 'Load failed');
      setLoading(false);
    }
  };

  const unloadModel = async () => {
    setLoading(true);
    setError(null);
    try {
      await fetch(`${API_URL}/api/v1/models/unload`, { method: 'POST' });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? `Unload failed: ${e.message}` : 'Unload failed');
      setLoading(false);
    }
  };

  const deleteModel = async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      await fetch(`${API_URL}/api/v1/models/${id}`, { method: 'DELETE' });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? `Delete failed: ${e.message}` : 'Delete failed');
      setLoading(false);
    }
  };

  const activateLora = async (modelId: string, profile: string) => {
    if (!profile) return;
    setLoading(true);
    setError(null);
    try {
      await fetch(`${API_URL}/api/v1/models/${modelId}/lora/${profile}`, { method: 'POST' });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? `LoRA failed: ${e.message}` : 'LoRA failed');
      setLoading(false);
    }
  };

  const availableModels = models.filter(
    (m) => !(activeModel && activeModel.model_id === m.id),
  );

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <span>Model Library</span>
          <Badge variant="info">{models.length}</Badge>
        </div>
      </CardHeader>

      {error && (
        <div className="mb-3 rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-400">
          {error}
        </div>
      )}

      {/* Active Model */}
      {activeModel && (
        <div className="mb-4 rounded-lg border border-l-4 border-l-emerald-500 border-gray-700 bg-gray-800/50 p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-medium text-gray-200">{activeModel.model_id}</span>
            <Badge variant="success">Active</Badge>
          </div>

          {(activeModel.avg_inference_ms != null || activeModel.frames_processed != null) && (
            <div className="mb-2 text-xs text-gray-500">
              {activeModel.avg_inference_ms != null && (
                <span>Inference: <span className="text-gray-300">{activeModel.avg_inference_ms.toFixed(1)} ms</span></span>
              )}
              {activeModel.avg_inference_ms != null && activeModel.frames_processed != null && (
                <span className="mx-2 text-gray-700">|</span>
              )}
              {activeModel.frames_processed != null && (
                <span>Frames: <span className="text-gray-300">{activeModel.frames_processed}</span></span>
              )}
            </div>
          )}

          {loraProfiles.length > 0 && (
            <div className="mb-2 flex items-center gap-2">
              <label className="text-xs text-gray-500">LoRA Profile:</label>
              <select
                className="flex-1 rounded border border-gray-700 bg-gray-900 px-2 py-1 text-xs text-gray-300 focus:border-cyan-700 focus:outline-none"
                onChange={(e) => activateLora(activeModel.model_id, e.target.value)}
                defaultValue=""
              >
                <option value="">-- none --</option>
                {loraProfiles.map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </div>
          )}

          <button
            onClick={unloadModel}
            disabled={loading}
            className="rounded border border-red-500/30 bg-red-500/10 px-3 py-1 text-xs text-red-400 hover:bg-red-500/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Unload
          </button>
        </div>
      )}

      {/* Available Models */}
      <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-gray-600">
        Available Models
      </div>

      {availableModels.length === 0 && !loading && (
        <p className="py-4 text-center text-xs text-gray-600">
          No .rvf models found. Train a model or place .rvf files in data/models/
        </p>
      )}

      <div className="space-y-2">
        {availableModels.map((m) => (
          <div
            key={m.id}
            className="rounded-lg border border-gray-800 bg-gray-900/50 p-3 transition-colors hover:border-cyan-900/50"
          >
            <div className="mb-1 text-sm font-medium text-gray-300">
              {m.filename ?? m.id}
            </div>
            <div className="mb-2 flex flex-wrap gap-1">
              {m.version && (
                <span className="rounded bg-gray-800 px-1.5 py-0.5 text-[10px] text-gray-500">
                  v{m.version}
                </span>
              )}
              {m.size_bytes != null && (
                <span className="rounded bg-gray-800 px-1.5 py-0.5 text-[10px] text-gray-500">
                  {fmtBytes(m.size_bytes)}
                </span>
              )}
              {m.pck_score != null && (
                <span className="rounded bg-gray-800 px-1.5 py-0.5 text-[10px] text-gray-500">
                  PCK {(m.pck_score * 100).toFixed(1)}%
                </span>
              )}
              {(m.lora_profiles?.length ?? 0) > 0 && (
                <span className="rounded bg-gray-800 px-1.5 py-0.5 text-[10px] text-gray-500">
                  {m.lora_profiles!.length} LoRA
                </span>
              )}
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => loadModel(m.id)}
                disabled={loading}
                className="rounded border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs text-emerald-400 hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Load
              </button>
              <button
                onClick={() => deleteModel(m.id)}
                disabled={loading}
                className="rounded border border-gray-700/50 bg-transparent px-2 py-1 text-[11px] text-gray-600 hover:border-red-500/30 hover:text-red-400 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Delete
              </button>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-3 flex justify-end">
        <button
          onClick={() => void refresh()}
          disabled={loading}
          className="rounded border border-gray-700 bg-gray-800 px-3 py-1 text-xs text-gray-400 hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? 'Loading...' : 'Refresh'}
        </button>
      </div>
    </Card>
  );
}
