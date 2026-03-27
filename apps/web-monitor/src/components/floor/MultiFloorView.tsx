import { useState, useMemo } from 'react';
import { useZoneStore, type Zone } from '@/stores/zoneStore';
import FloorView from './FloorView';
import { cn } from '@/lib/utils';

/**
 * MultiFloorView — Phase 8-2
 *
 * 멀티층 건물 뷰: B1 / 1F / 2F / 3F 탭 선택 + 층별 FloorView.
 * - 각 탭에 해당 층 재실 인원 배지 표시
 * - zoneStore의 zone.floor 필드로 필터링
 * - 다크모드 전용
 */

const FLOORS = ['B1', '1F', '2F', '3F'] as const;
type FloorKey = (typeof FLOORS)[number];

const FLOOR_LABELS: Record<FloorKey, string> = {
  B1: '지하 1층',
  '1F': '1층',
  '2F': '2층',
  '3F': '3층',
};

function FloorBadge({ count }: { count: number }) {
  if (count === 0)
    return (
      <span className="ml-1.5 inline-flex items-center justify-center rounded-full bg-gray-700 px-1.5 py-0.5 text-[10px] font-semibold text-gray-400">
        0
      </span>
    );
  return (
    <span
      className={cn(
        'ml-1.5 inline-flex items-center justify-center rounded-full px-1.5 py-0.5 text-[10px] font-semibold',
        count <= 2 ? 'bg-emerald-900 text-emerald-300' : 'bg-orange-900 text-orange-300',
      )}
    >
      {count}
    </span>
  );
}

/** 층별 재실 인원 합산 */
function useFloorPresence(zones: Zone[]): Record<FloorKey, number> {
  return useMemo(() => {
    const acc: Record<FloorKey, number> = { B1: 0, '1F': 0, '2F': 0, '3F': 0 };
    for (const z of zones) {
      const floor = z.floor as FloorKey | undefined;
      if (floor !== undefined && floor in acc) {
        acc[floor] += z.presenceCount ?? 0;
      }
    }
    return acc;
  }, [zones]);
}

interface MultiFloorViewProps {
  /** 기본 선택 층 (기본값: '1F') */
  defaultFloor?: FloorKey;
  className?: string;
}

export default function MultiFloorView({
  defaultFloor = '1F',
  className,
}: MultiFloorViewProps) {
  const zones = useZoneStore((s) => s.zones);
  const [activeFloor, setActiveFloor] = useState<FloorKey>(defaultFloor);
  const floorPresence = useFloorPresence(zones);

  const totalPresence = useMemo(
    () => Object.values(floorPresence).reduce((s, n) => s + n, 0),
    [floorPresence],
  );

  return (
    <div className={cn('flex flex-col gap-3', className)}>
      {/* 탭 바 */}
      <div className="flex items-center gap-1 rounded-xl bg-gray-900 p-1">
        {FLOORS.map((floor) => {
          const active = floor === activeFloor;
          const count = floorPresence[floor];
          return (
            <button
              key={floor}
              type="button"
              onClick={() => setActiveFloor(floor)}
              className={cn(
                'flex flex-1 items-center justify-center gap-0.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                active
                  ? 'bg-gray-800 text-cyan-400 shadow-sm'
                  : 'text-gray-500 hover:text-gray-300 hover:bg-gray-800/50',
              )}
              aria-pressed={active}
              aria-label={`${FLOOR_LABELS[floor]} — 재실 ${count}명`}
            >
              <span className="hidden sm:inline">{FLOOR_LABELS[floor]}</span>
              <span className="sm:hidden">{floor}</span>
              <FloorBadge count={count} />
            </button>
          );
        })}

        {/* 전체 재실 요약 */}
        <div className="ml-2 hidden md:flex items-center gap-1 text-xs text-gray-500 shrink-0">
          <span>전체</span>
          <span
            className={cn(
              'font-bold',
              totalPresence > 0 ? 'text-emerald-400' : 'text-gray-600',
            )}
          >
            {totalPresence}명
          </span>
        </div>
      </div>

      {/* 층 설명 */}
      <div className="flex items-center gap-2 text-xs text-gray-500 px-1">
        <span className="text-gray-400 font-medium">{FLOOR_LABELS[activeFloor]}</span>
        <span>—</span>
        <span>
          재실{' '}
          <span
            className={cn(
              'font-semibold',
              floorPresence[activeFloor] > 0 ? 'text-emerald-400' : 'text-gray-600',
            )}
          >
            {floorPresence[activeFloor]}명
          </span>
        </span>
        <span>·</span>
        <span>
          존{' '}
          {zones.filter((z) => (z.floor ?? '1F') === activeFloor).length}개
        </span>
      </div>

      {/* 평면도 */}
      <FloorView />
    </div>
  );
}
