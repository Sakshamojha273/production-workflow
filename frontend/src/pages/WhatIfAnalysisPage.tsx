import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useScenarios, usePlans } from '../hooks/useData';
import { ChartCard } from '../components/ChartCard';
import { cn, formatNumber } from '../utils/helpers';
import { api } from '../services/api';
import {
  Plus,
  BarChart3,
  TrendingUp,
  Settings,
  CheckCircle,
  XCircle,
  ChevronRight,
} from 'lucide-react';

/** "+12.5%" when a % change is defined, else the absolute change ("+87"). */
function formatMetricChange(metric: { change_pct?: number | null; change?: number; baseline?: number; scenario?: number }): string {
  if (typeof metric.change_pct === 'number') {
    return `${metric.change_pct >= 0 ? '+' : ''}${metric.change_pct.toFixed(1)}%`;
  }
  const delta = typeof metric.change === 'number'
    ? metric.change
    : (Number(metric.scenario) || 0) - (Number(metric.baseline) || 0);
  if (!delta) return '0';
  return `${delta > 0 ? '+' : ''}${delta.toLocaleString()} (from 0)`;
}

type Verdict = 'Improvement' | 'Trade-off' | 'Worse' | 'No change';

/**
 * Overall verdict from fulfilment and cost (same rule as the backend's
 * scenario_verdict): Improvement only if fulfilment >= baseline AND cost <=
 * baseline; Worse if both are worse-or-equal; otherwise a Trade-off. Used as a
 * fallback for comparisons saved before the API returned `verdict`.
 */
function scenarioVerdict(metrics: any[] = []): { verdict: Verdict; reason: string } | null {
  const find = (name: string) => metrics.find((m) => m.metric === name);
  const ful = find('Fulfillment Rate %');
  const cost = find('Total Cost');
  if (!ful || !cost) return null;
  const fd = Number(ful.change ?? (ful.scenario - ful.baseline)) || 0;
  const cd = Number(cost.change ?? (cost.scenario - cost.baseline)) || 0;
  const f = Math.abs(fd) < 1e-9 ? 0 : Math.sign(fd);
  const c = Math.abs(cd) < 1e-9 ? 0 : Math.sign(cd);
  const reason = `Fulfilment ${fd >= 0 ? '+' : ''}${fd.toFixed(1)} pts, cost ${formatMetricChange(cost)}`;
  if (f === 0 && c === 0) return { verdict: 'No change', reason };
  if (f >= 0 && c <= 0) return { verdict: 'Improvement', reason };
  if (f <= 0 && c >= 0) return { verdict: 'Worse', reason };
  return { verdict: 'Trade-off', reason };
}

const VERDICT_STYLE: Record<Verdict, string> = {
  Improvement: 'bg-success-100 text-success-700',
  'Trade-off': 'bg-warning-100 text-warning-700',
  Worse: 'bg-danger-100 text-danger-700',
  'No change': 'bg-secondary-100 text-secondary-600',
};

export function WhatIfAnalysisPage() {
  const { data: scenarios, loading: scenariosLoading, create, run } = useScenarios();
  const { data: plans } = usePlans();

  const [activeTab, setActiveTab] = useState<'create' | 'compare'>('create');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creating, setCreating] = useState(false);
  const [running, setRunning] = useState<string | null>(null);
  const [selectedScenarioId, setSelectedScenarioId] = useState<string | null>(null);
  const [forecastHorizon, setForecastHorizon] = useState(7);
  const [baselineForecast, setBaselineForecast] = useState<number | null>(null);
  const [forecastError, setForecastError] = useState<string | null>(null);

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    demand_change_pct: 0,
    machine_availability_change_pct: 0,
    worker_availability_change_pct: 0,
    overtime_limit_change_pct: 0,
    production_target_change_pct: 0,
    inventory_change_pct: 0,
    machine_failure_ids: [] as string[],
  });

  useEffect(() => {
    api.getForecasts({ horizon_days: forecastHorizon })
      .then((result) => {
        setBaselineForecast((result.forecasts || []).reduce(
          (sum: number, item: { predicted_demand: number }) => sum + item.predicted_demand,
          0,
        ));
        setForecastError(null);
      })
      .catch((error: unknown) => {
        setForecastError(error instanceof Error ? error.message : 'Unable to load the saved forecast.');
        setBaselineForecast(null);
      });
  }, [forecastHorizon]);

  const handleCreate = async () => {
    setCreating(true);
    try {
      await create(formData);
      setShowCreateModal(false);
      setFormData({
        name: '',
        description: '',
        demand_change_pct: 0,
        machine_availability_change_pct: 0,
        worker_availability_change_pct: 0,
        overtime_limit_change_pct: 0,
        production_target_change_pct: 0,
        inventory_change_pct: 0,
        machine_failure_ids: [],
      });
    } catch (error) {
      console.error('Failed to create scenario:', error);
    } finally {
      setCreating(false);
    }
  };

  const handleRun = async (scenarioId: string) => {
    // The API returns enum values ("Approved", "Generated"); compare case-insensitively.
    const baselinePlan =
      plans.find(p => p.status?.toLowerCase() === 'approved') ??
      plans.find(p => p.status?.toLowerCase() === 'generated');
    if (!baselinePlan?.optimization_run_id) {
      alert('No baseline plan available. Generate and approve a plan first.');
      return;
    }
    setRunning(scenarioId);
    try {
      await run(scenarioId, baselinePlan.optimization_run_id);
    } catch (error) {
      console.error('Failed to run scenario:', error);
      const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      alert(`Scenario run failed${typeof detail === 'string' ? `: ${detail}` : ''}`);
    } finally {
      setRunning(null);
    }
  };

  const completedScenarios = scenarios?.filter(s => s.status?.toLowerCase() === 'completed') || [];
  // Compare shows the scenario whose button was clicked (previously always the first one).
  const selectedScenario = completedScenarios.find(s => s.scenario_id === selectedScenarioId) || completedScenarios[0];
  const scenarioForecast = baselineForecast === null
    ? null
    : Math.max(0, baselineForecast * (1 + formData.demand_change_pct / 100));
  const forecastDifference = scenarioForecast === null || baselineForecast === null
    ? null
    : scenarioForecast - baselineForecast;
  const forecastDifferencePct = forecastDifference === null || !baselineForecast
    ? null
    : (forecastDifference / baselineForecast) * 100;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">What-If Analysis</h1>
          <p className="text-secondary-500">Simulate scenarios and compare outcomes</p>
        </div>
        <button onClick={() => setShowCreateModal(true)} className="btn-primary" disabled={creating}>
          <Plus className="w-4 h-4" />
          Create Scenario
        </button>
      </div>

      <section className="card space-y-4 p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="font-semibold text-secondary-900">Forecast demand scenario</h2>
            <p className="text-sm text-secondary-500">Apply a demand change to a saved forecast, then carry the same adjustment into scenario optimization.</p>
          </div>
          <Link to="/analytics/demand-forecast" className="text-sm font-medium text-primary-700 hover:underline">View baseline forecast</Link>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {[7, 14, 30].map((days) => (
            <button key={days} type="button" className={cn(
              'rounded-lg px-3 py-2 text-sm font-medium',
              forecastHorizon === days ? 'bg-primary-600 text-white' : 'bg-secondary-100 text-secondary-700',
            )} onClick={() => setForecastHorizon(days)}>
              {days} days
            </button>
          ))}
          {[-10, 10, 20].map((change) => (
            <button key={change} type="button" className="btn-secondary text-sm" onClick={() => setFormData({ ...formData, demand_change_pct: change })}>
              {change > 0 ? '+' : ''}{change}%
            </button>
          ))}
          <label className="flex items-center gap-2 text-sm text-secondary-700">
            Custom change %
            <input aria-label="Custom demand change percentage" className="input w-28" type="number" value={formData.demand_change_pct} onChange={(event) => setFormData({ ...formData, demand_change_pct: Number(event.target.value) })} />
          </label>
        </div>
        {forecastError && <p role="alert" className="text-sm text-danger-700">{forecastError}</p>}
        {baselineForecast === 0 && <p className="text-sm text-secondary-500">No forecast values are saved for this horizon. Generate a baseline first.</p>}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <ScenarioForecastValue label={`Baseline forecast (${forecastHorizon} days)`} value={baselineForecast === null ? '—' : formatNumber(baselineForecast)} />
          <ScenarioForecastValue label="Scenario forecast" value={scenarioForecast === null ? '—' : formatNumber(scenarioForecast)} />
          <ScenarioForecastValue label="Difference" value={forecastDifference === null ? '—' : `${forecastDifference >= 0 ? '+' : ''}${formatNumber(forecastDifference)} (${forecastDifferencePct?.toFixed(1)}%)`} />
        </div>
        <p className="text-xs text-secondary-500">Scenario calculations do not modify saved baseline forecasts. The selected demand change is stored with the scenario and applied only when you run that scenario against a plan.</p>
      </section>

      {/* Scenario List */}
      <div className="card">
        <div className="p-4 border-b border-secondary-200">
          <h3 className="text-lg font-semibold text-secondary-900">Scenarios</h3>
        </div>
        <div className="divide-y divide-secondary-200">
          {scenariosLoading && <p className="p-4 text-sm text-secondary-500">Loading scenarios...</p>}
          {scenarios?.map((scenario) => (
            <div key={scenario.scenario_id} className="p-4 flex items-center justify-between hover:bg-secondary-50">
              <div className="flex items-center gap-4">
                <div className="p-3 rounded-lg bg-primary-100 text-primary-600">
                  <Settings className="w-6 h-6" />
                </div>
                <div>
                  <h4 className="font-medium text-secondary-900">{scenario.name}</h4>
                  <p className="text-sm text-secondary-500">{scenario.description || 'No description'}</p>
                  <div className="flex items-center gap-4 mt-1 text-xs text-secondary-400">
                    <span>Demand: {scenario.demand_change_pct >= 0 ? '+' : ''}{scenario.demand_change_pct}%</span>
                    <span>Machines: {scenario.machine_availability_change_pct >= 0 ? '+' : ''}{scenario.machine_availability_change_pct}%</span>
                    <span>Workers: {scenario.worker_availability_change_pct >= 0 ? '+' : ''}{scenario.worker_availability_change_pct}%</span>
                    <span>Overtime: {scenario.overtime_limit_change_pct >= 0 ? '+' : ''}{scenario.overtime_limit_change_pct}%</span>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className={cn(
                  'px-2 py-1 rounded-full text-xs font-medium',
                  scenario.status?.toLowerCase() === 'completed' && 'bg-success-100 text-success-700',
                  scenario.status?.toLowerCase() === 'running' && 'bg-warning-100 text-warning-700',
                  scenario.status?.toLowerCase() === 'failed' && 'bg-danger-100 text-danger-700',
                  scenario.status?.toLowerCase() === 'draft' && 'bg-secondary-100 text-secondary-700',
                )}>
                  {scenario.status}
                </span>
                {['draft', 'failed'].includes(scenario.status?.toLowerCase()) && (
                  <button
                    onClick={() => handleRun(scenario.scenario_id)}
                    disabled={running === scenario.scenario_id}
                    className="btn-primary text-sm"
                  >
                    {running === scenario.scenario_id ? (
                      <span className="flex items-center gap-2">
                        <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                        Running...
                      </span>
                    ) : (
                      'Run'
                    )}
                  </button>
                )}
                {scenario.status?.toLowerCase() === 'completed' && (
                  <button className="btn-secondary text-sm" onClick={() => { setSelectedScenarioId(scenario.scenario_id); setActiveTab('compare'); }}>
                    Compare
                  </button>
                )}
              </div>
            </div>
          ))}
          {!scenariosLoading && scenarios?.length === 0 && (
            <div className="p-12 text-center">
              <BarChart3 className="w-16 h-16 text-secondary-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-secondary-900 mb-2">No scenarios created</h3>
              <p className="text-secondary-500 mb-4">Create a scenario to simulate what-if scenarios</p>
              <button onClick={() => setShowCreateModal(true)} className="btn-primary">
                <Plus className="w-4 h-4" />
                Create Scenario
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Comparison View */}
      {activeTab === 'compare' && selectedScenario && selectedScenario.comparison_results && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-secondary-900">Scenario Comparison</h2>
            <button onClick={() => setActiveTab('create')} className="btn-secondary text-sm">
              <ChevronRight className="w-4 h-4" />
              Back to Scenarios
            </button>
          </div>

          <div className="card">
            <div className="p-4 border-b border-secondary-200">
              <h3 className="text-lg font-semibold text-secondary-900">{selectedScenario.name} vs Baseline</h3>
              {(() => {
                const cr = selectedScenario.comparison_results;
                const computed = scenarioVerdict(cr.metrics);
                const verdict = (cr.verdict as Verdict | undefined) || computed?.verdict;
                const reason = cr.verdict_reason || computed?.reason;
                if (!verdict) return null;
                return (
                  <p className="mt-2 flex flex-wrap items-center gap-2 text-sm text-secondary-600" data-testid="scenario-verdict">
                    <span className={cn('px-2 py-0.5 rounded-full text-xs font-semibold', VERDICT_STYLE[verdict] || VERDICT_STYLE['No change'])}>
                      Overall: {verdict}
                    </span>
                    <span>{reason}</span>
                    <span className="text-secondary-400">· Improvement = fulfilment ≥ baseline and cost ≤ baseline</span>
                  </p>
                );
              })()}
            </div>
            <div className="p-4">
              <div className="table-container">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Metric</th>
                      <th className="text-right">Baseline</th>
                      <th className="text-right">Scenario</th>
                      <th className="text-right">Change</th>
                      <th>Impact</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedScenario.comparison_results.metrics?.map((metric: any, index: number) => (
                      <tr key={index}>
                        <td className="font-medium">{metric.metric}</td>
                        <td className="text-right">{typeof metric.baseline === 'number' ? metric.baseline.toLocaleString() : metric.baseline}</td>
                        <td className="text-right">{typeof metric.scenario === 'number' ? metric.scenario.toLocaleString() : metric.scenario}</td>
                        <td className={cn('text-right font-medium', metric.improvement === true ? 'text-success-600' : metric.improvement === false ? 'text-danger-600' : 'text-secondary-500')}>
                          {formatMetricChange(metric)}
                        </td>
                        <td>
                          {metric.improvement === null || metric.improvement === undefined ? (
                            <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-secondary-100 text-secondary-600">No change</span>
                          ) : (
                            <span className={cn('flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium', metric.improvement ? 'bg-success-100 text-success-700' : 'bg-danger-100 text-danger-700')}>
                              {metric.improvement ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                              {metric.improvement ? 'Better' : 'Worse'}
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Comparison Chart */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <ChartCard title="Cost Comparison" subtitle="Baseline vs Scenario" icon={<BarChart3 className="w-5 h-5" />}>
              <ComparisonBarChart metrics={selectedScenario.comparison_results.metrics} />
            </ChartCard>
            <ChartCard title="Utilization Comparison" subtitle="Machine & Workforce" icon={<TrendingUp className="w-5 h-5" />}>
              <UtilizationComparisonChart metrics={selectedScenario.comparison_results.metrics} />
            </ChartCard>
          </div>
        </div>
      )}

      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-xl rounded-xl bg-white p-6 shadow-xl" role="dialog" aria-modal="true" aria-labelledby="create-scenario-title">
            <form
              className="space-y-4"
              onSubmit={(event) => {
                event.preventDefault();
                void handleCreate();
              }}
            >
              <div className="flex items-center justify-between">
                <h2 id="create-scenario-title" className="text-xl font-semibold text-secondary-900">Create Scenario</h2>
                <button type="button" className="text-secondary-500 hover:text-secondary-900" onClick={() => setShowCreateModal(false)} aria-label="Close">
                  <XCircle className="h-5 w-5" />
                </button>
              </div>
              <label className="block text-sm font-medium text-secondary-700">
                Name
                <input
                  className="input mt-1"
                  value={formData.name}
                  onChange={(event) => setFormData({ ...formData, name: event.target.value })}
                  required
                />
              </label>
              <label className="block text-sm font-medium text-secondary-700">
                Description
                <textarea
                  className="input mt-1"
                  value={formData.description}
                  onChange={(event) => setFormData({ ...formData, description: event.target.value })}
                  rows={2}
                />
              </label>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {([
                  ['demand_change_pct', 'Demand change (%)'],
                  ['machine_availability_change_pct', 'Machine availability change (%)'],
                  ['worker_availability_change_pct', 'Worker availability change (%)'],
                  ['overtime_limit_change_pct', 'Overtime limit change (%)'],
                  ['production_target_change_pct', 'Production target change (%)'],
                  ['inventory_change_pct', 'Inventory change (%)'],
                ] as const).map(([key, label]) => (
                  <label key={key} className="block text-sm font-medium text-secondary-700">
                    {label}
                    <input
                      className="input mt-1"
                      type="number"
                      value={formData[key]}
                      onChange={(event) => setFormData({ ...formData, [key]: Number(event.target.value) })}
                    />
                  </label>
                ))}
              </div>
              <div className="flex justify-end gap-3">
                <button type="button" className="btn-secondary" onClick={() => setShowCreateModal(false)}>Cancel</button>
                <button type="submit" className="btn-primary" disabled={creating}>
                  {creating ? 'Creating...' : 'Create Scenario'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

function ComparisonBarChart({ metrics }: { metrics: any[] }) {
  const costMetrics = metrics.filter(m => m.metric.includes('Cost') || m.metric.includes('Overtime') || m.metric.includes('Late'));
  if (!costMetrics.length) return <div className="h-64 flex items-center justify-center text-secondary-400">No cost metrics</div>;

  const chartData = costMetrics.map(m => ({
    name: m.metric,
    baseline: m.baseline,
    scenario: m.scenario,
  }));

  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} tick={{ fill: '#64748b' }} />
          <YAxis stroke="#94a3b8" fontSize={11} tick={{ fill: '#64748b' }} />
          <Tooltip />
          <Legend />
          <Bar dataKey="baseline" name="Baseline" fill="#94a3b8" radius={[4, 4, 0, 0]} />
          <Bar dataKey="scenario" name="Scenario" fill="#3b82f6" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function UtilizationComparisonChart({ metrics }: { metrics: any[] }) {
  const utilMetrics = metrics.filter(m => m.metric.includes('Utilization') || m.metric.includes('Fulfillment'));
  if (!utilMetrics.length) return <div className="h-64 flex items-center justify-center text-secondary-400">No utilization metrics</div>;

  const chartData = utilMetrics.map(m => ({
    name: m.metric,
    baseline: m.baseline,
    scenario: m.scenario,
  }));

  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} tick={{ fill: '#64748b' }} />
          <YAxis stroke="#94a3b8" fontSize={11} tick={{ fill: '#64748b' }} domain={[0, 100]} />
          <Tooltip />
          <Legend />
          <Bar dataKey="baseline" name="Baseline" fill="#94a3b8" radius={[4, 4, 0, 0]} />
          <Bar dataKey="scenario" name="Scenario" fill="#22c55e" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function ScenarioForecastValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-secondary-50 p-4">
      <p className="text-sm text-secondary-500">{label}</p>
      <p className="mt-1 text-xl font-semibold text-secondary-900">{value}</p>
    </div>
  );
}

import { ResponsiveContainer, BarChart, Bar, CartesianGrid, XAxis, YAxis, Tooltip, Legend } from 'recharts';