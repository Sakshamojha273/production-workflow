import React from 'react';
import { cn, formatTrend, getTrendDirection } from '../utils/helpers';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface KPICardProps {
  title: string;
  value: string;
  trend?: number | null;
  description?: string;
  status?: 'Healthy' | 'Warning' | 'Critical' | null;
  icon?: React.ReactNode;
  iconColor?: string;
  children?: React.ReactNode;
}

export function KPICard({
  title,
  value,
  trend,
  description,
  status,
  icon,
  iconColor = 'bg-primary-100 text-primary-600',
  children,
}: KPICardProps) {
  const trendDirection = getTrendDirection(trend);
  const TrendIcon = trendDirection === 'up' ? TrendingUp : trendDirection === 'down' ? TrendingDown : Minus;
  const trendColor = trendDirection === 'up' ? 'text-success-600' : trendDirection === 'down' ? 'text-danger-600' : 'text-secondary-500';

  return (
    <div className="card p-6 hover:shadow-card-hover transition-shadow">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          {icon && (
            <div className={cn('p-2 rounded-lg', iconColor)}>
              {icon}
            </div>
          )}
          <p className="text-sm text-secondary-500 mt-2 truncate">{title}</p>
          <p className="text-3xl font-bold text-secondary-900 mt-1">{value}</p>
          {description && (
            <p className="text-xs text-secondary-400 mt-1">{description}</p>
          )}
        </div>
        {typeof trend === 'number' && Number.isFinite(trend) && (
          <div className={cn('flex items-center gap-1 text-sm font-medium', trendColor)}>
            <TrendIcon className="w-4 h-4" />
            <span>{formatTrend(trend)}</span>
          </div>
        )}
      </div>
      {children && (
        <div className="mt-4">
          {children}
        </div>
      )}
      {status && (
        <div className="mt-4">
          <span className={cn(
            'px-2 py-0.5 rounded-full text-xs font-medium',
            status === 'Healthy' && 'bg-success-100 text-success-700',
            status === 'Warning' && 'bg-warning-100 text-warning-700',
            status === 'Critical' && 'bg-danger-100 text-danger-700'
          )}>
            {status}
          </span>
        </div>
      )}
    </div>
  );
}