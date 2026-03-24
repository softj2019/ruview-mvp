import { useEffect, useCallback, useRef } from 'react';
import { useAlertStore, type AlertItem, type AlertSeverity } from '@/stores/alertStore';

const SEVERITY_COLORS: Record<AlertSeverity, { bg: string; border: string; text: string }> = {
  critical: { bg: '#fef2f2', border: '#ef4444', text: '#991b1b' },
  warning: { bg: '#fffbeb', border: '#f59e0b', text: '#92400e' },
  info: { bg: '#eff6ff', border: '#3b82f6', text: '#1e40af' },
};

const SEVERITY_LABELS: Record<AlertSeverity, string> = {
  critical: 'CRITICAL',
  warning: 'WARNING',
  info: 'INFO',
};

const AUTO_DISMISS_MS = 5000;

/** Play a short 800 Hz beep using the Web Audio API (critical alerts only). */
function playBeep() {
  try {
    const ctx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(800, ctx.currentTime);
    gain.gain.setValueAtTime(0.3, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.2);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.2);
    // Clean up after sound finishes
    setTimeout(() => ctx.close(), 500);
  } catch {
    // Web Audio API not available — silently skip
  }
}

function ToastItem({ alert, onDismiss }: { alert: AlertItem; onDismiss: (id: string) => void }) {
  const colors = SEVERITY_COLORS[alert.severity] || SEVERITY_COLORS.info;
  const label = SEVERITY_LABELS[alert.severity] || 'INFO';

  useEffect(() => {
    const timer = setTimeout(() => onDismiss(alert.id), AUTO_DISMISS_MS);
    return () => clearTimeout(timer);
  }, [alert.id, onDismiss]);

  return (
    <div
      style={{
        background: colors.bg,
        border: `2px solid ${colors.border}`,
        borderRadius: '8px',
        padding: '12px 16px',
        marginBottom: '8px',
        boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
        minWidth: '300px',
        maxWidth: '420px',
        animation: 'slideInRight 0.3s ease-out',
        cursor: 'pointer',
        position: 'relative',
      }}
      onClick={() => onDismiss(alert.id)}
      role="alert"
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
        <span
          style={{
            fontSize: '11px',
            fontWeight: 700,
            color: colors.border,
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
          }}
        >
          {label}
        </span>
        <span style={{ fontSize: '11px', color: '#9ca3af' }}>
          {new Date(alert.timestamp).toLocaleTimeString()}
        </span>
      </div>
      <div style={{ fontSize: '13px', fontWeight: 600, color: colors.text, marginBottom: '2px' }}>
        {alert.event_type.replace(/_/g, ' ')}
      </div>
      <div style={{ fontSize: '12px', color: '#6b7280' }}>
        {alert.message}
      </div>
    </div>
  );
}

/**
 * AlertToast — renders toast popups at top-right of screen.
 *
 * This component should be rendered once globally (e.g., inside DataProvider).
 * It listens to the alertStore for new alerts, plays a beep for critical ones,
 * and auto-dismisses after 5 seconds. Stacks up to 3 toasts.
 */
export default function AlertToast() {
  const alerts = useAlertStore((s) => s.alerts);
  const removeAlert = useAlertStore((s) => s.removeAlert);
  const prevCountRef = useRef(0);

  // Play beep when a new critical alert arrives
  useEffect(() => {
    if (alerts.length > prevCountRef.current) {
      const newest = alerts[0];
      if (newest && newest.severity === 'critical') {
        playBeep();
      }
    }
    prevCountRef.current = alerts.length;
  }, [alerts]);

  const handleDismiss = useCallback(
    (id: string) => removeAlert(id),
    [removeAlert],
  );

  if (alerts.length === 0) return null;

  return (
    <>
      {/* Inject keyframe animation */}
      <style>{`
        @keyframes slideInRight {
          from { transform: translateX(100%); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
      `}</style>
      <div
        style={{
          position: 'fixed',
          top: '16px',
          right: '16px',
          zIndex: 9999,
          pointerEvents: 'auto',
        }}
      >
        {alerts.map((alert) => (
          <ToastItem key={alert.id} alert={alert} onDismiss={handleDismiss} />
        ))}
      </div>
    </>
  );
}
