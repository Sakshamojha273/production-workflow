import React from 'react';
import { cn } from '../utils/helpers';

interface ChartCardProps {
  title: string;
  subtitle?: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  action?: React.ReactNode;
}

export function ChartCard({
  title,
  subtitle,
  icon,
  children,
  className,
  action,
}: ChartCardProps) {
  return (
    <div className={cn('card overflow-hidden', className)}>
      <div className="p-4 border-b border-secondary-200 flex items-center justify-between">
        <div className="flex items-center gap-3">
          {icon && (
            <div className="p-2 rounded-lg bg-primary-100 text-primary-600">
              {icon}
            </div>
          )}
          <div>
            <h3 className="text-lg font-semibold text-secondary-900">{title}</h3>
            {subtitle && <p className="text-sm text-secondary-500">{subtitle}</p>}
          </div>
        </div>
        {action && <div>{action}</div>}
      </div>
      <div className="p-4">
        {children}
      </div>
    </div>
  );
}