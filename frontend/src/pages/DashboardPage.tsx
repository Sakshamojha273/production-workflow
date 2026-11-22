import { useDashboard, useCharts } from '../hooks/useData';
import { ChartCard } from '../components/ChartCard';
import { cn, formatTrend, getTrendDirection } from '../utils/helpers';
import { api } from '../services/api';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Package,
  Factory,
  Users,
  Gauge,
  Box,
  Clock,
  AlertTriangle,
  ArrowUpRight,
} from 'lucide-react';

const KPI_CONFIG = [
  { key: 'total_orders', icon: Package, color: 'bg-primary-100 text-primary-600', label: 'Total Orders' },
  { key: 'production_planned', icon: Factory, color: 'bg-blue-100 text-blue-600', label: 'Production Planned' },
  { key: 'current_demand', icon: Package, color: 'bg-cyan-100 text-cyan-600', label: 'Current Demand' },
  { key: 'demand_forecast', icon: ArrowUpRight, color: 'bg-purple-100 text-purple-600', label: 'Demand Forecast' },
  { key: 'demand_growth', icon: TrendingUp, color: 'bg-pink-100 text-pink-600', label: 'Expected Demand Growth' },
  { key: 'machine_utilization', icon: Gauge, color: 'bg-green-100 text-green-600', label: 'Machine Utilization' },
  { key: 'workforce_utilization', icon: Users, color: 'bg-orange-100 text-orange-600', label: 'Workforce Utilization' },
  { key: 'inventory_level', icon: Box, color: 'bg-indigo-100 text-indigo-600', label: 'Inventory Level' },
  { key: 'overtime_hours', icon: Clock, color: 'bg-red-100 text-red-600', label: 'Overtime Hours' },
  { key: 'late_orders', icon: AlertTriangle, color: 'bg-yellow-100 text-yellow-600', label: 'Late Orders' },
];

export function DashboardPage() {
  const { data: dashboard, loading: dashboardLoading, error: dashboardError } = useDashboard();
  const { data: charts } = useCharts();
  const navigate = useNavigate();
  const [forecastPreview, setForecastPreview] = useState<{ date: string; actual?: number; forecast?: number }[]>([]);

  useEffect(() => {
    Promise.all([
      api.getDemandHistory({ days: 30 }),
      api.getForecasts({ horizon_days: 7 }),
    ]).then(([historyResult, forecastResult]) => {
      const values = new Map<string, { date: string; actual?: number; forecast?: number }>();
      (historyResult.history || []).forEach((point: { date: string; demand: number }) => {
        const current = values.get(point.date) || { date: point.date };
        current.actual = (current.actual || 0) + point.demand;
        values.set(point.date, current);
      });
      (forecastResult.forecasts || []).forEach((point: { forecast_date: string; predicted_demand: number }) => {
        const current = values.get(point.forecast_date) || { date: point.forecast_date };
        current.forecast = (current.forecast || 0) + point.predicted_demand;
        values.set(point.forecast_date, current);
      });
      setForecastPreview([...values.values()].sort((left, right) => left.date.localeCompare(right.date)));
    }).catch((error: unknown) => {
      console.error('Failed to load dashboard demand forecast preview:', error);
    });
  }, []);

  if (dashboardLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-secondary-900">Dashboard</h1>
            <p className="text-secondary-500">Overview of production planning metrics</p>
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5 gap-4">
          {Array.from({ length: KPI_CONFIG.length }).map((_, i) => (
            <KPICardSkeleton key={i} />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {Array.from({ length: 5 }).map((_, i) => (
            <ChartCardSkeleton key={i} />
          ))}
        </div>
      </div>
    );
  }

  if (dashboardError) {
    return (
      <div className="card p-8 text-center">
        <AlertTriangle className="w-12 h-12 text-danger-500 mx-auto mb-4" />
        <h2 className="text-xl font-semibold text-secondary-900 mb-2">Failed to load dashboard</h2>
        <p className="text-secondary-500 mb-4">{dashboardError}</p>
        <button className="btn-primary" onClick={() => window.location.reload()}>
          Retry
        </button>
      </div>
    );
  }

  const kpis = dashboard?.kpis || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Dashboard</h1>
          <p className="text-secondary-500">Overview of production planning metrics</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="px-3 py-1 rounded-full bg-success-100 text-success-700 text-sm font-medium">
            Live Data
          </span>
        </div>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5 gap-4">
        {KPI_CONFIG.map((config, index) => {
          const kpi = kpis[index];
          if (!kpi) return null;

          const TrendIcon = getTrendDirection(kpi.trend) === 'up' ? TrendingUp :
                            getTrendDirection(kpi.trend) === 'down' ? TrendingDown : Minus;
          const trendColor = getTrendDirection(kpi.trend) === 'up' ? 'text-success-600' :
                             getTrendDirection(kpi.trend) === 'down' ? 'text-danger-600' : 'text-secondary-500';

          const card = (
            <div className="card p-6 hover:shadow-card-hover transition-shadow">
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <div className={cn('p-2 rounded-lg', config.color)}>
                      <config.icon className="w-5 h-5" />
                    </div>
                  </div>
                  <p className="text-sm text-secondary-500 mt-2 truncate">{config.label}</p>
                  <p className="text-3xl font-bold text-secondary-900 mt-1">{kpi.value}</p>
                  {kpi.description && (
                    <p className="text-xs text-secondary-400 mt-1">{kpi.description}</p>
                  )}
                </div>
                <div className={cn('flex items-center gap-1 text-sm font-medium', trendColor)}>
                  <TrendIcon className="w-4 h-4" />
                  <span>{formatTrend(kpi.trend)}</span>
                </div>
              </div>
              <div className="mt-4 flex items-center gap-2">
                <span className={cn(
                  'px-2 py-0.5 rounded-full text-xs font-medium',
                  kpi.status === 'Healthy' && 'bg-success-100 text-success-700',
                  kpi.status === 'Warning' && 'bg-warning-100 text-warning-700',
                  kpi.status === 'Critical' && 'bg-danger-100 text-danger-700'
                )}>
                  {kpi.status}
                </span>
              </div>
            </div>
          );
          return config.key === 'demand_forecast' ? (
            <button key={config.key} type="button" className="text-left" onClick={() => navigate('/analytics/demand-forecast')}>
              {card}
            </button>
          ) : <div key={config.key}>{card}</div>;
        })}
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartCard title="Historical vs Forecast Demand" subtitle="Latest saved demand forecast" icon={<ArrowUpRight className="w-5 h-5" />}>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={forecastPreview} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip />
                <Legend />
                <Line dataKey="actual" name="Historical demand" stroke="#64748b" dot={false} connectNulls />
                <Line dataKey="forecast" name="Forecast demand" stroke="#2563eb" strokeWidth={2} dot={false} connectNulls />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>
        {/* Demand vs Production */}
        <ChartCard title="Demand vs Production" subtitle="Last 30 days" icon={<Package className="w-5 h-5" />}>
          <DemandVsProductionChart data={charts.demand_vs_production?.data} />
        </ChartCard>

        {/* Production by Product */}
        <ChartCard title="Production by Product" subtitle="Last 30 days" icon={<Factory className="w-5 h-5" />}>
          <ProductionByProductChart data={charts.production_by_product?.data} />
        </ChartCard>

        {/* Machine Utilization */}
        <ChartCard title="Machine Utilization" subtitle="Latest production plan · planned vs available units %" icon={<Gauge className="w-5 h-5" />}>
          <MachineUtilizationChart data={charts.machine_utilization?.data} />
        </ChartCard>

        {/* Workforce Utilization */}
        <ChartCard title="Workforce Utilization" subtitle="Latest production plan · regular hours used % (top 20)" icon={<Users className="w-5 h-5" />}>
          <WorkforceUtilizationChart data={charts.workforce_utilization?.data} />
        </ChartCard>

        {/* Production Cost Trend */}
        <ChartCard title="Production Cost Trend" subtitle="Last 30 days" icon={<ArrowUpRight className="w-5 h-5" />}>
          <ProductionCostChart data={charts.production_cost_trend?.data} />
        </ChartCard>

        {/* Overtime Trend */}
        <ChartCard title="Overtime Trend" subtitle="Last 30 days" icon={<Clock className="w-5 h-5" />}>
          <OvertimeChart data={charts.overtime_trend?.data} />
        </ChartCard>

        {/* Machine Risk Distribution */}
        <ChartCard title="Machine Risk Distribution" subtitle="Current risk levels" icon={<AlertTriangle className="w-5 h-5" />}>
          <RiskDistributionChart data={charts.machine_risk_distribution?.data} />
        </ChartCard>

        {/* Orders by Priority */}
        <ChartCard title="Orders by Priority" subtitle="Last 30 days" icon={<Package className="w-5 h-5" />}>
          <OrdersByPriorityChart data={charts.orders_by_priority?.data} />
        </ChartCard>
      </div>

      {/* Additional Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Inventory Status */}
        <ChartCard title="Inventory Status" subtitle="Current stock levels" icon={<Box className="w-5 h-5" />}>
          <InventoryStatusChart data={charts.inventory_status?.data} />
        </ChartCard>

        {/* Upcoming Maintenance */}
        <ChartCard title="Upcoming Maintenance" subtitle="Next 30 days" icon={<Gauge className="w-5 h-5" />}>
          <MaintenanceTimeline data={charts.upcoming_maintenance?.data} />
        </ChartCard>
      </div>
    </div>
  );
}

// Chart Components
function DemandVsProductionChart({ data }: { data?: any }) {
  if (!data?.labels?.length) return <div className="h-64 flex items-center justify-center text-secondary-400">No data available</div>;

  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data.labels.map((label: string, i: number) => ({
          name: label,
          demand: data.datasets[0]?.data[i] || 0,
          production: data.datasets[1]?.data[i] || 0,
        }))} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} tick={{ fill: '#64748b' }} />
          <YAxis stroke="#94a3b8" fontSize={11} tick={{ fill: '#64748b' }} />
          <Tooltip />
          <Legend />
          <Bar dataKey="demand" name="Demand" fill="#3b82f6" radius={[4, 4, 0, 0]} />
          <Line type="monotone" dataKey="production" name="Production" stroke="#22c55e" strokeWidth={2} dot={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

function ProductionByProductChart({ data }: { data?: any }) {
  if (!data?.labels?.length) return <div className="h-64 flex items-center justify-center text-secondary-400">No data available</div>;

  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data.labels.map((label: string, i: number) => ({
          name: label,
          value: data.datasets[0]?.data[i] || 0,
        }))} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} tick={{ fill: '#64748b' }} />
          <YAxis stroke="#94a3b8" fontSize={11} tick={{ fill: '#64748b' }} />
          <Tooltip />
          <Bar dataKey="value" fill="#3b82f6" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function MachineUtilizationChart({ data }: { data?: any }) {
  if (!data?.labels?.length) return <div className="h-64 flex items-center justify-center text-secondary-400">No data available</div>;

  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data.labels.map((label: string, i: number) => ({
          name: label,
          value: data.datasets[0]?.data[i] || 0,
        }))} margin={{ top: 10, right: 30, left: 0, bottom: 0 }} layout="vertical">
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis type="number" stroke="#94a3b8" fontSize={11} tick={{ fill: '#64748b' }} />
          <YAxis dataKey="name" type="category" stroke="#94a3b8" fontSize={11} tick={{ fill: '#64748b' }} width={100} />
          <Tooltip />
          <Bar dataKey="value" fill="#3b82f6" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function WorkforceUtilizationChart({ data }: { data?: any }) {
  if (!data?.labels?.length) return <div className="h-64 flex items-center justify-center text-secondary-400">No data available</div>;

  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data.labels.map((label: string, i: number) => ({
          name: label,
          value: data.datasets[0]?.data[i] || 0,
        }))} margin={{ top: 10, right: 30, left: 0, bottom: 0 }} layout="vertical">
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis type="number" stroke="#94a3b8" fontSize={11} tick={{ fill: '#64748b' }} />
          <YAxis dataKey="name" type="category" stroke="#94a3b8" fontSize={11} tick={{ fill: '#64748b' }} width={100} />
          <Tooltip />
          <Bar dataKey="value" fill="#f59e0b" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function ProductionCostChart({ data }: { data?: any }) {
  if (!data?.labels?.length) return <div className="h-64 flex items-center justify-center text-secondary-400">No data available</div>;

  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data.labels.map((label: string, i: number) => ({
          name: label,
          value: data.datasets[0]?.data[i] || 0,
        }))} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} tick={{ fill: '#64748b' }} />
          <YAxis stroke="#94a3b8" fontSize={11} tick={{ fill: '#64748b' }} />
          <Tooltip />
          <Line type="monotone" dataKey="value" stroke="#8b5cf6" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function OvertimeChart({ data }: { data?: any }) {
  if (!data?.labels?.length) return <div className="h-64 flex items-center justify-center text-secondary-400">No data available</div>;

  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data.labels.map((label: string, i: number) => ({
          name: label,
          value: data.datasets[0]?.data[i] || 0,
        }))} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} tick={{ fill: '#64748b' }} />
          <YAxis stroke="#94a3b8" fontSize={11} tick={{ fill: '#64748b' }} />
          <Tooltip />
          <Area type="monotone" dataKey="value" stroke="#ef4444" fill="#ef4444" fillOpacity={0.2} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function RiskDistributionChart({ data }: { data?: any }) {
  if (!data?.labels?.length) return <div className="h-64 flex items-center justify-center text-secondary-400">No data available</div>;

  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data.labels.map((label: string, i: number) => ({
              name: label,
              value: data.datasets[0]?.data[i] || 0,
            }))}
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={90}
            paddingAngle={2}
            dataKey="value"
            nameKey="name"
            label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
          >
            {data.datasets[0]?.data.map((_: number, i: number) => (
              <Cell key={`cell-${i}`} fill={['#22c55e', '#f59e0b', '#ef4444'][i]} />
            ))}
          </Pie>
          <Tooltip />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

function OrdersByPriorityChart({ data }: { data?: any }) {
  if (!data?.labels?.length) return <div className="h-64 flex items-center justify-center text-secondary-400">No data available</div>;

  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data.labels.map((label: string, i: number) => ({
              name: label,
              value: data.datasets[0]?.data[i] || 0,
            }))}
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={90}
            paddingAngle={2}
            dataKey="value"
            nameKey="name"
            label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
          >
            {data.datasets[0]?.data.map((_: number, i: number) => (
              <Cell key={`cell-${i}`} fill={['#ef4444', '#f59e0b', '#22c55e'][i]} />
            ))}
          </Pie>
          <Tooltip />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

function InventoryStatusChart({ data }: { data?: any }) {
  if (!data?.labels?.length) return <div className="h-64 flex items-center justify-center text-secondary-400">No data available</div>;

  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data.labels.map((label: string, i: number) => ({
          name: label,
          value: data.datasets[0]?.data[i] || 0,
        }))} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} tick={{ fill: '#64748b' }} />
          <YAxis stroke="#94a3b8" fontSize={11} tick={{ fill: '#64748b' }} />
          <Tooltip />
          <Bar dataKey="value" radius={[4, 4, 0, 0]}>
            {data.labels.map((_: string, index: number) => (
              <Cell key={`cell-${index}`} fill={['#22c55e', '#f59e0b', '#ef4444'][index % 3]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function MaintenanceTimeline({ data }: { data?: any }) {
  if (!data?.length) return <div className="h-64 flex items-center justify-center text-secondary-400">No upcoming maintenance</div>;

  return (
    <div className="h-64 overflow-y-auto">
      <div className="space-y-4">
        {data.slice(0, 8).map((item: any, index: number) => (
          <div key={index} className="flex items-start gap-3 p-3 rounded-lg bg-secondary-50">
            <div className="flex-shrink-0 w-10 h-10 rounded-full bg-primary-100 flex items-center justify-center">
              <Gauge className="w-5 h-5 text-primary-600" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-secondary-900">{item.machine_id}</p>
              <p className="text-xs text-secondary-500">{item.type} • {item.start_date} to {item.end_date}</p>
              <span className={cn(
                'inline-block mt-1 px-2 py-0.5 rounded-full text-xs font-medium',
                item.status === 'Scheduled' && 'bg-primary-100 text-primary-700',
                item.status === 'In Progress' && 'bg-warning-100 text-warning-700',
                item.status === 'Completed' && 'bg-success-100 text-success-700'
              )}>
                {item.status}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// Skeleton components
function KPICardSkeleton() {
  return (
    <div className="card p-6 animate-pulse">
      <div className="flex items-center gap-2">
        <div className="w-10 h-10 rounded-lg bg-secondary-200" />
      </div>
      <div className="mt-4 h-4 w-1/4 bg-secondary-200 rounded" />
      <div className="mt-2 h-8 w-1/2 bg-secondary-200 rounded" />
      <div className="mt-2 h-3 w-1/3 bg-secondary-200 rounded" />
      <div className="mt-4 h-6 w-1/4 bg-secondary-200 rounded" />
    </div>
  );
}

function ChartCardSkeleton() {
  return (
    <div className="card animate-pulse">
      <div className="p-4 border-b border-secondary-200">
        <div className="h-5 w-1/4 bg-secondary-200 rounded" />
        <div className="mt-1 h-3 w-1/3 bg-secondary-200 rounded" />
      </div>
      <div className="p-4 h-64">
        <div className="w-full h-full bg-secondary-100 rounded" />
      </div>
    </div>
  );
}

// Import Recharts components
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ComposedChart,
} from 'recharts';