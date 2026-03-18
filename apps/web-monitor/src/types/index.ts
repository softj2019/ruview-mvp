export type { Device } from '@/stores/deviceStore';
export type { Zone, Point } from '@/stores/zoneStore';
export type { DetectionEvent, EventType, Severity } from '@/stores/eventStore';
export type { SignalPoint } from '@/stores/signalStore';

export interface ApiResponse<T> {
  data: T;
  error: string | null;
  timestamp: string;
}

export interface WebSocketMessage {
  type: 'device_update' | 'event' | 'signal' | 'zone_update';
  payload: Record<string, unknown>;
  timestamp: string;
}
