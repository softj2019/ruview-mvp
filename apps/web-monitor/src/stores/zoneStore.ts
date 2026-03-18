import { create } from 'zustand';

export interface Point {
  x: number;
  y: number;
}

export interface Zone {
  id: string;
  name: string;
  polygon: Point[];
  status: 'active' | 'inactive' | 'alert';
  presenceCount: number;
  lastActivity: string | null;
}

interface ZoneState {
  zones: Zone[];
  setZones: (zones: Zone[]) => void;
  updateZone: (id: string, partial: Partial<Zone>) => void;
}

export const useZoneStore = create<ZoneState>((set) => ({
  zones: [],
  setZones: (zones) => set({ zones }),
  updateZone: (id, partial) =>
    set((state) => ({
      zones: state.zones.map((z) => (z.id === id ? { ...z, ...partial } : z)),
    })),
}));
