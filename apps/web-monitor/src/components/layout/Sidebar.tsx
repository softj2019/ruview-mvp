import { Link, useLocation } from 'react-router-dom';
import { Activity, LayoutDashboard, Cpu, Bell, Radio, Settings, GitMerge, HardDrive } from 'lucide-react';
import { cn } from '@/lib/utils';
import { StatusDot } from '@/components/ui/StatusDot';

const navItems = [
  { to: '/', label: '대시보드', icon: LayoutDashboard },
  { to: '/devices', label: '디바이스', icon: Cpu },
  { to: '/events', label: '이벤트', icon: Bell },
  { to: '/sensing', label: '센싱', icon: Radio },
  { to: '/pose-fusion', label: '포즈 융합', icon: GitMerge },
  { to: '/hardware', label: '하드웨어', icon: HardDrive },
  { to: '/settings', label: '설정', icon: Settings },
];

export default function Sidebar() {
  const location = useLocation();

  return (
    <aside className="fixed inset-y-0 left-0 z-40 flex w-56 flex-col border-r border-gray-800 bg-gray-950">
      {/* Logo */}
      <div className="flex h-14 items-center gap-2.5 px-5 border-b border-gray-800">
        <Activity className="h-5 w-5 text-cyan-400" />
        <span className="text-base font-semibold tracking-tight text-gray-100">RuView</span>
        <StatusDot status="online" className="ml-auto" />
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-1 px-3 py-4">
        {navItems.map(({ to, label, icon: Icon }) => {
          const active = location.pathname === to;
          return (
            <Link
              key={to}
              to={to}
              className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                active
                  ? 'bg-cyan-500/10 text-cyan-400'
                  : 'text-gray-400 hover:bg-gray-800/50 hover:text-gray-200',
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-gray-800 px-5 py-3">
        <p className="text-[10px] text-gray-600">RuView MVP v0.1.0</p>
        <p className="text-[10px] text-gray-600">Mock 시뮬레이션 모드</p>
      </div>
    </aside>
  );
}
