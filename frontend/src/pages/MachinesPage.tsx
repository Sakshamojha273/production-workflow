import { useMachines } from '../hooks/useData';
import { KPICard } from '../components/KPICard';
import { cn, getMachineStatusColor, getRiskColor, getRiskCategory } from '../utils/helpers';
import {
  Factory,
  Gauge,
  AlertTriangle,
  Wrench,
  Shield,
  Settings,
  Download,
  RefreshCw,
} from 'lucide-react';

export function MachinesPage() {
  const { data: machines, loading } = useMachines();

  const operational = machines?.filter(m => m.status === 'Operational').length || 0;
  const maintenance = machines?.filter(m => m.status === 'Maintenance').length || 0;
  const offline = machines?.filter(m => m.status === 'Offline').length || 0;
  const avgUtilization = machines?.reduce((sum, m) => sum + m.utilization, 0) / (machines?.length || 1);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Machines</h1>
          <p className="text-secondary-500">Monitor machine status, utilization, and health</p>
        </div>
        <div className="flex items-center gap-2">
          <button className="btn-secondary">
            <Download className="w-4 h-4" />
            Export
          </button>
          <button className="btn-secondary" disabled={loading}>
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <KPICard title="Total Machines" value={machines?.length.toString() || '0'} icon={<Factory className="w-5 h-5" />} iconColor="bg-blue-100 text-blue-600" />
        <KPICard title="Operational" value={operational.toString()} icon={<Shield className="w-5 h-5" />} iconColor="bg-success-100 text-success-600" />
        <KPICard title="Maintenance" value={maintenance.toString()} icon={<Wrench className="w-5 h-5" />} iconColor="bg-warning-100 text-warning-600" />
        <KPICard title="Offline" value={offline.toString()} icon={<AlertTriangle className="w-5 h-5" />} iconColor="bg-danger-100 text-danger-600" />
        <KPICard title="Avg Utilization" value={`${avgUtilization.toFixed(1)}%`} icon={<Gauge className="w-5 h-5" />} iconColor="bg-purple-100 text-purple-600" />
      </div>

      {/* Machine Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
        {machines?.map((machine) => {
          const riskCat = getRiskCategory(machine.risk_score);
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
                  <p className="text-2xl font-bold text-secondary-900">{machine.utilization.toFixed(1)}%</p>
                  <p className="text-xs text-secondary-500">Utilization</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-secondary-900">{machine.vibration.toFixed(3)}</p>
                  <p className="text-xs text-secondary-500">Vibration</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-secondary-900">{machine.temperature_c.toFixed(1)}°C</p>
                  <p className="text-xs text-secondary-500">Temperature</p>
                </div>
              </div>

              <div className="flex items-center justify-between mb-4">
                <span className={cn('px-2 py-1 rounded-full text-xs font-medium', getRiskColor(riskCat))}>
                  {riskCat} Risk
                </span>
                <div className="flex items-center gap-1 text-xs font-medium text-secondary-500">
                  <span>Risk: {machine.risk_score.toFixed(2)}</span>
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-secondary-500">Availability</span>
                  <span className={cn('font-medium', machine.availability ? 'text-success-600' : 'text-danger-600')}>
                    {machine.availability ? 'Available' : 'Unavailable'}
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-secondary-500">Last Maintenance</span>
                  <span className="font-medium">{machine.last_maintenance ? format(new Date(machine.last_maintenance), 'MMM d, yyyy') : 'Never'}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-secondary-500">Next Maintenance</span>
                  <span className="font-medium">{machine.next_maintenance ? format(new Date(machine.next_maintenance), 'MMM d, yyyy') : 'Not scheduled'}</span>
                </div>
              </div>

              <div className="mt-4 pt-4 border-t border-secondary-200 flex gap-2">
                <button className="btn-secondary text-sm flex-1">
                  <Settings className="w-4 h-4" />
                  Details
                </button>
                <button className="btn-outline text-sm flex-1">
                  <Wrench className="w-4 h-4" />
                  Schedule Maintenance
                </button>
              </div>
            </div>
          );
        })}
        {machines?.length === 0 && (
          <div className="col-span-full card p-12 text-center">
            <Factory className="w-16 h-16 text-secondary-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-secondary-900 mb-2">No machines found</h3>
            <p className="text-secondary-500">Upload data to see machines</p>
          </div>
        )}
      </div>

      {/* Machine Table */}
      <div className="card">
        <div className="p-4 border-b border-secondary-200">
          <h3 className="text-lg font-semibold text-secondary-900">All Machines Table</h3>
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
                <th>Last Maintenance</th>
                <th>Next Maintenance</th>
              </tr>
            </thead>
            <tbody>
              {machines?.map((machine, index) => {
                const riskCat = getRiskCategory(machine.risk_score);
                return (
                  <tr key={index}>
                    <td className="font-mono text-sm">{machine.machine_id}</td>
                    <td>{machine.name}</td>
                    <td>{machine.type}</td>
                    <td>{machine.capacity}</td>
                    <td>{machine.utilization.toFixed(1)}%</td>
                    <td>{machine.vibration.toFixed(3)}</td>
                    <td>{machine.temperature_c.toFixed(1)}°C</td>
                    <td className="font-mono">{machine.risk_score.toFixed(2)}</td>
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
                    <td>{machine.last_maintenance ? format(new Date(machine.last_maintenance), 'MMM d, yyyy') : '-'}</td>
                    <td>{machine.next_maintenance ? format(new Date(machine.next_maintenance), 'MMM d, yyyy') : '-'}</td>
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

import { format } from 'date-fns';