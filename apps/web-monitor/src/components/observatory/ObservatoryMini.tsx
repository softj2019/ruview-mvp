import { useRef, useEffect, useState } from 'react';
import { Maximize2, Minimize2, ExternalLink } from 'lucide-react';
import { Card, CardHeader } from '@/components/ui';
import { Button } from '@/components/ui';

const OBSERVATORY_URL = '/observatory/index.html';

export default function ObservatoryMini() {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (event.origin !== window.location.origin) return;
    };
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, []);

  if (isFullscreen) {
    return (
      <div className="fixed inset-0 z-50 bg-gray-950">
        <div className="absolute right-4 top-4 z-10">
          <Button variant="outline" size="sm" onClick={() => setIsFullscreen(false)}>
            <Minimize2 className="h-4 w-4" />
          </Button>
        </div>
        <iframe
          ref={iframeRef}
          src={OBSERVATORY_URL}
          className="h-full w-full border-0"
          title="RuView 관측소"
          onLoad={() => setLoaded(true)}
        />
      </div>
    );
  }

  return (
    <Card variant="glow" className="h-[420px]">
      <div className="mb-2 flex items-center justify-between">
        <CardHeader className="mb-0">3D 관측소</CardHeader>
        <div className="flex gap-1">
          <button
            onClick={() => window.open(OBSERVATORY_URL, '_blank')}
            className="rounded p-1 text-gray-500 transition-colors hover:text-cyan-400"
          >
            <ExternalLink className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={() => setIsFullscreen(true)}
            className="rounded p-1 text-gray-500 transition-colors hover:text-cyan-400"
          >
            <Maximize2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
      <div className="relative h-[calc(100%-2.5rem)] overflow-hidden rounded-lg border border-gray-800">
        <iframe
          ref={iframeRef}
          src={OBSERVATORY_URL}
          className="h-full w-full border-0"
          title="RuView 관측소"
          onLoad={() => setLoaded(true)}
        />
        {!loaded && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-950 text-sm text-gray-600">
            관측소 로딩 중...
          </div>
        )}
      </div>
    </Card>
  );
}
