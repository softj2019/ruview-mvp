import { useRef, useState, useEffect } from 'react';
import { Maximize2, Minimize2, ExternalLink, Globe, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui';

const OBSERVATORY_URL = '/observatory/index.html';

export default function ObservatoryPage() {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [loaded, setLoaded] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [key, setKey] = useState(0);

  // ESC 키로 fullscreen 해제
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isFullscreen) setIsFullscreen(false);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isFullscreen]);

  const handleReload = () => {
    setLoaded(false);
    setKey((k) => k + 1);
  };

  const iframe = (
    <iframe
      key={key}
      ref={iframeRef}
      src={OBSERVATORY_URL}
      className="h-full w-full border-0"
      title="RuView 3D 관측소"
      allow="autoplay"
      onLoad={() => setLoaded(true)}
    />
  );

  /* ─── 전체화면 모드 ─── */
  if (isFullscreen) {
    return (
      <div className="fixed inset-0 z-50 flex flex-col bg-gray-950">
        {/* 최소화 툴바 */}
        <div className="absolute right-4 top-4 z-10 flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleReload}
            title="새로고침"
          >
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => window.open(OBSERVATORY_URL, '_blank')}
            title="새 탭에서 열기"
          >
            <ExternalLink className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsFullscreen(false)}
            title="창 모드로 전환 (ESC)"
          >
            <Minimize2 className="h-4 w-4" />
          </Button>
        </div>
        {!loaded && (
          <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-gray-950 text-sm text-gray-500">
            <Globe className="mb-3 h-8 w-8 animate-pulse text-cyan-500" />
            <span>관측소 초기화 중...</span>
          </div>
        )}
        {iframe}
      </div>
    );
  }

  /* ─── 일반 모드 ─── */
  return (
    <div className="flex h-full flex-col gap-4 p-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Globe className="h-5 w-5 text-cyan-400" />
          <div>
            <h1 className="text-lg font-semibold text-gray-100">3D 관측소</h1>
            <p className="text-xs text-gray-500">
              WiFi DensePose — 실시간 3D 재실 시각화
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={handleReload} title="새로고침">
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => window.open(OBSERVATORY_URL, '_blank')}
            title="새 탭에서 열기"
          >
            <ExternalLink className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsFullscreen(true)}
            title="전체화면"
          >
            <Maximize2 className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* 안내 배지 */}
      <div className="flex flex-wrap gap-2">
        {[
          { label: 'Human Pose Estimation', color: 'text-cyan-400' },
          { label: 'Vital Sign Monitoring', color: 'text-rose-400' },
          { label: 'Presence Detection', color: 'text-emerald-400' },
          { label: 'Fall Detection', color: 'text-amber-400' },
        ].map(({ label, color }) => (
          <span
            key={label}
            className={`rounded-full border border-gray-700 bg-gray-900 px-3 py-1 text-xs font-medium ${color}`}
          >
            {label}
          </span>
        ))}
      </div>

      {/* 관측소 iframe */}
      <div className="relative flex-1 overflow-hidden rounded-xl border border-gray-800 bg-gray-950 shadow-lg shadow-cyan-950/20">
        {!loaded && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-gray-950 text-sm text-gray-500">
            <Globe className="mb-3 h-8 w-8 animate-pulse text-cyan-500" />
            <span>관측소 초기화 중...</span>
          </div>
        )}
        {iframe}
      </div>

      {/* 키보드 단축키 힌트 */}
      <div className="flex flex-wrap items-center gap-3 text-[10px] text-gray-600">
        <span className="font-medium text-gray-500">단축키:</span>
        {['[A] 카메라 공전', '[D] 시나리오 전환', '[F] FPS 표시', '[S] 설정', '[Space] 일시정지'].map(
          (hint) => (
            <span key={hint} className="rounded border border-gray-800 bg-gray-900 px-1.5 py-0.5">
              {hint}
            </span>
          ),
        )}
      </div>
    </div>
  );
}
