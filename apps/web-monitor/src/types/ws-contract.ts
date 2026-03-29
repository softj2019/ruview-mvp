/**
 * WebSocket message payload type contract
 *
 * Single source of truth for all WS message types exchanged between
 * signal-adapter (Python) and web-monitor / observatory (TypeScript/JS).
 *
 * Server sends: { type: string, payload: object }
 * Source: services/signal-adapter/main.py — broadcast() calls
 */

import type { Device } from '@/stores/deviceStore';
import type { Zone } from '@/stores/zoneStore';
import type { DetectionEvent } from '@/stores/eventStore';
import type { SignalPoint } from '@/stores/signalStore';
import type { AlertItem } from '@/stores/alertStore';

// ── Vitals ──────────────────────────────────────────────────────────────────

/**
 * Emitted per-node on every vitals UDP frame (VITALS_MAGIC 0xC5110002).
 * Fields mirror vitals_payload in main.py handle_vitals_frame().
 */
export interface VitalsPayload {
  device_id: string;
  breathing_rate_bpm: number;
  heart_rate_bpm: number;
  motion_energy: number;
  /** WiFi CSI presence score. Reliable signal: ≥0.15. Noise level: <0.05. */
  presence_score: number;
  /** CSI-estimated person count (requires calibration). */
  n_persons: number;
  /**
   * Status flags bitmask:
   *   bit 0 (0x01) — fall suspected
   *   bit 1 (0x02) — fall suspected (broadcast trigger)
   *   bit 2 (0x04) — signal quality warning
   */
  flags: number;
}

// ── Camera detection ─────────────────────────────────────────────────────────

export interface CameraDetectionPayload {
  device_id?: string;
  persons?: Array<{
    id: string;
    pose: string;
    pose_confidence: number;
    bbox?: [number, number, number, number];
  }>;
  detections?: Array<{
    pose?: string;
    pose_confidence?: number;
    device_id?: string;
    [key: string]: unknown;
  }>;
  person_count?: number;
  timestamp?: string;
}

// ── Pose update ───────────────────────────────────────────────────────────────

/**
 * Emitted by signal-adapter after camera+CSI pose fusion.
 * Payload contains fused pose results per detected person.
 */
export interface PoseUpdatePayload {
  poses: Array<{
    pose: string;
    pose_confidence: number;
    device_id: string | null;
    camera_pose?: string;
    csi_pose?: string;
    [key: string]: unknown;
  }>;
}

// ── Discriminated union ──────────────────────────────────────────────────────

/**
 * All WebSocket messages from signal-adapter, keyed by `type`.
 * Use this in onmessage handlers to get exhaustive type narrowing.
 */
export type WSMessage =
  | { type: 'init'; payload: { devices?: Device[]; zones?: Zone[] } }
  | { type: 'device_update'; payload: { devices: Device[] } }
  | { type: 'zone_update'; payload: { zones: Zone[] } }
  | { type: 'signal'; payload: SignalPoint }
  | { type: 'vitals'; payload: VitalsPayload }
  | { type: 'event'; payload: DetectionEvent }
  | { type: 'camera_detection'; payload: CameraDetectionPayload }
  | { type: 'pose_update'; payload: PoseUpdatePayload }
  | { type: 'alert'; payload: AlertItem };
