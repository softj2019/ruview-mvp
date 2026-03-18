import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';

export default function AppShell() {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <Sidebar />
      <main className="pl-56">
        <div className="p-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
