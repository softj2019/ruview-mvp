import { useCallback } from 'react';
import { Routes, Route } from 'react-router-dom';
import DashboardPage from './pages/DashboardPage';
import DevicesPage from './pages/DevicesPage';
import EventsPage from './pages/EventsPage';
import SettingsPage from './pages/SettingsPage';
import AppShell from './components/layout/AppShell';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useDeviceStore } from '@/stores/deviceStore';
import { useZoneStore } from '@/stores/zoneStore';
import { useEventStore } from '@/stores/eventStore';
import { useSignalStore } from '@/stores/signalStore';

function getWsUrl(): string {
  if (import.meta.env.VITE_WS_URL) return import.meta.env.VITE_WS_URL;
  const { hostname } = window.location;
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return 'ws://localhost:8001/ws/events';
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
          if (msg.payload.devices) setDevices(msg.payload.devices as never[]);
          if (msg.payload.zones) setZones(msg.payload.zones as never[]);
          break;
        case 'event':
          addEvent(msg.payload as never);
          break;
        case 'signal':
          addSignalPoint(msg.payload as never);
          break;
        case 'device_update':
          if (msg.payload.devices) setDevices(msg.payload.devices as never[]);
          break;
        case 'zone_update':
          if (msg.payload.zones) setZones(msg.payload.zones as never[]);
          break;
        case 'vitals':
          // vitals payload does not match SignalPoint schema; observatory consumes it via its own WS
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
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </DataProvider>
  );
}
