import { create } from 'zustand';

export type EventType =
  | 'presence_detected'
  | 'motion_active'
  | 'stationary_detected'
  | 'fall_suspected'
  | 'fall_confirmed'
  | 'zone_intrusion'
  | 'device_offline'
  | 'signal_weak';

export type Severity = 'info' | 'warning' | 'critical';

export interface DetectionEvent {
  id: string;
  type: EventType;
  severity: Severity;
  zone: string;
  deviceId: string;
  confidence: number;
  timestamp: string;
  metadata?: Record<string, unknown>;
}

interface EventState {
  events: DetectionEvent[];
  maxEvents: number;
  addEvent: (event: DetectionEvent) => void;
  clearEvents: () => void;
}

export const useEventStore = create<EventState>((set) => ({
  events: [],
  maxEvents: 100,
  addEvent: (event) =>
    set((state) => ({
      events: [event, ...state.events].slice(0, state.maxEvents),
    })),
  clearEvents: () => set({ events: [] }),
}));
