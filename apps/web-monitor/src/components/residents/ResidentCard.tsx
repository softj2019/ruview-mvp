import type { Resident } from '@/stores/residentStore';

const CONDITION_COLORS: Record<string, string> = {
  당뇨: 'bg-yellow-900/50 text-yellow-300 border border-yellow-700',
  고혈압: 'bg-red-900/50 text-red-300 border border-red-700',
  낙상위험: 'bg-orange-900/50 text-orange-300 border border-orange-700',
  치매: 'bg-purple-900/50 text-purple-300 border border-purple-700',
  심장질환: 'bg-pink-900/50 text-pink-300 border border-pink-700',
};

const DEFAULT_TAG_COLOR = 'bg-gray-800 text-gray-300 border border-gray-700';

interface ResidentCardProps {
  resident: Resident;
  zoneName?: string;
  lastSeen?: string;
  onEdit?: (id: string) => void;
  onRemove?: (id: string) => void;
}

export function ResidentCard({ resident, zoneName, lastSeen, onEdit, onRemove }: ResidentCardProps) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 p-4 space-y-3">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-white">{resident.name}</h3>
          <p className="text-xs text-gray-400">
            호실 {resident.roomNumber}
            {zoneName ? ` · ${zoneName}` : ''}
          </p>
        </div>
        <span
          className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${
            resident.active
              ? 'bg-green-900/50 text-green-300 border border-green-700'
              : 'bg-gray-800 text-gray-500 border border-gray-700'
          }`}
        >
          {resident.active ? '활성' : '비활성'}
        </span>
      </div>

      {/* Condition tags */}
      {resident.conditions.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {resident.conditions.map((c) => (
            <span
              key={c}
              className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                CONDITION_COLORS[c] ?? DEFAULT_TAG_COLOR
              }`}
            >
              {c}
            </span>
          ))}
        </div>
      )}

      {/* Last seen */}
      {lastSeen && (
        <p className="text-[10px] text-gray-500">
          마지막 감지:{' '}
          {new Date(lastSeen).toLocaleString('ko-KR', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
          })}
        </p>
      )}

      {/* Re-ID badge */}
      {resident.reIdEmbedding && (
        <p className="text-[10px] text-cyan-500">AETHER Re-ID 연결됨</p>
      )}

      {/* Emergency contact */}
      {resident.emergencyContact && (
        <p className="text-[10px] text-gray-500">
          비상연락처: {resident.emergencyContact}
        </p>
      )}

      {/* Actions */}
      {(onEdit || onRemove) && (
        <div className="flex gap-2 pt-1">
          {onEdit && (
            <button
              onClick={() => onEdit(resident.id)}
              className="text-xs text-cyan-400 hover:text-cyan-300 transition-colors"
            >
              수정
            </button>
          )}
          {onRemove && (
            <button
              onClick={() => onRemove(resident.id)}
              className="text-xs text-red-400 hover:text-red-300 transition-colors"
            >
              삭제
            </button>
          )}
        </div>
      )}
    </div>
  );
}
