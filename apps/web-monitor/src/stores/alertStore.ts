import { create } from 'zustand';

export type AlertSeverity = 'info' | 'warning' | 'critical';

export interface AlertItem {
  id: string;
  event_type: string;
  message: string;
  severity: AlertSeverity;
  metadata: Record<string, unknown>;
  timestamp: string;
  /** Internal: auto-dismiss timer id */
  _timerId?: ReturnType<typeof setTimeout>;
}

interface AlertState {
  alerts: AlertItem[];
  maxVisible: number;
  addAlert: (alert: AlertItem) => void;
  removeAlert: (id: string) => void;
  clearAlerts: () => void;
}

export const useAlertStore = create<AlertState>((set) => ({
  alerts: [],
  maxVisible: 3,
  addAlert: (alert) =>
    set((state) => {
      // Stack up to maxVisible toasts; drop oldest if exceeded
      const next = [alert, ...state.alerts].slice(0, state.maxVisible);
      return { alerts: next };
    }),
  removeAlert: (id) =>
    set((state) => ({
      alerts: state.alerts.filter((a) => a.id !== id),
    })),
  clearAlerts: () => set({ alerts: [] }),
}));
