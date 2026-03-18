import { useRef, useEffect } from 'react';
import { Maximize2 } from 'lucide-react';

interface ObservatoryMessage {
  type: string;
  payload: Record<string, unknown>;
}

export default function ObservatoryMini() {
  const iframeRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    const handleMessage = (event: MessageEvent<ObservatoryMessage>) => {
      if (event.data?.type === 'observatory:status') {
        // Handle status updates from RuView Observatory
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, []);

  return (
    <div className="card-glow h-[400px] relative">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-medium text-gray-400">3D Observatory</h3>
        <button className="text-gray-500 hover:text-neon-cyan transition-colors">
          <Maximize2 className="w-4 h-4" />
        </button>
      </div>
      <div className="w-full h-[calc(100%-2rem)] rounded-lg overflow-hidden border border-surface-600">
        <div className="w-full h-full flex items-center justify-center bg-surface-900 text-gray-500 text-sm">
          <p>Observatory view will be connected to RuView</p>
        </div>
      </div>
    </div>
  );
}
