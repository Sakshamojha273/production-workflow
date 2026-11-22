import { useWorkers } from '../hooks/useData';
import { KPICard } from '../components/KPICard';
import { cn, downloadFile, toCSV } from '../utils/helpers';
import { useNavigate } from 'react-router-dom';
import type { Worker } from '../types';
import {
  Users,
  UserCheck,
  Clock,
  AlertTriangle,
  Brain,
  Download,
  RefreshCw,
  Settings,
  Briefcase,
} from 'lucide-react';

export function WorkforcePage() {
  const { data: workers, meta, loading, refetch } = useWorkers();
  const navigate = useNavigate();
  // Per-worker utilization comes from the latest production plan (backend).
  const utilOf = (w: Worker) => w.utilization ?? 0;

  const available = workers?.filter(w => w.availability === 'Available').length || 0;
  const unavailable = workers?.filter(w => w.availability === 'Unavailable').length || 0;
  const onLeave = workers?.filter(w => w.availability === 'On Leave').length || 0;
  // Plan-level figure (same as the Production Planning page and Dashboard).
  const avgUtilization = meta.workforce_utilization ?? 0;

  const handleExport = () => {
    downloadFile(toCSV(
      ['Worker ID', 'Name', 'Department', 'Shift', 'Availability', 'Hours/week (plan)', 'Max Hours', 'Overtime/week (plan)', 'Utilization %', 'Skills'],
      (workers || []).map(w => [w.worker_id, w.name, w.department, w.shift, w.availability, w.current_hours, w.max_hours_per_week, w.overtime_hours, utilOf(w).toFixed(1), w.skills.map(sk => sk.machine_type).join('; ')]),
    ), 'workforce.csv');
  };

  const departments = [...new Set(workers?.map(w => w.department) || [])];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Workforce</h1>
          <p className="text-secondary-500">Manage worker assignments, skills, and availability</p>
          <p className="text-xs text-secondary-400 mt-1">
            {meta.plan_id ? `Hours and utilization from latest plan ${meta.plan_id} (hours normalised to a 7-day week)` : 'No production plan yet: generate one on Production Planning to see hours and utilization'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button className="btn-secondary" onClick={handleExport} disabled={!workers?.length}>
            <Download className="w-4 h-4" />
            Export
          </button>
          <button className="btn-secondary" onClick={() => refetch()} disabled={loading}>
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <KPICard title="Total Workers" value={workers?.length.toString() || '0'} icon={<Users className="w-5 h-5" />} iconColor="bg-blue-100 text-blue-600" />
        <KPICard title="Available" value={available.toString()} icon={<UserCheck className="w-5 h-5" />} iconColor="bg-success-100 text-success-600" />
        <KPICard title="Unavailable" value={unavailable.toString()} icon={<AlertTriangle className="w-5 h-5" />} iconColor="bg-warning-100 text-warning-600" />
        <KPICard title="On Leave" value={onLeave.toString()} icon={<Clock className="w-5 h-5" />} iconColor="bg-secondary-100 text-secondary-600" />
        <KPICard title="Avg Utilization" value={`${avgUtilization.toFixed(1)}%`} icon={<Brain className="w-5 h-5" />} iconColor="bg-purple-100 text-purple-600" />
      </div>

      {/* Worker Cards by Department */}
      {departments.map(dept => {
        const deptWorkers = workers?.filter(w => w.department === dept) || [];
        return (
          <div key={dept} className="card">
            <div className="p-4 border-b border-secondary-200 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-secondary-900 flex items-center gap-2">
                <Briefcase className="w-5 h-5" />
                {dept} ({deptWorkers.length})
              </h3>
            </div>
            <div className="p-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {deptWorkers.map((worker) => (
                  <div key={worker.worker_id} className="p-4 bg-secondary-50 rounded-lg hover:shadow-card-hover transition-shadow">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="w-10 h-10 rounded-full bg-primary-100 flex items-center justify-center">
                        <Users className="w-5 h-5 text-primary-600" />
                      </div>
                      <div>
                        <h4 className="font-medium text-secondary-900">{worker.name}</h4>
                        <p className="text-xs text-secondary-500">{worker.worker_id}</p>
                      </div>
                    </div>
                    <div className="space-y-2 text-sm">
                      <div className="flex items-center justify-between">
                        <span className="text-secondary-500">Shift</span>
                        <span className="font-medium">{worker.shift}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-secondary-500">Availability</span>
                        <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium',
                          worker.availability === 'Available' && 'bg-success-100 text-success-700',
                          worker.availability === 'Unavailable' && 'bg-warning-100 text-warning-700',
                          worker.availability === 'On Leave' && 'bg-secondary-100 text-secondary-700'
                        )}>
                          {worker.availability}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-secondary-500">Hours</span>
                        <span className="font-medium">{worker.current_hours}/{worker.max_hours_per_week}h</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-secondary-500">Overtime</span>
                        <span className="font-medium text-warning-600">{worker.overtime_hours}h</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-secondary-500">Utilization</span>
                        <span className="font-medium">{utilOf(worker).toFixed(1)}%</span>
                      </div>
                    </div>
                    {worker.skills.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-secondary-200">
                        <p className="text-xs text-secondary-500 mb-1">Skills:</p>
                        <div className="flex flex-wrap gap-1">
                          {worker.skills.map((skill, si) => (
                            <span key={si} className="px-2 py-0.5 text-xs rounded bg-primary-100 text-primary-700">
                              {skill.machine_type} ({Math.round(skill.proficiency * 100)}%)
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    <button className="btn-secondary text-sm w-full mt-3" onClick={() => navigate('/planning/production')} title="Open this plan's assignments on Production Planning">
                      <Settings className="w-4 h-4" />
                      View Assignments
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        );
      })}

      {/* Worker Table */}
      <div className="card">
        <div className="p-4 border-b border-secondary-200">
          <h3 className="text-lg font-semibold text-secondary-900">All Workers Table</h3>
        </div>
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Worker ID</th>
                <th>Name</th>
                <th>Department</th>
                <th>Shift</th>
                <th>Availability</th>
                <th>Hours</th>
                <th>Max Hours</th>
                <th>Overtime</th>
                <th>Utilization</th>
                <th>Skills</th>
              </tr>
            </thead>
            <tbody>
              {workers?.map((worker) => (
                <tr key={worker.worker_id}>
                  <td className="font-mono text-sm">{worker.worker_id}</td>
                  <td>{worker.name}</td>
                  <td>{worker.department}</td>
                  <td>{worker.shift}</td>
                  <td>
                    <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium',
                      worker.availability === 'Available' && 'bg-success-100 text-success-700',
                      worker.availability === 'Unavailable' && 'bg-warning-100 text-warning-700',
                      worker.availability === 'On Leave' && 'bg-secondary-100 text-secondary-700'
                    )}>
                      {worker.availability}
                    </span>
                  </td>
                  <td>{worker.current_hours}</td>
                  <td>{worker.max_hours_per_week}</td>
                  <td className="text-warning-600 font-medium">{worker.overtime_hours}</td>
                  <td>{utilOf(worker).toFixed(1)}%</td>
                  <td>
                    <div className="flex flex-wrap gap-1">
                      {worker.skills.slice(0, 3).map((skill, si) => (
                        <span key={si} className="px-2 py-0.5 text-xs rounded bg-primary-100 text-primary-700">
                          {skill.machine_type}
                        </span>
                      ))}
                      {worker.skills.length > 3 && <span className="px-2 py-0.5 text-xs rounded bg-secondary-100 text-secondary-600">+{worker.skills.length - 3}</span>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}