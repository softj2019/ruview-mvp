import { useCallback } from 'react';
import { Routes, Route } from 'react-router-dom';
import DashboardPage from './pages/DashboardPage';
import DevicesPage from './pages/DevicesPage';
import EventsPage from './pages/EventsPage';
import SensingPage from './pages/SensingPage';
import SettingsPage from './pages/SettingsPage';
import AppShell from './components/layout/AppShell';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useDeviceStore, type Device } from '@/stores/deviceStore';
import { useZoneStore, type Zone } from '@/stores/zoneStore';
import { useEventStore, type DetectionEvent } from '@/stores/eventStore';
import { useSignalStore, type SignalPoint } from '@/stores/signalStore';

function getWsUrl(): string {
  if (import.meta.env.VITE_WS_URL) return import.meta.env.VITE_WS_URL;
  const { hostname } = window.location;

  // Local development
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return 'ws://localhost:8001/ws/events';
  }

  // Cloudflare Pages deployment — connect to relay Worker
  if (hostname.includes('pages.dev') || hostname.includes('workers.dev')) {
    return 'wss://ruview-relay.dev-softj.workers.dev/api/front/ws?session=default';
  }

  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${wsProtocol}//${hostname}/ws/events`;
}
const WS_URL = getWsUrl();

function DataProvider({ children }: { children: React.ReactNode }) {
  const setDevices = useDeviceStore((s) => s.setDevices);
  const setZones = useZoneStore((s) => s.setZones);
  const addEvent = useEventStore((s) => s.addEvent);
  const addSignalPoint = useSignalStore((s) => s.addPoint);

  const handleMessage = useCallback(
    (data: unknown) => {
      const msg = data as { type: string; payload: Record<string, unknown> };
      if (!msg || !msg.type) return;
      switch (msg.type) {
        case 'init':
          if (msg.payload.devices) setDevices(msg.payload.devices as Device[]);
          if (msg.payload.zones) setZones(msg.payload.zones as Zone[]);
          break;
        case 'event':
          addEvent(msg.payload as unknown as DetectionEvent);
          break;
        case 'signal':
          addSignalPoint(msg.payload as unknown as SignalPoint);
          break;
        case 'device_update':
          if (msg.payload.devices) setDevices(msg.payload.devices as Device[]);
          break;
        case 'zone_update':
          if (msg.payload.zones) setZones(msg.payload.zones as Zone[]);
          break;
        case 'vitals':
          // vitals payload does not match SignalPoint schema; observatory consumes it via its own WS
          break;
        case 'camera_detection':
          // camera detections update zones via zone_update; no separate handling needed
          break;
      }
    },
    [setDevices, setZones, addEvent, addSignalPoint],
  );

  useWebSocket({
    url: WS_URL,
    onMessage: handleMessage,
    onOpen: () => console.log('[WS] Connected to', WS_URL),
    onClose: () => console.log('[WS] Disconnected'),
  });

  return <>{children}</>;
}

export default function App() {
  return (
    <DataProvider>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/devices" element={<DevicesPage />} />
          <Route path="/events" element={<EventsPage />} />
          <Route path="/sensing" element={<SensingPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </DataProvider>
  );
}
