import { create } from 'zustand';

export interface Device {
  id: string;
  name: string;
  mac: string;
  status: 'online' | 'offline' | 'error';
  x: number;
  y: number;
  signalStrength: number | null;
  lastSeen: string;
  firmwareVersion: string;
  motion_energy?: number;
  presence_score?: number;
  n_persons?: number;
  breathing_bpm?: number;
  heart_rate?: number;
  csi_breathing_bpm?: number;
  csi_heart_rate?: number;
  zone_id?: string;
}

interface DeviceState {
  devices: Device[];
  selectedId: string | null;
  setDevices: (devices: Device[]) => void;
  updateDevice: (id: string, partial: Partial<Device>) => void;
  selectDevice: (id: string | null) => void;
}

export const useDeviceStore = create<DeviceState>((set) => ({
  devices: [],
  selectedId: null,
  setDevices: (devices) => set({ devices }),
  updateDevice: (id, partial) =>
    set((state) => ({
      devices: state.devices.map((d) => (d.id === id ? { ...d, ...partial } : d)),
    })),
  selectDevice: (id) => set({ selectedId: id }),
}));
