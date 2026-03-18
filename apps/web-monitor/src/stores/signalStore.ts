import { create } from 'zustand';

export interface SignalPoint {
  time: string;
  rssi: number;
  snr: number;
  csi_amplitude: number;
}

interface SignalState {
  history: SignalPoint[];
  maxHistory: number;
  addPoint: (point: SignalPoint) => void;
}

export const useSignalStore = create<SignalState>((set) => ({
  history: [],
  maxHistory: 300,
  addPoint: (point) =>
    set((state) => ({
      history: [...state.history, point].slice(-state.maxHistory),
    })),
}));
