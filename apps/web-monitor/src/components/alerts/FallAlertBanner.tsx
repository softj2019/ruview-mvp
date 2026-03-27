import { useEffect, useCallback, useState, useRef } from 'react';
import { useEventStore, type DetectionEvent } from '@/stores/eventStore';

/**
 * FallAlertBanner — Phase 8-1
 *
 * 낙상 감지(fall_confirmed / fall_suspected) 이벤트 발생 시
 * 전체화면 붉은 배너를 표시합니다.
 *
 * - eventStore에서 fall 이벤트를 감시
 * - 확인 버튼 또는 배너 클릭으로 닫기
 * - fall_confirmed: 진한 빨간, fall_suspected: 주황
 * - 다크모드 전용 (bg-gray-950 기반)
 */

interface FallAlert {
  event: DetectionEvent;
  id: string;
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString('ko-KR', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return iso;
  }
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color =
    pct >= 80 ? 'bg-red-500' : pct >= 50 ? 'bg-orange-400' : 'bg-yellow-400';
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-gray-300 w-10 text-right">{pct}%</span>
      <div className="flex-1 h-2 rounded-full bg-gray-700 overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function BannerItem({
  alert,
  onDismiss,
}: {
  alert: FallAlert;
  onDismiss: (id: string) => void;
}) {
  const isConfirmed = alert.event.type === 'fall_confirmed';
  const borderColor = isConfirmed ? 'border-red-500' : 'border-orange-400';
  const headingColor = isConfirmed ? 'text-red-400' : 'text-orange-400';
  const bgColor = isConfirmed
    ? 'bg-red-950/90'
    : 'bg-orange-950/90';

  const handleDismiss = useCallback(() => onDismiss(alert.id), [alert.id, onDismiss]);

  return (
    <div
      className={`
        w-full max-w-lg rounded-xl border-2 ${borderColor} ${bgColor}
        shadow-2xl px-6 py-5 flex flex-col gap-3
        animate-[pulse_0.4s_ease-in-out_2]
      `}
      role="alertdialog"
      aria-modal="true"
      aria-label="낙상 감지 경고"
    >
      {/* 헤더 */}
      <div className="flex items-center gap-3">
        {/* 경보 아이콘 */}
        <span className={`text-3xl select-none ${headingColor}`}>
          {isConfirmed ? '🚨' : '⚠️'}
        </span>
        <div className="flex-1">
          <p className={`text-lg font-bold tracking-wide uppercase ${headingColor}`}>
            {isConfirmed ? '낙상 확인' : '낙상 의심'}
          </p>
          <p className="text-sm text-gray-400">
            {isConfirmed
              ? '낙상이 확인되었습니다. 즉시 확인하세요.'
              : '낙상 가능성이 감지되었습니다.'}
          </p>
        </div>
      </div>

      {/* 상세 정보 */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
        <span className="text-gray-500">구역</span>
        <span className="text-gray-100 font-semibold">{alert.event.zone}</span>

        <span className="text-gray-500">시각</span>
        <span className="text-gray-100">{formatTime(alert.event.timestamp)}</span>

        <span className="text-gray-500">신뢰도</span>
        <ConfidenceBar value={alert.event.confidence} />
      </div>

      {/* 확인 버튼 */}
      <button
        type="button"
        onClick={handleDismiss}
        className={`
          mt-1 w-full rounded-lg py-2.5 text-sm font-semibold
          transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-950
          ${isConfirmed
            ? 'bg-red-600 hover:bg-red-700 text-white focus:ring-red-500'
            : 'bg-orange-600 hover:bg-orange-700 text-white focus:ring-orange-500'
          }
        `}
      >
        확인
      </button>
    </div>
  );
}

/**
 * FallAlertBanner — 전역 1회 배치.
 * AppShell 또는 App 최상위에 렌더링합니다.
 *
 * 사용 예:
 *   <FallAlertBanner />
 */
export default function FallAlertBanner() {
  const events = useEventStore((s) => s.events);
  const [activeAlerts, setActiveAlerts] = useState<FallAlert[]>([]);
  const seenIds = useRef<Set<string>>(new Set());

  // eventStore에서 새로운 fall 이벤트 감지
  useEffect(() => {
    const fallEvents = events.filter(
      (e) =>
        (e.type === 'fall_confirmed' || e.type === 'fall_suspected') &&
        !seenIds.current.has(e.id),
    );

    if (fallEvents.length === 0) return;

    const newAlerts: FallAlert[] = fallEvents.map((e) => {
      seenIds.current.add(e.id);
      return { event: e, id: e.id };
    });

    setActiveAlerts((prev) => [...newAlerts, ...prev]);
  }, [events]);

  const handleDismiss = useCallback((id: string) => {
    setActiveAlerts((prev) => prev.filter((a) => a.id !== id));
  }, []);

  if (activeAlerts.length === 0) return null;

  return (
    <>
      {/* 반투명 오버레이 */}
      <div
        className="fixed inset-0 z-[9990] bg-black/60 backdrop-blur-sm"
        aria-hidden="true"
      />

      {/* 배너 컨테이너 */}
      <div
        className="
          fixed inset-0 z-[9991]
          flex flex-col items-center justify-center gap-4
          px-4 py-8 overflow-y-auto
        "
      >
        {/* 스택 상단 레드 스트라이프 */}
        <div className="w-full max-w-lg">
          <div className="h-1 w-full rounded-full bg-gradient-to-r from-red-600 via-orange-500 to-red-600 animate-pulse mb-4" />
        </div>

        {activeAlerts.map((alert) => (
          <BannerItem key={alert.id} alert={alert} onDismiss={handleDismiss} />
        ))}
      </div>
    </>
  );
}
