import { useEffect, useRef } from 'react';
import { supabase, isSupabaseEnabled } from '@/lib/supabase';
import { useEventStore, type DetectionEvent } from '@/stores/eventStore';
import { useAlertStore, type AlertItem } from '@/stores/alertStore';
import type { RealtimeChannel } from '@supabase/supabase-js';

/**
 * Syncs fall events to Supabase `fall_events` table and subscribes
 * to real-time updates from other clients.
 * No-ops gracefully when VITE_SUPABASE_URL is not set.
 */
export function useSupabaseSync() {
  const events = useEventStore((s) => s.events);
  const addEvent = useEventStore((s) => s.addEvent);
  const addAlert = useAlertStore((s) => s.addAlert);

  // Track which event IDs have already been synced to avoid duplicates
  const syncedIds = useRef<Set<string>>(new Set());
  const channelRef = useRef<RealtimeChannel | null>(null);

  // Push new fall events to Supabase
  useEffect(() => {
    if (!isSupabaseEnabled || !supabase) return;

    const fallEvents = events.filter(
      (e) =>
        (e.type === 'fall_confirmed' || e.type === 'fall_suspected') &&
        !syncedIds.current.has(e.id),
    );

    for (const event of fallEvents) {
      syncedIds.current.add(event.id);
      void supabase
        .from('fall_events')
        .insert({
          id: event.id,
          type: event.type,
          severity: event.severity,
          zone: event.zone,
          device_id: event.deviceId,
          confidence: event.confidence,
          timestamp: event.timestamp,
          metadata: event.metadata ?? null,
        })
        .then(({ error }) => {
          if (error) {
            console.warn('[Supabase] insert error:', error.message);
          }
        });
    }
  }, [events]);

  // Subscribe to real-time fall_events from other clients
  useEffect(() => {
    if (!isSupabaseEnabled || !supabase) return;

    const channel = supabase
      .channel('fall_events_realtime')
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'fall_events' },
        (payload) => {
          const row = payload.new as Record<string, unknown>;
          if (!row || typeof row.id !== 'string') return;

          // Avoid re-adding events we ourselves pushed
          if (syncedIds.current.has(row.id)) return;
          syncedIds.current.add(row.id);

          const event: DetectionEvent = {
            id: row.id,
            type: (row.type as DetectionEvent['type']) ?? 'fall_confirmed',
            severity: (row.severity as DetectionEvent['severity']) ?? 'critical',
            zone: typeof row.zone === 'string' ? row.zone : '',
            deviceId: typeof row.device_id === 'string' ? row.device_id : '',
            confidence: typeof row.confidence === 'number' ? row.confidence : 1,
            timestamp: typeof row.timestamp === 'string' ? row.timestamp : new Date().toISOString(),
            metadata: row.metadata as Record<string, unknown> | undefined,
          };

          addEvent(event);

          const alert: AlertItem = {
            id: `supa-${event.id}`,
            event_type: event.type,
            message: `[원격] 낙상 감지 — 구역 ${event.zone} (신뢰도 ${Math.round(event.confidence * 100)}%)`,
            severity: event.severity,
            metadata: event.metadata ?? {},
            timestamp: event.timestamp,
          };
          addAlert(alert);
        },
      )
      .subscribe();

    channelRef.current = channel;

    return () => {
      if (channelRef.current && supabase) {
        void supabase.removeChannel(channelRef.current);
        channelRef.current = null;
      }
    };
  }, [addEvent, addAlert]);
}
