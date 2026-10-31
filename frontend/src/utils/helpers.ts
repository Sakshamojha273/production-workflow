import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
export { format } from 'date-fns';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNumber(num: number): string {
  if (num >= 1000000) {
    return `${Number((num / 1000000).toFixed(1))}M`;
  }
  if (num >= 1000) {
    return `${Number((num / 1000).toFixed(1))}K`;
  }
  return num.toLocaleString();
}

export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatPercent(value: number): string {
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`;
}

export function formatDate(date: string | Date): string {
  return new Date(date).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export function formatDateTime(date: string | Date): string {
  return new Date(date).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function getTrendDirection(trend?: number | null): 'up' | 'down' | 'neutral' {
  if (typeof trend !== 'number' || !Number.isFinite(trend) || trend === 0) return 'neutral';
  return trend > 0 ? 'up' : 'down';
}

/** Format a KPI trend percentage. The API sends `trend: null` when no trend exists. */
export function formatTrend(trend?: number | null): string {
  if (typeof trend !== 'number' || !Number.isFinite(trend)) return '—';
  return `${trend >= 0 ? '+' : ''}${trend.toFixed(1)}%`;
}

export function getStatusColor(status: string): string {
  switch (status) {
    case 'Healthy':
      return 'text-success-600 bg-success-100';
    case 'Warning':
      return 'text-warning-600 bg-warning-100';
    case 'Critical':
      return 'text-danger-600 bg-danger-100';
    default:
      return 'text-secondary-600 bg-secondary-100';
  }
}

export function getPriorityColor(priority: string): string {
  switch (priority) {
    case 'High':
      return 'text-danger-600 bg-danger-100';
    case 'Medium':
      return 'text-warning-600 bg-warning-100';
    case 'Low':
      return 'text-success-600 bg-success-100';
    default:
      return 'text-secondary-600 bg-secondary-100';
  }
}

export function getOrderStatusColor(status: string): string {
  switch (status) {
    case 'Completed':
      return 'text-success-600 bg-success-100';
    case 'In Progress':
      return 'text-primary-600 bg-primary-100';
    case 'Pending':
      return 'text-secondary-600 bg-secondary-100';
    case 'Delayed':
      return 'text-danger-600 bg-danger-100';
    default:
      return 'text-secondary-600 bg-secondary-100';
  }
}

export function getMachineStatusColor(status: string): string {
  switch (status) {
    case 'Operational':
      return 'text-success-600 bg-success-100';
    case 'Maintenance':
      return 'text-warning-600 bg-warning-100';
    case 'Offline':
      return 'text-danger-600 bg-danger-100';
    default:
      return 'text-secondary-600 bg-secondary-100';
  }
}

export function getRiskCategory(score: number): 'Low' | 'Medium' | 'High' {
  if (score < 0.3) return 'Low';
  if (score < 0.6) return 'Medium';
  return 'High';
}

export function getRiskColor(category: string): string {
  switch (category) {
    case 'Low':
      return 'text-success-600 bg-success-100';
    case 'Medium':
      return 'text-warning-600 bg-warning-100';
    case 'High':
      return 'text-danger-600 bg-danger-100';
    default:
      return 'text-secondary-600 bg-secondary-100';
  }
}

export function calculateCoverage(current: number, safetyStock: number): number {
  if (safetyStock === 0) return 0;
  return Math.round((current / safetyStock) * 100);
}

export function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: ReturnType<typeof setTimeout> | null = null;
  return (...args: Parameters<T>) => {
    if (timeout) clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
}

export function generateId(prefix: string = ''): string {
  return `${prefix}${Date.now().toString(36)}${Math.random().toString(36).substr(2, 9)}`;
}

export function downloadFile(content: string, filename: string, type: string = 'text/csv') {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export function parseCSV(csv: string): any[] {
  const lines = csv.trim().split('\n');
  const headers = lines[0].split(',').map(h => h.trim());
  return lines.slice(1).map(line => {
    const values = line.split(',').map(v => v.trim());
    return headers.reduce((obj, header, index) => {
      obj[header] = values[index] || '';
      return obj;
    }, {} as any);
  });
}