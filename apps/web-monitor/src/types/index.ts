export type { Device } from '@/stores/deviceStore';
export type { Zone, Point } from '@/stores/zoneStore';
export type { DetectionEvent, EventType, Severity } from '@/stores/eventStore';
export type { SignalPoint } from '@/stores/signalStore';
export type { WSMessage, VitalsPayload, CameraDetectionPayload } from './ws-contract';

export interface ApiResponse<T> {
  data: T;
  error: string | null;
  timestamp: string;
}
