import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import MobileNav from './MobileNav';

export default function AppShell() {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <Sidebar />
      {/* Main content: on mobile no left padding (sidebar hidden), on md+ left padding for sidebar */}
      <main className="md:pl-56 pb-16 md:pb-0">
        {/* Top spacer on mobile to avoid hamburger overlap */}
        <div className="h-14 md:hidden" />
        <div className="p-4 md:p-6">
          <Outlet />
        </div>
      </main>
      <MobileNav />
    </div>
  );
}
