import { useMachines, useMachineRisk, useRiskDistribution, useMaintenanceTimeline } from '../hooks/useData';
import { KPICard } from '../components/KPICard';
import { ChartCard } from '../components/ChartCard';
import { cn, getRiskColor, getRiskCategory, getMachineStatusColor } from '../utils/helpers';
import {
  Activity,
  AlertTriangle,
  Wrench,
  TrendingUp,
  TrendingDown,
  Minus,
  Zap,
  Shield,
  RefreshCw,
} from 'lucide-react';

export function MachineHealthPage() {
  const { data: machines, refetch: refetchMachines } = useMachines();
  const { data: riskData, loading: riskLoading, refetch: refetchRisk } = useMachineRisk();
  const { data: riskDist, refetch: refetchRiskDist } = useRiskDistribution();
  const { data: maintenanceTimeline, refetch: refetchTimeline } = useMaintenanceTimeline(30);
  const refreshAll = () => { refetchMachines(); refetchRisk(); refetchRiskDist(); refetchTimeline(); };

  // Merge risk data with machines
  const machineRiskMap = new Map(riskData?.map(r => [r.machine_id, r]) || []);
  const enrichedMachines = machines?.map(m => ({
    ...m,
    risk: machineRiskMap.get(m.machine_id) || {
      risk_score: m.risk_score,
      risk_category: getRiskCategory(m.risk_score),
      trend: 'stable',
      anomaly_detected: false,
      maintenance_recommended: m.risk_score > 0.5,
    }
  }));

  const riskCategories = [
    { key: 'low' as const, label: 'Low Risk', color: 'bg-success-100 text-success-700', icon: <Shield className="w-5 h-5" /> },
    { key: 'medium' as const, label: 'Medium Risk', color: 'bg-warning-100 text-warning-700', icon: <AlertTriangle className="w-5 h-5" /> },
    { key: 'high' as const, label: 'High Risk', color: 'bg-danger-100 text-danger-700', icon: <Zap className="w-5 h-5" /> },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Machine Health</h1>
          <p className="text-secondary-500">Monitor machine risk, utilization, and maintenance</p>
        </div>
        <button className="btn-secondary" onClick={refreshAll} disabled={riskLoading}>
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Risk Distribution KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {riskCategories.map(cat => {
          // Count the same classification the cards below display (live
          // /machine-risk analysis); the server distribution uses that same
          // analysis and is only a fallback while it loads.
          const count = riskData?.length
            ? (enrichedMachines?.filter(m => m.risk?.risk_category?.toLowerCase() === cat.key).length || 0)
            : (riskDist?.[cat.key] ?? 0);
          return (
            <KPICard key={cat.key} title={cat.label} value={count.toString()} icon={cat.icon} iconColor={cat.color} />
          );
        })}
      </div>

      {/* Machine Health Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
        {enrichedMachines?.map((machine) => {
          const risk = machine.risk;
          const riskCat = risk?.risk_category || getRiskCategory(machine.risk_score);
          const TrendIcon = risk?.trend === 'increasing' ? TrendingUp :
                            risk?.trend === 'decreasing' ? TrendingDown : Minus;
          const trendColor = risk?.trend === 'increasing' ? 'text-danger-600' :
                             risk?.trend === 'decreasing' ? 'text-success-600' : 'text-secondary-500';

          return (
            <div key={machine.machine_id} className="card p-6 hover:shadow-card-hover transition-shadow">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <p className="text-sm text-secondary-500">{machine.machine_id}</p>
                  <h3 className="text-lg font-semibold text-secondary-900">{machine.name}</h3>
                  <p className="text-xs text-secondary-400">{machine.type} • Capacity: {machine.capacity}</p>
                </div>
                <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', getMachineStatusColor(machine.status))}>
                  {machine.status}
                </span>
              </div>

              <div className="grid grid-cols-3 gap-4 mb-4 p-4 bg-secondary-50 rounded-lg">
                <div className="text-center">
                  <p className="text-2xl font-bold text-secondary-900">{Number(risk?.risk_score ?? machine.risk_score).toFixed(2)}</p>
                  <p className="text-xs text-secondary-500">Risk Score</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-secondary-900">{Number((risk as { current_vibration?: number })?.current_vibration ?? machine.vibration).toFixed(3)}</p>
                  <p className="text-xs text-secondary-500">Vibration</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-secondary-900">{Number((risk as { current_temperature?: number })?.current_temperature ?? machine.temperature_c).toFixed(1)}°C</p>
                  <p className="text-xs text-secondary-500">Temperature</p>
                </div>
              </div>

              <div className="flex items-center justify-between mb-4">
                <span className={cn('px-2 py-1 rounded-full text-xs font-medium', getRiskColor(riskCat))}>
                  {riskCat} Risk
                </span>
                <div className={cn('flex items-center gap-1 text-xs font-medium', trendColor)}>
                  <TrendIcon className="w-3 h-3" />
                  <span>{risk?.trend || 'stable'}</span>
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-secondary-500">Utilization</span>
                  <span className="font-medium">{machine.utilization.toFixed(1)}%</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-secondary-500">Availability</span>
                  <span className={cn('font-medium', machine.availability ? 'text-success-600' : 'text-danger-600')}>
                    {machine.availability ? 'Operational' : 'Offline'}
                  </span>
                </div>
                {risk?.anomaly_detected && (
                  <div className="flex items-center gap-2 text-sm text-warning-600 bg-warning-50 px-2 py-1 rounded">
                    <AlertTriangle className="w-4 h-4" />
                    Anomaly detected in sensor data
                  </div>
                )}
                {risk?.maintenance_recommended && (
                  <div className="flex items-center gap-2 text-sm text-primary-600 bg-primary-50 px-2 py-1 rounded">
                    <Wrench className="w-4 h-4" />
                    Maintenance recommended
                  </div>
                )}
              </div>
            </div>
          );
        })}
        {enrichedMachines?.length === 0 && (
          <div className="col-span-full card p-12 text-center">
            <Activity className="w-16 h-16 text-secondary-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-secondary-900 mb-2">No machines found</h3>
            <p className="text-secondary-500">Upload data to see machine health</p>
          </div>
        )}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Risk Distribution */}
        <ChartCard title="Risk Distribution" subtitle="Current machine risk levels" icon={<Activity className="w-5 h-5" />}>
          <RiskDistributionChart data={riskDist ?? undefined} />
        </ChartCard>

        {/* Maintenance Timeline */}
        <ChartCard title="Upcoming Maintenance" subtitle="Next 30 days" icon={<Wrench className="w-5 h-5" />}>
          <MaintenanceTimelineChart data={maintenanceTimeline} />
        </ChartCard>
      </div>

      {/* Machine Table */}
      <div className="card">
        <div className="p-4 border-b border-secondary-200">
          <h3 className="text-lg font-semibold text-secondary-900">All Machines</h3>
        </div>
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Machine ID</th>
                <th>Name</th>
                <th>Type</th>
                <th>Capacity</th>
                <th>Utilization</th>
                <th>Vibration</th>
                <th>Temperature</th>
                <th>Risk Score</th>
                <th>Risk Category</th>
                <th>Status</th>
                <th>Availability</th>
              </tr>
            </thead>
            <tbody>
              {enrichedMachines?.map((machine, index) => {
                const risk = machine.risk;
                const riskCat = risk?.risk_category || getRiskCategory(machine.risk_score);
                return (
                  <tr key={index}>
                    <td className="font-mono text-sm">{machine.machine_id}</td>
                    <td>{machine.name}</td>
                    <td>{machine.type}</td>
                    <td>{machine.capacity}</td>
                    <td>{machine.utilization.toFixed(1)}%</td>
                    <td>{machine.vibration.toFixed(3)}</td>
                    <td>{machine.temperature_c.toFixed(1)}°C</td>
                    <td className="font-mono">{Number(risk?.risk_score ?? machine.risk_score).toFixed(2)}</td>
                    <td>
                      <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', getRiskColor(riskCat))}>
                        {riskCat}
                      </span>
                    </td>
                    <td>
                      <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', getMachineStatusColor(machine.status))}>
                        {machine.status}
                      </span>
                    </td>
                    <td>
                      <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', machine.availability ? 'bg-success-100 text-success-700' : 'bg-danger-100 text-danger-700')}>
                        {machine.availability ? 'Available' : 'Unavailable'}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function RiskDistributionChart({ data }: { data?: { low: number; medium: number; high: number } }) {
  if (!data) return <div className="h-64 flex items-center justify-center text-secondary-400">No data</div>;

  const chartData = [
    { name: 'Low', value: data.low, color: '#22c55e' },
    { name: 'Medium', value: data.medium, color: '#f59e0b' },
    { name: 'High', value: data.high, color: '#ef4444' },
  ];

  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={90}
            paddingAngle={2}
            dataKey="value"
            nameKey="name"
            label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
          >
            {chartData.map((_, i) => <Cell key={`cell-${i}`} fill={chartData[i].color} />)}
          </Pie>
          <Tooltip />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

function MaintenanceTimelineChart({ data }: { data?: any[] }) {
  if (!data?.length) return <div className="h-64 flex items-center justify-center text-secondary-400">No upcoming maintenance</div>;

  return (
    <div className="h-64 overflow-y-auto">
      <div className="space-y-3">
        {data.slice(0, 10).map((item, index) => (
          <div key={index} className="flex items-start gap-3 p-3 rounded-lg bg-secondary-50">
            <div className="flex-shrink-0 w-10 h-10 rounded-full bg-primary-100 flex items-center justify-center">
              <Wrench className="w-5 h-5 text-primary-600" />
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

import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip, Legend } from 'recharts';