import { useState } from 'react';
import { useResidentStore } from '@/stores/residentStore';
import { useZoneStore } from '@/stores/zoneStore';
import { ResidentCard } from '@/components/residents/ResidentCard';

const PRESET_CONDITIONS = ['당뇨', '고혈압', '낙상위험', '치매', '심장질환', '천식'];

const emptyForm = {
  name: '',
  roomNumber: '',
  zoneId: '',
  conditions: [] as string[],
  notes: '',
  emergencyContact: '',
  active: true,
};

type FormState = typeof emptyForm;

export default function ResidentsPage() {
  const residents = useResidentStore((s) => s.residents);
  const addResident = useResidentStore((s) => s.addResident);
  const updateResident = useResidentStore((s) => s.updateResident);
  const removeResident = useResidentStore((s) => s.removeResident);
  const zones = useZoneStore((s) => s.zones);

  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [customCondition, setCustomCondition] = useState('');
  const [viewMode, setViewMode] = useState<'table' | 'card'>('table');

  function openAdd() {
    setEditingId(null);
    setForm(emptyForm);
    setShowForm(true);
  }

  function openEdit(id: string) {
    const r = residents.find((x) => x.id === id);
    if (!r) return;
    setEditingId(id);
    setForm({
      name: r.name,
      roomNumber: r.roomNumber,
      zoneId: r.zoneId,
      conditions: [...r.conditions],
      notes: r.notes,
      emergencyContact: r.emergencyContact,
      active: r.active,
    });
    setShowForm(true);
  }

  function closeForm() {
    setShowForm(false);
    setEditingId(null);
    setForm(emptyForm);
    setCustomCondition('');
  }

  function toggleCondition(c: string) {
    setForm((prev) => ({
      ...prev,
      conditions: prev.conditions.includes(c)
        ? prev.conditions.filter((x) => x !== c)
        : [...prev.conditions, c],
    }));
  }

  function addCustomCondition() {
    const val = customCondition.trim();
    if (!val || form.conditions.includes(val)) return;
    setForm((prev) => ({ ...prev, conditions: [...prev.conditions, val] }));
    setCustomCondition('');
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) return;
    if (editingId) {
      updateResident(editingId, form);
    } else {
      addResident(form);
    }
    closeForm();
  }

  const zoneName = (id: string) => zones.find((z) => z.id === id)?.name ?? id;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">입주자 관리</h1>
          <p className="text-sm text-gray-400 mt-0.5">
            등록된 입주자 {residents.length}명
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* View toggle */}
          <div className="flex rounded-lg border border-gray-700 overflow-hidden text-xs">
            <button
              onClick={() => setViewMode('table')}
              className={`px-3 py-1.5 transition-colors ${viewMode === 'table' ? 'bg-gray-700 text-white' : 'text-gray-400 hover:text-white'}`}
            >
              표
            </button>
            <button
              onClick={() => setViewMode('card')}
              className={`px-3 py-1.5 transition-colors ${viewMode === 'card' ? 'bg-gray-700 text-white' : 'text-gray-400 hover:text-white'}`}
            >
              카드
            </button>
          </div>
          <button
            onClick={openAdd}
            className="rounded-lg bg-cyan-600 hover:bg-cyan-500 px-4 py-2 text-sm font-medium text-white transition-colors"
          >
            + 입주자 추가
          </button>
        </div>
      </div>

      {/* Add/Edit Form */}
      {showForm && (
        <div className="rounded-xl border border-gray-700 bg-gray-900 p-5">
          <h2 className="text-sm font-semibold text-white mb-4">
            {editingId ? '입주자 수정' : '새 입주자 등록'}
          </h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              {/* Name */}
              <div>
                <label className="block text-xs text-gray-400 mb-1">이름 *</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                  required
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-cyan-500 focus:outline-none"
                  placeholder="홍길동"
                />
              </div>
              {/* Room */}
              <div>
                <label className="block text-xs text-gray-400 mb-1">호실 번호</label>
                <input
                  type="text"
                  value={form.roomNumber}
                  onChange={(e) => setForm((p) => ({ ...p, roomNumber: e.target.value }))}
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-cyan-500 focus:outline-none"
                  placeholder="101호"
                />
              </div>
              {/* Zone */}
              <div>
                <label className="block text-xs text-gray-400 mb-1">구역</label>
                <select
                  value={form.zoneId}
                  onChange={(e) => setForm((p) => ({ ...p, zoneId: e.target.value }))}
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-cyan-500 focus:outline-none"
                >
                  <option value="">구역 선택</option>
                  {zones.map((z) => (
                    <option key={z.id} value={z.id}>
                      {z.name}
                    </option>
                  ))}
                </select>
              </div>
              {/* Emergency contact */}
              <div>
                <label className="block text-xs text-gray-400 mb-1">비상연락처</label>
                <input
                  type="text"
                  value={form.emergencyContact}
                  onChange={(e) => setForm((p) => ({ ...p, emergencyContact: e.target.value }))}
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-cyan-500 focus:outline-none"
                  placeholder="010-0000-0000"
                />
              </div>
            </div>

            {/* Conditions */}
            <div>
              <label className="block text-xs text-gray-400 mb-2">건강 상태 태그</label>
              <div className="flex flex-wrap gap-2 mb-2">
                {PRESET_CONDITIONS.map((c) => (
                  <button
                    key={c}
                    type="button"
                    onClick={() => toggleCondition(c)}
                    className={`rounded-full px-3 py-1 text-xs font-medium border transition-colors ${
                      form.conditions.includes(c)
                        ? 'bg-cyan-700 text-white border-cyan-500'
                        : 'bg-gray-800 text-gray-400 border-gray-700 hover:border-gray-500'
                    }`}
                  >
                    {c}
                  </button>
                ))}
              </div>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={customCondition}
                  onChange={(e) => setCustomCondition(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addCustomCondition())}
                  className="flex-1 rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-xs text-white placeholder-gray-500 focus:border-cyan-500 focus:outline-none"
                  placeholder="직접 입력 후 Enter"
                />
                <button
                  type="button"
                  onClick={addCustomCondition}
                  className="rounded-lg border border-gray-700 px-3 py-1.5 text-xs text-gray-300 hover:text-white transition-colors"
                >
                  추가
                </button>
              </div>
              {form.conditions.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {form.conditions.map((c) => (
                    <span
                      key={c}
                      className="flex items-center gap-1 rounded-full bg-cyan-900/50 text-cyan-300 border border-cyan-700 px-2 py-0.5 text-[10px]"
                    >
                      {c}
                      <button
                        type="button"
                        onClick={() => toggleCondition(c)}
                        className="hover:text-white"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Notes */}
            <div>
              <label className="block text-xs text-gray-400 mb-1">메모</label>
              <textarea
                value={form.notes}
                onChange={(e) => setForm((p) => ({ ...p, notes: e.target.value }))}
                rows={2}
                className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-cyan-500 focus:outline-none resize-none"
                placeholder="추가 정보..."
              />
            </div>

            {/* Active toggle */}
            <label className="flex items-center gap-3 cursor-pointer">
              <div
                onClick={() => setForm((p) => ({ ...p, active: !p.active }))}
                className={`relative w-9 h-5 rounded-full transition-colors ${form.active ? 'bg-cyan-600' : 'bg-gray-700'}`}
              >
                <div
                  className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${form.active ? 'translate-x-4' : ''}`}
                />
              </div>
              <span className="text-sm text-gray-300">활성 입주자</span>
            </label>

            {/* Actions */}
            <div className="flex gap-2 pt-1">
              <button
                type="submit"
                className="rounded-lg bg-cyan-600 hover:bg-cyan-500 px-4 py-2 text-sm font-medium text-white transition-colors"
              >
                {editingId ? '저장' : '등록'}
              </button>
              <button
                type="button"
                onClick={closeForm}
                className="rounded-lg border border-gray-700 px-4 py-2 text-sm text-gray-300 hover:text-white transition-colors"
              >
                취소
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Card view */}
      {viewMode === 'card' && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {residents.length === 0 && (
            <p className="col-span-full text-sm text-gray-500 text-center py-10">
              등록된 입주자가 없습니다.
            </p>
          )}
          {residents.map((r) => (
            <ResidentCard
              key={r.id}
              resident={r}
              zoneName={r.zoneId ? zoneName(r.zoneId) : undefined}
              onEdit={openEdit}
              onRemove={removeResident}
            />
          ))}
        </div>
      )}

      {/* Table view */}
      {viewMode === 'table' && (
        <div className="rounded-xl border border-gray-800 bg-gray-900 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-xs text-gray-400">
                <th className="px-4 py-3 text-left font-medium">이름</th>
                <th className="px-4 py-3 text-left font-medium">호실</th>
                <th className="px-4 py-3 text-left font-medium">구역</th>
                <th className="px-4 py-3 text-left font-medium">건강 상태</th>
                <th className="px-4 py-3 text-left font-medium">상태</th>
                <th className="px-4 py-3 text-left font-medium">비상연락처</th>
                <th className="px-4 py-3 text-left font-medium">작업</th>
              </tr>
            </thead>
            <tbody>
              {residents.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-gray-500">
                    등록된 입주자가 없습니다.
                  </td>
                </tr>
              )}
              {residents.map((r) => (
                <tr
                  key={r.id}
                  className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors"
                >
                  <td className="px-4 py-3 text-white font-medium">{r.name}</td>
                  <td className="px-4 py-3 text-gray-300">{r.roomNumber}</td>
                  <td className="px-4 py-3 text-gray-300">
                    {r.zoneId ? zoneName(r.zoneId) : '-'}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {r.conditions.map((c) => (
                        <span
                          key={c}
                          className="rounded-full bg-gray-800 text-gray-300 border border-gray-700 px-2 py-0.5 text-[10px]"
                        >
                          {c}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                        r.active
                          ? 'bg-green-900/50 text-green-300 border border-green-700'
                          : 'bg-gray-800 text-gray-500 border border-gray-700'
                      }`}
                    >
                      {r.active ? '활성' : '비활성'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-300 text-xs">{r.emergencyContact || '-'}</td>
                  <td className="px-4 py-3">
                    <div className="flex gap-3">
                      <button
                        onClick={() => openEdit(r.id)}
                        className="text-xs text-cyan-400 hover:text-cyan-300 transition-colors"
                      >
                        수정
                      </button>
                      <button
                        onClick={() => removeResident(r.id)}
                        className="text-xs text-red-400 hover:text-red-300 transition-colors"
                      >
                        삭제
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
