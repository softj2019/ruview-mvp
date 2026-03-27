import { Link, useLocation } from 'react-router-dom';
import { Home, Activity, Wifi, Users, BarChart2 } from 'lucide-react';
import { cn } from '@/lib/utils';

const mobileNavItems = [
  { to: '/', label: '홈', icon: Home },
  { to: '/sensing', label: '센싱', icon: Activity },
  { to: '/devices', label: '디바이스', icon: Wifi },
  { to: '/events', label: '이벤트', icon: Users },
  { to: '/reports', label: '리포트', icon: BarChart2 },
];

export default function MobileNav() {
  const location = useLocation();

  return (
    <nav className="fixed bottom-0 inset-x-0 z-50 flex md:hidden border-t border-gray-800 bg-gray-950">
      {mobileNavItems.map(({ to, label, icon: Icon }) => {
        const active = location.pathname === to;
        return (
          <Link
            key={to}
            to={to}
            className={cn(
              'flex flex-1 flex-col items-center justify-center gap-0.5 py-2 text-[10px] font-medium transition-colors',
              active ? 'text-cyan-400' : 'text-gray-500 hover:text-gray-300',
            )}
          >
            <Icon className={cn('h-5 w-5', active ? 'text-cyan-400' : 'text-gray-500')} />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
