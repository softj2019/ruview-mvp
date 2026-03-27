import { useMemo } from 'react';

export interface ZoneReport {
  zone: string;
  avgBreathing: number;
  avgHeartRate: number;
  fallCount: number;
  presenceHours: number;
  trend: 'up' | 'down' | 'stable';
  sparkline: number[]; // 24 data points
}

export interface DayReport {
  date: string;
  falls: number;
  maxOccupancy: number;
}

export interface ReportData {
  zones: ZoneReport[];
  days: DayReport[];
  generated: string;
}

const ZONE_NAMES = ['거실', '침실', '주방', '욕실'];

function seededRandom(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s * 1664525 + 1013904223) & 0xffffffff;
    return ((s >>> 0) / 0xffffffff);
  };
}

function generateSparkline(rng: () => number, base: number, variance: number): number[] {
  return Array.from({ length: 24 }, () => Math.round(base + (rng() - 0.5) * variance * 2));
}

export function useReportData(range: 'day' | 'week' | 'month'): ReportData {
  return useMemo(() => {
    const now = new Date();
    const seed = now.getFullYear() * 10000 + (now.getMonth() + 1) * 100 + now.getDate();
    const rng = seededRandom(seed);

    const zones: ZoneReport[] = ZONE_NAMES.map((name, i) => {
      const zoneRng = seededRandom(seed + i * 137);
      const avgBreathing = 14 + Math.round(zoneRng() * 6);
      const avgHeartRate = 62 + Math.round(zoneRng() * 20);
      const fallCount = i === 3 ? 0 : Math.floor(zoneRng() * 3);
      const presenceHours = range === 'day'
        ? Math.round(zoneRng() * 16 * 10) / 10
        : range === 'week'
          ? Math.round(zoneRng() * 80 * 10) / 10
          : Math.round(zoneRng() * 300 * 10) / 10;
      const trendRoll = zoneRng();
      const trend: 'up' | 'down' | 'stable' = trendRoll < 0.33 ? 'up' : trendRoll < 0.66 ? 'down' : 'stable';

      return {
        zone: name,
        avgBreathing,
        avgHeartRate,
        fallCount,
        presenceHours,
        trend,
        sparkline: generateSparkline(zoneRng, avgBreathing, 4),
      };
    });

    const dayCount = range === 'day' ? 1 : range === 'week' ? 7 : 30;
    const days: DayReport[] = Array.from({ length: dayCount }, (_, i) => {
      const d = new Date(now);
      d.setDate(d.getDate() - (dayCount - 1 - i));
      const dayRng = seededRandom(seed + i * 53);
      return {
        date: d.toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' }),
        falls: Math.floor(dayRng() * 4),
        maxOccupancy: 1 + Math.floor(dayRng() * 4),
      };
    });

    const generated = now.toLocaleString('ko-KR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });

    void rng; // suppress unused warning

    return { zones, days, generated };
  }, [range]);
}
