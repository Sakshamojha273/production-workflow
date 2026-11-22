import { useState } from 'react';
import { format } from 'date-fns';
import { useMaintenance, useMaintenanceTimeline, useMachines } from '../hooks/useData';
import { KPICard } from '../components/KPICard';
import { cn, formatCurrency, downloadFile, toCSV } from '../utils/helpers';
import {
  Wrench,
  Calendar,
  Clock,
  CheckCircle,
  Settings,
  Download,
  RefreshCw,
  Plus,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

export function MaintenancePage() {
  const { data: maintenance, loading, refetch } = useMaintenance();
  const { data: timeline, refetch: refetchTimeline } = useMaintenanceTimeline(30);
  const { data: machines } = useMachines();

  const [currentPage, setCurrentPage] = useState(1);
  const [filters, setFilters] = useState({
    machine_id: '',
    status: '',
    type: '',
  });
  const pageSize = 20;

  const filteredMaintenance = maintenance?.filter(m => {
    if (filters.machine_id && m.machine_id !== filters.machine_id) return false;
    if (filters.status && m.status !== filters.status) return false;
    if (filters.type && m.type !== filters.type) return false;
    return true;
  }) || [];

  const paginatedMaintenance = filteredMaintenance.slice((currentPage - 1) * pageSize, currentPage * pageSize);
  const totalPages = Math.ceil(filteredMaintenance.length / pageSize);

  const scheduled = maintenance?.filter(m => m.status === 'Scheduled').length || 0;
  const inProgress = maintenance?.filter(m => m.status === 'In Progress').length || 0;
  const completed = maintenance?.filter(m => m.status === 'Completed').length || 0;
  const now = new Date();
  const thisMonth = maintenance?.filter(m => {
    const d = new Date(m.start_date);
    return d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear();
  }).length || 0;

  const handleExport = () => {
    downloadFile(toCSV(
      ['Maintenance ID', 'Machine ID', 'Machine', 'Type', 'Status', 'Start', 'End', 'Reason', 'Cost'],
      filteredMaintenance.map(m => [m.maintenance_id, m.machine_id, m.machine_name, m.type, m.status, m.start_date, m.end_date, m.reason, m.cost]),
    ), 'maintenance.csv');
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Maintenance</h1>
          <p className="text-secondary-500">Track and schedule machine maintenance activities</p>
        </div>
        <div className="flex items-center gap-2">
          <button className="btn-primary" disabled title="Not available yet: the backend has no API for creating maintenance events">
            <Plus className="w-4 h-4" />
            Schedule Maintenance
          </button>
          <button className="btn-secondary" onClick={handleExport} disabled={!filteredMaintenance.length}>
            <Download className="w-4 h-4" />
            Export
          </button>
          <button className="btn-secondary" onClick={() => { refetch(); refetchTimeline(); }} disabled={loading}>
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <KPICard title="Total Records" value={maintenance?.length.toString() || '0'} icon={<Wrench className="w-5 h-5" />} iconColor="bg-blue-100 text-blue-600" />
        <KPICard title="Scheduled" value={scheduled.toString()} icon={<Calendar className="w-5 h-5" />} iconColor="bg-primary-100 text-primary-600" />
        <KPICard title="In Progress" value={inProgress.toString()} icon={<Clock className="w-5 h-5" />} iconColor="bg-warning-100 text-warning-600" />
        <KPICard title="Completed" value={completed.toString()} icon={<CheckCircle className="w-5 h-5" />} iconColor="bg-success-100 text-success-600" />
        <KPICard title="This Month" value={thisMonth.toString()} icon={<Calendar className="w-5 h-5" />} iconColor="bg-purple-100 text-purple-600" />
      </div>

      {/* Timeline View */}
      <div className="card">
        <div className="p-4 border-b border-secondary-200">
          <h3 className="text-lg font-semibold text-secondary-900">Upcoming Maintenance (Next 30 Days)</h3>
        </div>
        <div className="p-4">
          {timeline?.length ? (
            <div className="space-y-3">
              {timeline.slice(0, 10).map((item, index) => (
                <div key={index} className="flex items-center gap-4 p-4 rounded-lg bg-secondary-50">
                  <div className="flex-shrink-0 w-12 h-12 rounded-full bg-primary-100 flex items-center justify-center">
                    <Wrench className="w-6 h-6 text-primary-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3">
                      <h4 className="font-medium text-secondary-900">{item.machine_id}</h4>
                      <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium',
                        item.status === 'Scheduled' && 'bg-primary-100 text-primary-700',
                        item.status === 'In Progress' && 'bg-warning-100 text-warning-700',
                        item.status === 'Completed' && 'bg-success-100 text-success-700'
                      )}>
                        {item.status}
                      </span>
                      <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-secondary-100 text-secondary-700">
                        {item.type}
                      </span>
                    </div>
                    <p className="text-sm text-secondary-500 mt-1">
                      {format(new Date(item.start_date), 'MMM d, yyyy')} - {format(new Date(item.end_date), 'MMM d, yyyy')}
                      {item.reason && ` • ${item.reason}`}
                    </p>
                  </div>
                  <button
                    className="btn-secondary text-sm"
                    title="Filter the history table to this machine"
                    onClick={() => { setFilters(f => ({ ...f, machine_id: item.machine_id })); setCurrentPage(1); }}
                  >
                    <Settings className="w-4 h-4" />
                    History
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-secondary-500">
              <Calendar className="w-12 h-12 mx-auto mb-2 text-secondary-300" />
              <p>No upcoming maintenance scheduled</p>
            </div>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="card p-4">
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          <select value={filters.machine_id} onChange={e => setFilters({ ...filters, machine_id: e.target.value })} className="input">
            <option value="">All Machines</option>
            {machines?.map(m => <option key={m.machine_id} value={m.machine_id}>{m.name} ({m.machine_id})</option>)}
          </select>
          <select value={filters.status} onChange={e => setFilters({ ...filters, status: e.target.value })} className="input">
            <option value="">All Statuses</option>
            <option value="Scheduled">Scheduled</option>
            <option value="In Progress">In Progress</option>
            <option value="Completed">Completed</option>
            <option value="Cancelled">Cancelled</option>
            <option value="Overdue">Overdue</option>
          </select>
          <select value={filters.type} onChange={e => setFilters({ ...filters, type: e.target.value })} className="input">
            <option value="">All Types</option>
            <option value="Preventive">Preventive</option>
            <option value="Corrective">Corrective</option>
            <option value="Predictive">Predictive</option>
            <option value="Emergency">Emergency</option>
          </select>
        </div>
      </div>

      {/* Maintenance Table */}
      <div className="card">
        <div className="p-4 border-b border-secondary-200 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-secondary-900">Maintenance Records ({filteredMaintenance.length})</h3>
        </div>
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Maintenance ID</th>
                <th>Machine</th>
                <th>Type</th>
                <th>Status</th>
                <th>Start Date</th>
                <th>End Date</th>
                <th>Duration</th>
                <th>Reason</th>
                <th>Cost</th>
                <th>Performed By</th>
              </tr>
            </thead>
            <tbody>
              {paginatedMaintenance.map((item, index) => (
                <tr key={index}>
                  <td className="font-mono text-sm">{item.maintenance_id}</td>
                  <td>{item.machine_name || item.machine_id}</td>
                  <td>
                    <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-secondary-100 text-secondary-700">
                      {item.type}
                    </span>
                  </td>
                  <td>
                    <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium',
                      item.status === 'Scheduled' && 'bg-primary-100 text-primary-700',
                      item.status === 'In Progress' && 'bg-warning-100 text-warning-700',
                      item.status === 'Completed' && 'bg-success-100 text-success-700',
                      item.status === 'Cancelled' && 'bg-secondary-100 text-secondary-700',
                      item.status === 'Overdue' && 'bg-danger-100 text-danger-700'
                    )}>
                      {item.status}
                    </span>
                  </td>
                  <td>{format(new Date(item.start_date), 'MMM d, yyyy')}</td>
                  <td>{format(new Date(item.end_date), 'MMM d, yyyy')}</td>
                  <td>{Math.ceil((new Date(item.end_date).getTime() - new Date(item.start_date).getTime()) / (1000 * 60 * 60 * 24))} days</td>
                  <td className="max-w-xs truncate">{item.reason || '-'}</td>
                  <td>{formatCurrency(item.cost)}</td>
                  <td>{item.performed_by || '-'}</td>
                </tr>
              ))}
              {paginatedMaintenance.length === 0 && (
                <tr>
                  <td colSpan={10} className="text-center py-8 text-secondary-500">No maintenance records found</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="p-4 border-t border-secondary-200 flex items-center justify-between">
            <p className="text-sm text-secondary-500">
              Page {currentPage} of {totalPages} ({filteredMaintenance.length} records)
            </p>
            <div className="flex items-center gap-2">
              <button onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={currentPage === 1} className="btn-secondary text-sm">
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))} disabled={currentPage === totalPages} className="btn-secondary text-sm">
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
