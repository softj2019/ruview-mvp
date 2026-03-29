// Zustand store for sleep monitoring
import { create } from 'zustand';

interface SleepDeviceStatus {
  id: string;
  sleep_stage: 'wake' | 'light' | 'deep' | 'rem' | 'unknown';
  apnea: boolean;
}

interface SleepState {
  stage: string;
  apneaEventsLastHour: number;
  devices: SleepDeviceStatus[];
  stageDistribution: Record<string, number>;
  setStatus: (data: Partial<SleepState>) => void;
}

export const useSleepStore = create<SleepState>((set) => ({
  stage: 'unknown',
  apneaEventsLastHour: 0,
  devices: [],
  stageDistribution: { wake: 0, light: 0, deep: 0, rem: 0 },
  setStatus: (data) => set((s) => ({ ...s, ...data })),
}));
