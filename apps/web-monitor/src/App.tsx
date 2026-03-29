import { useCallback } from 'react';
import { Routes, Route } from 'react-router-dom';
import DashboardPage from './pages/DashboardPage';
import DevicesPage from './pages/DevicesPage';
import EventsPage from './pages/EventsPage';
import SensingPage from './pages/SensingPage';
import SettingsPage from './pages/SettingsPage';
import PoseFusionPage from './pages/PoseFusionPage';
import HardwarePage from './pages/HardwarePage';
import LiveDemoPage from './pages/LiveDemoPage';
import ObservatoryPage from './pages/ObservatoryPage';
import VizPage from './pages/VizPage';
import BuildingPage from './pages/BuildingPage';
import ResidentsPage from './pages/ResidentsPage';
import ReportsPage from './pages/ReportsPage';
import RFTomographyPage from './pages/RFTomographyPage';
import PositionPage from './pages/PositionPage';
import SleepPage from './pages/SleepPage';
import AnalyticsPage from './pages/AnalyticsPage';
import WifiPosePage from './pages/WifiPosePage';
import AppShell from './components/layout/AppShell';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useDeviceStore } from '@/stores/deviceStore';
import { useZoneStore } from '@/stores/zoneStore';
import { useEventStore } from '@/stores/eventStore';
import { useSignalStore } from '@/stores/signalStore';
import { useAlertStore } from '@/stores/alertStore';
import AlertToast from '@/components/alerts/AlertToast';
import FallAlertBanner from '@/components/alerts/FallAlertBanner';
import type { WSMessage } from '@/types/ws-contract';

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
  const addAlert = useAlertStore((s) => s.addAlert);

  const handleMessage = useCallback(
    (data: unknown) => {
      const raw = data as Record<string, unknown>;
      if (!raw || typeof raw.type !== 'string') return;
      const msg = raw as WSMessage;
      switch (msg.type) {
        case 'init':
          if (msg.payload.devices) setDevices(msg.payload.devices);
          if (msg.payload.zones) setZones(msg.payload.zones);
          break;
        case 'event':
          addEvent(msg.payload);
          break;
        case 'signal':
          addSignalPoint(msg.payload);
          break;
        case 'device_update':
          setDevices(msg.payload.devices);
          break;
        case 'zone_update':
          setZones(msg.payload.zones);
          break;
        case 'vitals':
          useDeviceStore.getState().updateDevice(msg.payload.device_id, {
            breathing_bpm: msg.payload.breathing_rate_bpm,
            heart_rate: msg.payload.heart_rate_bpm,
            motion_energy: msg.payload.motion_energy,
            presence_score: msg.payload.presence_score,
            n_persons: msg.payload.n_persons,
          });
          break;
        case 'camera_detection':
          if (msg.payload.detections) {
            for (const det of msg.payload.detections) {
              if (det.device_id && det.pose !== undefined) {
                useDeviceStore.getState().updateDevice(det.device_id, {
                  pose: det.pose,
                  pose_confidence: det.pose_confidence,
                });
              }
            }
          }
          break;
        case 'pose_update':
          for (const p of msg.payload.poses) {
            if (p.device_id) {
              useDeviceStore.getState().updateDevice(p.device_id, {
                pose: p.pose,
                pose_confidence: p.pose_confidence,
              });
            }
          }
          break;
        case 'alert':
          addAlert(msg.payload);
          break;
        default: {
          const _exhaustive: never = msg;
          console.warn('[WS] Unhandled message type:', (_exhaustive as Record<string, unknown>).type);
        }
      }
    },
    [setDevices, setZones, addEvent, addSignalPoint, addAlert],
  );

  useWebSocket({
    url: WS_URL,
    onMessage: handleMessage,
    onOpen: () => console.log('[WS] Connected to', WS_URL),
    onClose: () => console.log('[WS] Disconnected'),
  });

  return (
    <>
      <AlertToast />
      <FallAlertBanner />
      {children}
    </>
  );
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
          <Route path="/pose-fusion" element={<PoseFusionPage />} />
          <Route path="/hardware" element={<HardwarePage />} />
          <Route path="/live-demo" element={<LiveDemoPage />} />
          <Route path="/observatory" element={<ObservatoryPage />} />
          <Route path="/viz" element={<VizPage />} />
          <Route path="/building" element={<BuildingPage />} />
          <Route path="/residents" element={<ResidentsPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/rf-tomography" element={<RFTomographyPage />} />
          <Route path="/position" element={<PositionPage />} />
          <Route path="/sleep" element={<SleepPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="/wifi-pose" element={<WifiPosePage />} />
        </Route>
      </Routes>
    </DataProvider>
  );
}
