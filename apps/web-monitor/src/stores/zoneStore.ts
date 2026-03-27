import { create } from 'zustand';

export interface Point {
  x: number;
  y: number;
}

export interface Zone {
  id: string;
  name: string;
  polygon: Point[];
  /** 층 식별자 (B1 / 1F / 2F / 3F). 기본값: '1F' */
  floor?: string;
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
