import { cn } from '@/lib/utils';

interface StatusDotProps {
  status: 'online' | 'offline' | 'alert' | 'warning';
  pulse?: boolean;
  className?: string;
}

const colors = {
  online: 'bg-emerald-400',
  offline: 'bg-gray-500',
  alert: 'bg-red-400',
  warning: 'bg-amber-400',
};

export function StatusDot({ status, pulse = true, className }: StatusDotProps) {
  return (
    <span className={cn('relative flex h-2 w-2', className)}>
      {pulse && status !== 'offline' && (
        <span
          className={cn(
            'absolute inline-flex h-full w-full animate-ping rounded-full opacity-75',
            colors[status],
          )}
        />
      )}
      <span className={cn('relative inline-flex h-2 w-2 rounded-full', colors[status])} />
    </span>
  );
}
