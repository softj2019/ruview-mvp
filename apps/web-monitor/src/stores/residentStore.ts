import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface Resident {
  id: string;
  name: string;
  roomNumber: string;
  zoneId: string;
  conditions: string[];
  notes: string;
  emergencyContact: string;
  createdAt: string;
  active: boolean;
  reIdEmbedding?: number[]; // from AETHER camera re-ID
}

interface ResidentState {
  residents: Resident[];
  addResident: (resident: Omit<Resident, 'id' | 'createdAt'>) => void;
  updateResident: (id: string, partial: Partial<Resident>) => void;
  removeResident: (id: string) => void;
  linkReId: (residentId: string, embedding: number[]) => void;
  getByZone: (zoneId: string) => Resident[];
}

export const useResidentStore = create<ResidentState>()(
  persist(
    (set, get) => ({
      residents: [],

      addResident: (data) =>
        set((state) => ({
          residents: [
            ...state.residents,
            {
              ...data,
              id: crypto.randomUUID(),
              createdAt: new Date().toISOString(),
            },
          ],
        })),

      updateResident: (id, partial) =>
        set((state) => ({
          residents: state.residents.map((r) =>
            r.id === id ? { ...r, ...partial } : r,
          ),
        })),

      removeResident: (id) =>
        set((state) => ({
          residents: state.residents.filter((r) => r.id !== id),
        })),

      linkReId: (residentId, embedding) =>
        set((state) => ({
          residents: state.residents.map((r) =>
            r.id === residentId ? { ...r, reIdEmbedding: embedding } : r,
          ),
        })),

      getByZone: (zoneId) =>
        get().residents.filter((r) => r.zoneId === zoneId),
    }),
    { name: 'ruview-residents' },
  ),
);
