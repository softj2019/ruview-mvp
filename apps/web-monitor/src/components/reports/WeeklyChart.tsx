interface DayData {
  date: string;
  falls: number;
  maxOccupancy: number;
}

interface WeeklyChartProps {
  days: DayData[];
}

const CHART_W = 560;
const CHART_H = 160;
const PAD_LEFT = 36;
const PAD_RIGHT = 12;
const PAD_TOP = 12;
const PAD_BOTTOM = 40;

const INNER_W = CHART_W - PAD_LEFT - PAD_RIGHT;
const INNER_H = CHART_H - PAD_TOP - PAD_BOTTOM;

const FALL_COLOR = '#f87171';
const OCC_COLOR = '#818cf8';

export default function WeeklyChart({ days }: WeeklyChartProps) {
  if (days.length === 0) return null;

  const maxFalls = Math.max(...days.map((d) => d.falls), 1);
  const maxOcc = Math.max(...days.map((d) => d.maxOccupancy), 1);
  const maxVal = Math.max(maxFalls, maxOcc, 4);

  const n = days.length;
  const slotW = INNER_W / n;
  const barW = Math.min(slotW * 0.35, 20);

  // Y-axis ticks
  const tickCount = 4;
  const ticks = Array.from({ length: tickCount + 1 }, (_, i) => {
    const val = Math.round((maxVal / tickCount) * i);
    const y = PAD_TOP + INNER_H - (val / maxVal) * INNER_H;
    return { val, y };
  });

  return (
    <div className="overflow-x-auto">
      <svg
        width={CHART_W}
        height={CHART_H}
        viewBox={`0 0 ${CHART_W} ${CHART_H}`}
        className="min-w-full"
        style={{ fontFamily: 'inherit' }}
      >
        {/* Grid lines */}
        {ticks.map(({ val, y }) => (
          <g key={val}>
            <line
              x1={PAD_LEFT}
              y1={y}
              x2={CHART_W - PAD_RIGHT}
              y2={y}
              stroke="#374151"
              strokeWidth="0.5"
              strokeDasharray="4 4"
            />
            <text
              x={PAD_LEFT - 4}
              y={y}
              textAnchor="end"
              dominantBaseline="middle"
              fill="#6b7280"
              fontSize="10"
            >
              {val}
            </text>
          </g>
        ))}

        {/* Bars */}
        {days.map((day, i) => {
          const cx = PAD_LEFT + slotW * i + slotW / 2;
          const fallBarH = (day.falls / maxVal) * INNER_H;
          const occBarH = (day.maxOccupancy / maxVal) * INNER_H;
          const fallX = cx - barW - 2;
          const occX = cx + 2;
          const baseY = PAD_TOP + INNER_H;

          return (
            <g key={day.date}>
              {/* Fall bar */}
              <rect
                x={fallX}
                y={baseY - fallBarH}
                width={barW}
                height={fallBarH}
                fill={FALL_COLOR}
                fillOpacity="0.85"
                rx="2"
              />
              {/* Occupancy bar */}
              <rect
                x={occX}
                y={baseY - occBarH}
                width={barW}
                height={occBarH}
                fill={OCC_COLOR}
                fillOpacity="0.85"
                rx="2"
              />
              {/* X label */}
              <text
                x={cx}
                y={baseY + 14}
                textAnchor="middle"
                fill="#9ca3af"
                fontSize="10"
              >
                {day.date}
              </text>
              {/* Value labels */}
              {day.falls > 0 && (
                <text
                  x={fallX + barW / 2}
                  y={baseY - fallBarH - 3}
                  textAnchor="middle"
                  fill={FALL_COLOR}
                  fontSize="9"
                  fontWeight="600"
                >
                  {day.falls}
                </text>
              )}
            </g>
          );
        })}

        {/* Axes */}
        <line x1={PAD_LEFT} y1={PAD_TOP} x2={PAD_LEFT} y2={PAD_TOP + INNER_H} stroke="#4b5563" strokeWidth="1" />
        <line x1={PAD_LEFT} y1={PAD_TOP + INNER_H} x2={CHART_W - PAD_RIGHT} y2={PAD_TOP + INNER_H} stroke="#4b5563" strokeWidth="1" />
      </svg>

      {/* Legend */}
      <div className="flex items-center gap-4 mt-2 px-1">
        <div className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-sm" style={{ background: FALL_COLOR }} />
          <span className="text-xs text-gray-400">낙상 이벤트</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-sm" style={{ background: OCC_COLOR }} />
          <span className="text-xs text-gray-400">최대 재실 인원</span>
        </div>
      </div>
    </div>
  );
}
