import { useRef, useEffect, useState } from 'react';
import { Maximize2, Minimize2, ExternalLink } from 'lucide-react';

const OBSERVATORY_URL = '/observatory/index.html';

export default function ObservatoryMini() {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (event.origin !== window.location.origin) return;
      if (event.data?.type === 'observatory:status') {
        // Handle status updates from RuView Observatory
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, []);

  const toggleFullscreen = () => setIsFullscreen(!isFullscreen);
  const openInNewTab = () => window.open(OBSERVATORY_URL, '_blank');

  if (isFullscreen) {
    return (
      <div className="fixed inset-0 z-50 bg-surface-900">
        <div className="absolute top-4 right-4 z-10 flex gap-2">
          <button
            onClick={toggleFullscreen}
            className="p-2 bg-surface-800 border border-surface-600 rounded-lg hover:border-neon-cyan/50 text-gray-400 hover:text-neon-cyan transition-colors"
          >
            <Minimize2 className="w-4 h-4" />
          </button>
        </div>
        <iframe
          ref={iframeRef}
          src={OBSERVATORY_URL}
          className="w-full h-full border-0"
          title="RuView Observatory"
          onLoad={() => setLoaded(true)}
        />
      </div>
    );
  }

  return (
    <div className="card-glow h-[400px] relative">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-medium text-gray-400">3D Observatory</h3>
        <div className="flex gap-1">
          <button
            onClick={openInNewTab}
            className="text-gray-500 hover:text-neon-cyan transition-colors p-1"
            title="Open in new tab"
          >
            <ExternalLink className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={toggleFullscreen}
            className="text-gray-500 hover:text-neon-cyan transition-colors p-1"
            title="Fullscreen"
          >
            <Maximize2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
      <div className="w-full h-[calc(100%-2rem)] rounded-lg overflow-hidden border border-surface-600 relative">
        <iframe
          ref={iframeRef}
          src={OBSERVATORY_URL}
          className="w-full h-full border-0"
          title="RuView Observatory"
          onLoad={() => setLoaded(true)}
        />
        {!loaded && (
          <div className="absolute inset-0 flex items-center justify-center bg-surface-900 text-gray-500 text-sm">
            Loading Observatory...
          </div>
        )}
      </div>
    </div>
  );
}
