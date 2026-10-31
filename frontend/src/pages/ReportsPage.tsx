import { useState } from 'react';
import { cn, format } from '../utils/helpers';
import {
  Download,
  Calendar,
  Factory,
  Users,
  BarChart3,
  Wrench,
  Brain,
  DollarSign,
  RefreshCw,
  Settings,
  Plus,
} from 'lucide-react';

const REPORT_TYPES = [
  { id: 'production', name: 'Production Report', icon: Factory, description: 'Detailed production orders, quantities, and costs', color: 'bg-blue-100 text-blue-600' },
  { id: 'workforce', name: 'Workforce Report', icon: Users, description: 'Worker assignments, hours, overtime, and skills', color: 'bg-green-100 text-green-600' },
  { id: 'machine_utilization', name: 'Machine Utilization Report', icon: BarChart3, description: 'Machine utilization, capacity, and performance metrics', color: 'bg-purple-100 text-purple-600' },
  { id: 'maintenance', name: 'Maintenance Report', icon: Wrench, description: 'Maintenance schedules, history, and costs', color: 'bg-orange-100 text-orange-600' },
  { id: 'demand_forecast', name: 'Demand Forecast Report', icon: Brain, description: 'Forecasted demand vs actuals with accuracy metrics', color: 'bg-pink-100 text-pink-600' },
  { id: 'optimization', name: 'Optimization Report', icon: Settings, description: 'Optimization runs, objectives, and results', color: 'bg-indigo-100 text-indigo-600' },
  { id: 'cost', name: 'Cost Report', icon: DollarSign, description: 'Production costs, overtime costs, and cost analysis', color: 'bg-red-100 text-red-600' },
];

const FORMATS = [
  { id: 'csv', name: 'CSV', description: 'Comma-separated values for Excel' },
  { id: 'pdf', name: 'PDF', description: 'Portable document format' },
];

export function ReportsPage() {
  const [dateRange, setDateRange] = useState({
    start: format(new Date(new Date().setDate(new Date().getDate() - 30)), 'yyyy-MM-dd'),
    end: format(new Date(), 'yyyy-MM-dd'),
  });
  const [selectedFormat, setSelectedFormat] = useState('csv');
  const [generating, setGenerating] = useState<string | null>(null);
  const [generatedReports, setGeneratedReports] = useState<any[]>([]);

  const handleGenerate = async (reportType: string) => {
    setGenerating(reportType);
    // Simulate report generation
    await new Promise(resolve => setTimeout(resolve, 2000));
    const newReport = {
      id: `RPT-${Date.now().toString(36).toUpperCase()}`,
      type: reportType,
      format: selectedFormat.toUpperCase(),
      dateRange: `${dateRange.start} to ${dateRange.end}`,
      status: 'Completed',
      createdAt: new Date().toISOString(),
      downloadUrl: '#',
    };
    setGeneratedReports(prev => [newReport, ...prev]);
    setGenerating(null);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Reports</h1>
          <p className="text-secondary-500">Generate and download production planning reports</p>
        </div>
      </div>

      {/* Report Configuration */}
      <div className="card p-6">
        <h3 className="text-lg font-semibold text-secondary-900 mb-4">Report Configuration</h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
          <div>
            <label className="label">Date Range</label>
            <div className="flex gap-2">
              <input
                type="date"
                value={dateRange.start}
                onChange={e => setDateRange({ ...dateRange, start: e.target.value })}
                className="input flex-1"
              />
              <span className="flex items-center text-secondary-400">to</span>
              <input
                type="date"
                value={dateRange.end}
                onChange={e => setDateRange({ ...dateRange, end: e.target.value })}
                className="input flex-1"
              />
            </div>
          </div>
          <div>
            <label className="label">Format</label>
            <select value={selectedFormat} onChange={e => setSelectedFormat(e.target.value)} className="input">
              {FORMATS.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}
            </select>
          </div>
        </div>
      </div>

      {/* Report Types */}
      <div className="card">
        <div className="p-4 border-b border-secondary-200">
          <h3 className="text-lg font-semibold text-secondary-900">Available Reports</h3>
        </div>
        <div className="p-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {REPORT_TYPES.map(report => (
              <div key={report.id} className="p-4 border border-secondary-200 rounded-lg hover:border-primary-300 hover:shadow-card-hover transition-all cursor-pointer"
                onClick={() => handleGenerate(report.id)}
              >
                <div className="flex items-start gap-4">
                  <div className={cn('p-3 rounded-lg flex-shrink-0', report.color)}>
                    <report.icon className="w-6 h-6" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h4 className="font-medium text-secondary-900">{report.name}</h4>
                    <p className="text-sm text-secondary-500 mt-1">{report.description}</p>
                    <div className="flex items-center gap-3 mt-3 pt-3 border-t border-secondary-200">
                      <span className="text-xs text-secondary-500">{selectedFormat.toUpperCase()}</span>
                      <button className="btn-primary text-sm flex-1" disabled={generating === report.id}>
                        {generating === report.id ? (
                          <span className="flex items-center justify-center gap-2">
                            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                            Generating...
                          </span>
                        ) : (
                          <span className="flex items-center justify-center gap-2">
                            <Download className="w-4 h-4" />
                            Generate
                          </span>
                        )}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Generated Reports History */}
      <div className="card">
        <div className="p-4 border-b border-secondary-200 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-secondary-900">Generated Reports</h3>
          <button className="btn-secondary text-sm">
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Report ID</th>
                <th>Type</th>
                <th>Format</th>
                <th>Date Range</th>
                <th>Status</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {generatedReports.map((report, index) => (
                <tr key={index}>
                  <td className="font-mono text-sm">{report.id}</td>
                  <td>
                    <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-secondary-100 text-secondary-700">
                      {report.type.replace('_', ' ')}
                    </span>
                  </td>
                  <td>{report.format}</td>
                  <td>{report.dateRange}</td>
                  <td>
                    <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium',
                      report.status === 'Completed' && 'bg-success-100 text-success-700',
                      report.status === 'Generating' && 'bg-warning-100 text-warning-700',
                      report.status === 'Failed' && 'bg-danger-100 text-danger-700'
                    )}>
                      {report.status === 'Generating' ? (
                        <span className="flex items-center gap-1">
                          <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                          {report.status}
                        </span>
                      ) : (
                        report.status
                      )}
                    </span>
                  </td>
                  <td className="text-sm text-secondary-500">{format(new Date(report.createdAt), 'MMM d, yyyy HH:mm')}</td>
                  <td>
                    {report.status === 'Completed' && (
                      <a href={report.downloadUrl} className="btn-secondary text-sm" download>
                        <Download className="w-4 h-4" />
                        Download
                      </a>
                    )}
                  </td>
                </tr>
              ))}
              {generatedReports.length === 0 && (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-secondary-500">No reports generated yet</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Scheduled Reports */}
      <div className="card">
        <div className="p-4 border-b border-secondary-200 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-secondary-900">Scheduled Reports</h3>
          <button className="btn-primary text-sm">
            <Plus className="w-4 h-4" />
            Schedule Report
          </button>
        </div>
        <div className="p-4 text-center text-secondary-500">
          <Calendar className="w-12 h-12 mx-auto mb-2 text-secondary-300" />
          <p>No scheduled reports configured</p>
          <p className="text-sm mt-1">Set up automated report delivery</p>
        </div>
      </div>
    </div>
  );
}