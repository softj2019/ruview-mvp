import { useState, useRef, useCallback } from 'react';
import { Camera, Maximize2, Minimize2, Settings, ZoomIn, ZoomOut } from 'lucide-react';
import { Card, CardHeader } from '@/components/ui';
import { useZoneStore } from '@/stores/zoneStore';

function getCamUrl(): string {
  const { hostname } = window.location;
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return 'http://localhost:8002';
  }
  return `http://${hostname}:8002`;
}

const CAM_BASE = getCamUrl();

export default function CameraFeed() {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showCalibration, setShowCalibration] = useState(false);
  const [connected, setConnected] = useState(true);
  const [zoom, setZoom] = useState(1.0);
  const imgRef = useRef<HTMLImageElement>(null);
  const zones = useZoneStore((s) => s.zones);
  const cameraPersonCount = (zones[0] as unknown as Record<string, unknown>)?.camera_person_count as number | undefined;

  const handleZoom = useCallback(async (delta: number) => {
    const newZoom = Math.max(1.0, Math.min(5.0, zoom + delta));
    setZoom(newZoom);
    try {
      await fetch(`${CAM_BASE}/cam/zoom`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ level: newZoom, center: [0.5, 0.5] }),
      });
      // Force stream reload
      if (imgRef.current) {
        const src = imgRef.current.src;
        imgRef.current.src = '';
        imgRef.current.src = src;
      }
    } catch {}
  }, [zoom]);

  const streamUrl = `${CAM_BASE}/cam/stream`;

  if (isFullscreen) {
    return (
      <div className="fixed inset-0 z-50 bg-gray-950 flex flex-col">
        <div className="flex items-center justify-between p-3 bg-gray-900/80">
          <div className="flex items-center gap-2">
            <Camera className="h-4 w-4 text-cyan-400" />
            <span className="text-sm text-gray-300">카메라 모니터링</span>
            {cameraPersonCount !== undefined && (
              <span className="ml-2 rounded bg-emerald-500/20 px-2 py-0.5 text-xs text-emerald-400">
                감지 {cameraPersonCount}명
              </span>
            )}
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setShowCalibration(!showCalibration)}
              className="rounded p-1.5 text-gray-400 hover:text-cyan-400 transition-colors"
            >
              <Settings className="h-4 w-4" />
            </button>
            <button
              onClick={() => setIsFullscreen(false)}
              className="rounded p-1.5 text-gray-400 hover:text-white transition-colors"
            >
              <Minimize2 className="h-4 w-4" />
            </button>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center p-4">
          <img
            ref={imgRef}
            src={streamUrl}
            alt="Camera Feed"
            className="max-h-full max-w-full object-contain rounded-lg"
            onError={() => setConnected(false)}
            onLoad={() => setConnected(true)}
          />
        </div>
        {showCalibration && <CalibrationPanel />}
      </div>
    );
  }

  return (
    <Card variant="glow" className="h-[420px]">
      <div className="mb-2 flex items-center justify-between">
        <CardHeader className="mb-0">
          <span className="flex items-center gap-2">
            <Camera className="h-4 w-4" />
            카메라
            {cameraPersonCount !== undefined && (
              <span className="ml-1 text-sm text-emerald-400">
                {cameraPersonCount}명
              </span>
            )}
          </span>
        </CardHeader>
        <div className="flex items-center gap-1">
          <button
            onClick={() => handleZoom(-0.5)}
            className="rounded p-1 text-gray-500 transition-colors hover:text-cyan-400 disabled:opacity-30"
            disabled={zoom <= 1.0}
          >
            <ZoomOut className="h-3.5 w-3.5" />
          </button>
          {zoom > 1.0 && (
            <span className="text-[10px] text-cyan-400">{zoom.toFixed(1)}x</span>
          )}
          <button
            onClick={() => handleZoom(0.5)}
            className="rounded p-1 text-gray-500 transition-colors hover:text-cyan-400 disabled:opacity-30"
            disabled={zoom >= 5.0}
          >
            <ZoomIn className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={() => setShowCalibration(!showCalibration)}
            className="rounded p-1 text-gray-500 transition-colors hover:text-cyan-400"
          >
            <Settings className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={() => setIsFullscreen(true)}
            className="rounded p-1 text-gray-500 transition-colors hover:text-cyan-400"
          >
            <Maximize2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
      <div className="relative h-[calc(100%-2.5rem)] overflow-hidden rounded-lg border border-gray-800 bg-gray-950">
        {connected ? (
          <img
            ref={imgRef}
            src={streamUrl}
            alt="Camera Feed"
            className="h-full w-full object-contain"
            onError={() => setConnected(false)}
          />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-gray-600">
            <div className="text-center">
              <Camera className="mx-auto mb-2 h-8 w-8 text-gray-700" />
              <p>카메라 연결 대기중...</p>
              <button
                onClick={() => setConnected(true)}
                className="mt-2 text-xs text-cyan-500 hover:text-cyan-400"
              >
                재연결
              </button>
            </div>
          </div>
        )}
      </div>
      {showCalibration && <CalibrationPanel />}
    </Card>
  );
}

function CalibrationPanel() {
  const [points, setPoints] = useState({
    camera_points: [[0, 0], [640, 0], [640, 480], [0, 480]],
    floor_points: [[80, 80], [720, 80], [720, 420], [80, 420]],
  });
  const [status, setStatus] = useState('');

  const handleSave = async () => {
    try {
      const res = await fetch(`${CAM_BASE}/cam/calibration`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(points),
      });
      if (res.ok) {
        setStatus('저장 완료');
      } else {
        setStatus('저장 실패');
      }
    } catch {
      setStatus('연결 실패');
    }
    setTimeout(() => setStatus(''), 3000);
  };

  const handleLoad = async () => {
    try {
      const res = await fetch(`${CAM_BASE}/cam/calibration`);
      if (res.ok) {
        const data = await res.json();
        setPoints({
          camera_points: data.camera_points,
          floor_points: data.floor_points,
        });
        setStatus('로드 완료');
      }
    } catch {
      setStatus('연결 실패');
    }
    setTimeout(() => setStatus(''), 3000);
  };

  return (
    <div className="absolute bottom-0 left-0 right-0 rounded-b-lg border-t border-gray-700 bg-gray-900/95 p-3 backdrop-blur">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-medium text-gray-400">좌표 캘리브레이션</span>
        <div className="flex gap-2">
          <button onClick={handleLoad} className="text-xs text-cyan-500 hover:text-cyan-400">불러오기</button>
          <button onClick={handleSave} className="text-xs text-emerald-500 hover:text-emerald-400">저장</button>
          {status && <span className="text-xs text-yellow-400">{status}</span>}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <p className="mb-1 text-gray-500">카메라 좌표 (px)</p>
          {points.camera_points.map((pt, i) => (
            <div key={i} className="flex gap-1 mb-0.5">
              <span className="w-4 text-gray-600">{i + 1}</span>
              <input
                type="number" value={pt[0]}
                onChange={(e) => {
                  const next = [...points.camera_points];
                  next[i] = [Number(e.target.value), next[i][1]];
                  setPoints({ ...points, camera_points: next });
                }}
                className="w-16 rounded bg-gray-800 px-1 text-gray-300"
              />
              <input
                type="number" value={pt[1]}
                onChange={(e) => {
                  const next = [...points.camera_points];
                  next[i] = [next[i][0], Number(e.target.value)];
                  setPoints({ ...points, camera_points: next });
                }}
                className="w-16 rounded bg-gray-800 px-1 text-gray-300"
              />
            </div>
          ))}
        </div>
        <div>
          <p className="mb-1 text-gray-500">평면도 좌표</p>
          {points.floor_points.map((pt, i) => (
            <div key={i} className="flex gap-1 mb-0.5">
              <span className="w-4 text-gray-600">{i + 1}</span>
              <input
                type="number" value={pt[0]}
                onChange={(e) => {
                  const next = [...points.floor_points];
                  next[i] = [Number(e.target.value), next[i][1]];
                  setPoints({ ...points, floor_points: next });
                }}
                className="w-16 rounded bg-gray-800 px-1 text-gray-300"
              />
              <input
                type="number" value={pt[1]}
                onChange={(e) => {
                  const next = [...points.floor_points];
                  next[i] = [next[i][0], Number(e.target.value)];
                  setPoints({ ...points, floor_points: next });
                }}
                className="w-16 rounded bg-gray-800 px-1 text-gray-300"
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
