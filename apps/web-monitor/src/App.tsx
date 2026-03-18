import { useEffect } from 'react';
import { Routes, Route } from 'react-router-dom';
import DashboardPage from './pages/DashboardPage';
import DevicesPage from './pages/DevicesPage';
import EventsPage from './pages/EventsPage';
import SettingsPage from './pages/SettingsPage';
import Layout from './components/Layout';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useDeviceStore } from '@/stores/deviceStore';
import { useZoneStore } from '@/stores/zoneStore';
import { useEventStore } from '@/stores/eventStore';
import { useSignalStore } from '@/stores/signalStore';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8001/ws/events';

function DataProvider({ children }: { children: React.ReactNode }) {
  const setDevices = useDeviceStore((s) => s.setDevices);
  const setZones = useZoneStore((s) => s.setZones);
  const addEvent = useEventStore((s) => s.addEvent);
  const addSignalPoint = useSignalStore((s) => s.addPoint);

  const { send } = useWebSocket({
    url: WS_URL,
    onMessage: (data: unknown) => {
      const msg = data as { type: string; payload: Record<string, unknown> };
      switch (msg.type) {
        case 'init':
          setDevices(msg.payload.devices as never[]);
          setZones(msg.payload.zones as never[]);
          break;
        case 'event':
          addEvent(msg.payload as never);
          break;
        case 'signal':
          addSignalPoint(msg.payload as never);
          break;
        case 'device_update':
          setDevices(msg.payload.devices as never[]);
          break;
        case 'zone_update':
          setZones(msg.payload.zones as never[]);
          break;
      }
    },
    onOpen: () => console.log('[WS] Connected to', WS_URL),
    onClose: () => console.log('[WS] Disconnected'),
  });

  return <>{children}</>;
}

export default function App() {
  return (
    <DataProvider>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/devices" element={<DevicesPage />} />
          <Route path="/events" element={<EventsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </DataProvider>
  );
}
