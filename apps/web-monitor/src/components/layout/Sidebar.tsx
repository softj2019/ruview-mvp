import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Activity, LayoutDashboard, Cpu, Bell, Radio, Settings, GitMerge, HardDrive, Play, Globe, BarChart2, Building2, Users, FileText, Menu, X, Layers, Moon, TrendingUp, Crosshair, PersonStanding } from 'lucide-react';
import { cn } from '@/lib/utils';
import { StatusDot } from '@/components/ui/StatusDot';
import { NightModeToggle } from '@/components/ui/NightModeToggle';

type NavItem =
  | { type?: 'link'; to: string; label: string; icon: typeof LayoutDashboard; external?: boolean }
  | { type: 'divider'; label: string };

const navItems: NavItem[] = [
  // ── 모니터링
  { type: 'divider', label: '모니터링' },
  { to: '/', label: '대시보드', icon: LayoutDashboard },
  { to: '/events', label: '이벤트', icon: Bell },
  { to: '/devices', label: '디바이스', icon: Cpu },
  // ── 감지 / 분석
  { type: 'divider', label: '감지 · 분석' },
  { to: '/sensing', label: 'WiFi 센싱', icon: Radio },
  { to: '/rf-tomography', label: 'RF 히트맵', icon: Layers },
  { to: '/pose-fusion', label: '포즈 융합', icon: GitMerge },
  { to: '/sleep', label: '수면 모니터', icon: Moon },
  { to: '/analytics', label: '공간 분석', icon: TrendingUp },
  { to: '/position', label: '위치 추정', icon: Crosshair },
  { to: '/wifi-pose', label: 'WiFi 포즈', icon: PersonStanding },
  // ── 시각화
  { type: 'divider', label: '시각화' },
  { to: '/observatory', label: '3D 관측소', icon: Globe },
  { to: '/building', label: '건물 관제', icon: Building2 },
  { to: '/viz', label: '시각화', icon: BarChart2 },
  // ── 관리
  { type: 'divider', label: '관리' },
  { to: '/residents', label: '입주자', icon: Users },
  { to: '/reports', label: '리포트', icon: FileText },
  // ── 개발 도구
  { type: 'divider', label: '개발 도구' },
  { to: '/hardware', label: '하드웨어', icon: HardDrive },
  { to: '/live-demo', label: '라이브 데모', icon: Play },
  { to: '/settings', label: '설정', icon: Settings },
];

export default function Sidebar() {
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  const navContent = (
    <>
      {/* Logo */}
      <div className="flex h-14 items-center gap-2.5 px-5 border-b border-gray-800">
        <Activity className="h-5 w-5 text-cyan-400" />
        <span className="text-base font-semibold tracking-tight text-gray-100">RuView</span>
        <StatusDot status="online" className="ml-auto" />
        {/* Mobile close button */}
        <button
          onClick={() => setMobileOpen(false)}
          className="ml-2 md:hidden text-gray-400 hover:text-gray-200"
          aria-label="사이드바 닫기"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-3 overflow-y-auto space-y-0.5">
        {navItems.map((item, i) => {
          if (item.type === 'divider') {
            return (
              <div key={`div-${i}`} className="pt-3 pb-1 px-3">
                <p className="text-[10px] font-semibold uppercase tracking-widest text-gray-600">{item.label}</p>
              </div>
            );
          }
          const { to, label, icon: Icon, external } = item;
          const active = location.pathname === to;
          const cls = cn(
            'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors hover:bg-gray-800/50',
            active ? 'bg-gray-800/60 text-cyan-400' : 'text-gray-400 hover:text-gray-200',
          );
          if (external) {
            return <a key={to} href={to} className={cls}><Icon className="h-4 w-4" />{label}</a>;
          }
          return (
            <Link key={to} to={to} className={cls} onClick={() => setMobileOpen(false)}>
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Night mode toggle */}
      <div className="border-t border-gray-800 px-3 py-2">
        <NightModeToggle />
      </div>

      {/* Footer */}
      <div className="border-t border-gray-800 px-5 py-3">
        <p className="text-[10px] text-gray-600">RuView MVP v0.1.0</p>
        <p className="text-[10px] text-gray-600">ESP32 Hardware Mode</p>
      </div>
    </>
  );

  return (
    <>
      {/* Mobile hamburger — visible only below md */}
      <button
        onClick={() => setMobileOpen(true)}
        className="fixed top-3 left-3 z-50 flex md:hidden items-center justify-center h-9 w-9 rounded-lg border border-gray-700 bg-gray-900 text-gray-300 hover:text-gray-100 hover:bg-gray-800 transition-colors"
        aria-label="메뉴 열기"
      >
        <Menu className="h-4 w-4" />
      </button>

      {/* Mobile overlay backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Mobile slide-over sidebar */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 flex w-56 flex-col border-r border-gray-800 bg-gray-950 transition-transform duration-200 md:hidden',
          mobileOpen ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        {navContent}
      </aside>

      {/* Desktop sidebar — always shown on md+ */}
      <aside className="hidden md:fixed md:inset-y-0 md:left-0 md:z-40 md:flex md:w-56 md:flex-col border-r border-gray-800 bg-gray-950">
        {navContent}
      </aside>
    </>
  );
}
