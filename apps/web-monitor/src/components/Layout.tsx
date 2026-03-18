import { Outlet, Link, useLocation } from 'react-router-dom';
import { Activity, LayoutDashboard, Cpu, Bell, Settings } from 'lucide-react';

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/devices', label: 'Devices', icon: Cpu },
  { to: '/events', label: 'Events', icon: Bell },
  { to: '/settings', label: 'Settings', icon: Settings },
];

export default function Layout() {
  const location = useLocation();

  return (
    <div className="min-h-screen flex flex-col">
      <header className="h-14 border-b border-surface-600 flex items-center px-6 gap-3">
        <Activity className="w-5 h-5 text-neon-cyan" />
        <h1 className="text-lg font-semibold tracking-tight">RuView Monitor</h1>
        <nav className="ml-6 flex items-center gap-1">
          {navItems.map(({ to, label, icon: Icon }) => {
            const active = location.pathname === to;
            return (
              <Link
                key={to}
                to={to}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors ${
                  active
                    ? 'bg-neon-cyan/10 text-neon-cyan'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-surface-700'
                }`}
              >
                <Icon className="w-4 h-4" />
                {label}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto flex items-center gap-4 text-sm text-gray-400">
          <span className="status-online" /> System Online
        </div>
      </header>
      <main className="flex-1 p-4 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
