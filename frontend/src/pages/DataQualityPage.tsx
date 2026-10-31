import { useState } from 'react';
import { format } from 'date-fns';
import { useDataQuality } from '../hooks/useData';
import { cn, formatNumber } from '../utils/helpers';
import {
  CheckCircle,
  AlertCircle,
  XCircle,
  BarChart3,
  Database,
  RefreshCw,
  Eye,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';

export function DataQualityPage() {
  const { data: reports, loading, refetch } = useDataQuality();
  const [selectedReport, setSelectedReport] = useState<any>(null);

  const latestReport = reports?.[0];

  const getStatusColor = (status: string) => {
    switch (status?.toUpperCase()) {
      case 'COMPLETED': return 'bg-success-100 text-success-700';
      case 'FAILED': return 'bg-danger-100 text-danger-700';
      case 'PROCESSING': return 'bg-warning-100 text-warning-700';
      default: return 'bg-secondary-100 text-secondary-700';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status?.toUpperCase()) {
      case 'COMPLETED': return <CheckCircle className="w-4 h-4" />;
      case 'FAILED': return <XCircle className="w-4 h-4" />;
      case 'PROCESSING': return <AlertCircle className="w-4 h-4" />;
      default: return <AlertCircle className="w-4 h-4" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Data Quality</h1>
          <p className="text-secondary-500">Monitor and analyze data quality metrics</p>
        </div>
        <button onClick={refetch} className="btn-secondary" disabled={loading}>
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Latest Report Overview */}
      {latestReport && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          <div className="card p-6">
            <div className="flex items-center gap-3">
              <div className="p-3 rounded-lg bg-primary-100 text-primary-600">
                <Database className="w-6 h-6" />
              </div>
              <div>
                <p className="text-sm text-secondary-500">Quality Score</p>
                <p className="text-3xl font-bold text-secondary-900">{latestReport.quality_score.toFixed(1)}%</p>
              </div>
            </div>
          </div>
          <div className="card p-6">
            <div className="flex items-center gap-3">
              <div className="p-3 rounded-lg bg-blue-100 text-blue-600">
                <BarChart3 className="w-6 h-6" />
              </div>
              <div>
                <p className="text-sm text-secondary-500">Total Rows</p>
                <p className="text-3xl font-bold text-secondary-900">{formatNumber(latestReport.total_rows)}</p>
              </div>
            </div>
          </div>
          <div className="card p-6">
            <div className="flex items-center gap-3">
              <div className="p-3 rounded-lg bg-warning-100 text-warning-600">
                <AlertCircle className="w-6 h-6" />
              </div>
              <div>
                <p className="text-sm text-secondary-500">Missing Values</p>
                <p className="text-3xl font-bold text-secondary-900">{formatNumber(latestReport.missing_values)}</p>
              </div>
            </div>
          </div>
          <div className="card p-6">
            <div className="flex items-center gap-3">
              <div className="p-3 rounded-lg bg-orange-100 text-orange-600">
                <XCircle className="w-6 h-6" />
              </div>
              <div>
                <p className="text-sm text-secondary-500">Duplicates</p>
                <p className="text-3xl font-bold text-secondary-900">{formatNumber(latestReport.duplicate_rows)}</p>
              </div>
            </div>
          </div>
          <div className="card p-6">
            <div className="flex items-center gap-3">
              <div className="p-3 rounded-lg bg-danger-100 text-danger-600">
                <XCircle className="w-6 h-6" />
              </div>
              <div>
                <p className="text-sm text-secondary-500">Invalid Records</p>
                <p className="text-3xl font-bold text-secondary-900">{formatNumber(latestReport.invalid_records)}</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Charts */}
      {latestReport && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="card">
            <div className="p-4 border-b border-secondary-200">
              <h3 className="text-lg font-semibold text-secondary-900">Missing Values by Column</h3>
            </div>
            <div className="p-4 h-64">
              <MissingValuesChart missingByColumn={latestReport.missing_by_column} />
            </div>
          </div>
          <div className="card">
            <div className="p-4 border-b border-secondary-200">
              <h3 className="text-lg font-semibold text-secondary-900">Data Quality Breakdown</h3>
            </div>
            <div className="p-4 h-64">
              <QualityBreakdownChart report={latestReport} />
            </div>
          </div>
        </div>
      )}

      {/* Reports History */}
      <div className="card">
        <div className="p-4 border-b border-secondary-200 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-secondary-900">Quality Reports History</h3>
        </div>
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Report ID</th>
                <th>Filename</th>
                <th>Rows</th>
                <th>Columns</th>
                <th>Missing</th>
                <th>Duplicates</th>
                <th>Invalid</th>
                <th>Outliers</th>
                <th>Quality Score</th>
                <th>Status</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {reports?.map((report, index) => (
                <tr key={index}>
                  <td className="font-mono text-sm">{report.report_id}</td>
                  <td>{report.filename}</td>
                  <td>{formatNumber(report.total_rows)}</td>
                  <td>{report.total_columns}</td>
                  <td>{formatNumber(report.missing_values)}</td>
                  <td>{formatNumber(report.duplicate_rows)}</td>
                  <td>{formatNumber(report.invalid_records)}</td>
                  <td>{formatNumber(report.outliers)}</td>
                  <td className="font-medium">{report.quality_score.toFixed(1)}%</td>
                  <td>
                    <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', getStatusColor(report.status))}>
                      {getStatusIcon(report.status)} {report.status}
                    </span>
                  </td>
                  <td className="text-sm text-secondary-500">{format(new Date(report.created_at), 'MMM d, yyyy HH:mm')}</td>
                  <td>
                    <button onClick={() => setSelectedReport(report)} className="btn-secondary text-sm">
                      <Eye className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
              {reports?.length === 0 && (
                <tr>
                  <td colSpan={12} className="text-center py-8 text-secondary-500">No quality reports yet. Upload a dataset to generate one.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Report Detail Modal */}
      {selectedReport && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-secondary-200 flex items-center justify-between">
              <h2 className="text-xl font-semibold text-secondary-900">Data Quality Report: {selectedReport.filename}</h2>
              <button onClick={() => setSelectedReport(null)} className="p-2 hover:bg-secondary-100 rounded-lg">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-6 space-y-6">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-4 bg-secondary-50 rounded-lg">
                  <p className="text-sm text-secondary-500">Rows</p>
                  <p className="text-2xl font-bold text-secondary-900">{formatNumber(selectedReport.total_rows)}</p>
                </div>
                <div className="p-4 bg-secondary-50 rounded-lg">
                  <p className="text-sm text-secondary-500">Columns</p>
                  <p className="text-2xl font-bold text-secondary-900">{selectedReport.total_columns}</p>
                </div>
                <div className="p-4 bg-secondary-50 rounded-lg">
                  <p className="text-sm text-secondary-500">Quality Score</p>
                  <p className="text-2xl font-bold text-primary-600">{selectedReport.quality_score.toFixed(1)}%</p>
                </div>
                <div className="p-4 bg-secondary-50 rounded-lg">
                  <p className="text-sm text-secondary-500">Status</p>
                  <p className="text-2xl font-bold text-secondary-900">{selectedReport.status}</p>
                </div>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-4 bg-warning-50 rounded-lg border border-warning-200">
                  <p className="text-sm text-warning-700">Missing Values</p>
                  <p className="text-2xl font-bold text-warning-700">{formatNumber(selectedReport.missing_values)}</p>
                </div>
                <div className="p-4 bg-orange-50 rounded-lg border border-orange-200">
                  <p className="text-sm text-orange-700">Duplicates</p>
                  <p className="text-2xl font-bold text-orange-700">{formatNumber(selectedReport.duplicate_rows)}</p>
                </div>
                <div className="p-4 bg-danger-50 rounded-lg border border-danger-200">
                  <p className="text-sm text-danger-700">Invalid Records</p>
                  <p className="text-2xl font-bold text-danger-700">{formatNumber(selectedReport.invalid_records)}</p>
                </div>
                <div className="p-4 bg-purple-50 rounded-lg border border-purple-200">
                  <p className="text-sm text-purple-700">Outliers</p>
                  <p className="text-2xl font-bold text-purple-700">{formatNumber(selectedReport.outliers)}</p>
                </div>
              </div>

              {selectedReport.missing_by_column && (
                <div>
                  <h4 className="font-medium text-secondary-900 mb-3">Missing Values by Column</h4>
                  <div className="table-container">
                    <table className="table text-sm">
                      <thead>
                        <tr>
                          <th>Column</th>
                          <th className="text-right">Missing Count</th>
                          <th className="text-right">Missing %</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(selectedReport.missing_by_column).map(([col, count]) => (
                          <tr key={col}>
                            <td className="font-mono">{col}</td>
                            <td className="text-right">{formatNumber(count as number)}</td>
                            <td className="text-right">{((count as number) / selectedReport.total_rows * 100).toFixed(2)}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {selectedReport.column_types && (
                <div>
                  <h4 className="font-medium text-secondary-900 mb-3">Column Types</h4>
                  <div className="table-container">
                    <table className="table text-sm">
                      <thead>
                        <tr>
                          <th>Column</th>
                          <th>Type</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(selectedReport.column_types).map(([col, type]) => (
                          <tr key={col}>
                            <td className="font-mono">{col}</td>
                            <td>{String(type)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              <div className="flex justify-end gap-3 pt-4 border-t border-secondary-200">
                <button onClick={() => setSelectedReport(null)} className="btn-secondary">Close</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function MissingValuesChart({ missingByColumn }: { missingByColumn?: Record<string, number> }) {
  if (!missingByColumn) return <div className="h-full flex items-center justify-center text-secondary-400">No data</div>;

  try {
    const data = Object.entries(missingByColumn)
      .filter(([, count]) => count > 0)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 15)
      .map(([name, value]) => ({ name, value }));

    if (data.length === 0) return <div className="h-full flex items-center justify-center text-secondary-400">No missing values</div>;

    return (
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis type="number" stroke="#94a3b8" fontSize={11} tick={{ fill: '#64748b' }} />
          <YAxis dataKey="name" type="category" stroke="#94a3b8" fontSize={11} tick={{ fill: '#64748b' }} width={120} />
          <Tooltip />
          <Bar dataKey="value" fill="#f59e0b" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    );
  } catch {
    return <div className="h-full flex items-center justify-center text-secondary-400">Error parsing data</div>;
  }
}

function QualityBreakdownChart({ report }: { report: any }) {
  const chartData = [
    { name: 'Valid', value: report.total_rows - report.missing_values - report.duplicate_rows - report.invalid_records - report.outliers, color: '#22c55e' },
    { name: 'Missing', value: report.missing_values, color: '#f59e0b' },
    { name: 'Duplicates', value: report.duplicate_rows, color: '#fb923c' },
    { name: 'Invalid', value: report.invalid_records, color: '#ef4444' },
    { name: 'Outliers', value: report.outliers, color: '#8b5cf6' },
  ].filter(d => d.value > 0);

  if (chartData.length === 0) return <div className="h-full flex items-center justify-center text-secondary-400">No data</div>;

  return (
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
          label={({ name, percent }) => `${name} ${(percent * 100).toFixed(1)}%`}
        >
          {chartData.map((_, i) => <Cell key={`cell-${i}`} fill={chartData[i].color} />)}
        </Pie>
        <Tooltip />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  );
}
