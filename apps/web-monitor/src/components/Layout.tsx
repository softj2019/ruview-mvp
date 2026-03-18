import { Outlet } from 'react-router-dom';
import { Activity } from 'lucide-react';

export default function Layout() {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="h-14 border-b border-surface-600 flex items-center px-6 gap-3">
        <Activity className="w-5 h-5 text-neon-cyan" />
        <h1 className="text-lg font-semibold tracking-tight">RuView Monitor</h1>
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
