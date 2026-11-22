import { useMemo, useState } from 'react';
import { usePlans, useLatestPlan, useProducts, useMachines, useInventory } from '../hooks/useData';
import { BarChartComponent, DonutChartComponent } from '../charts/ChartComponents';
import { KPICard } from '../components/KPICard';
import { ChartCard } from '../components/ChartCard';
import { cn, formatNumber, formatCurrency, getPriorityColor, getOrderStatusColor } from '../utils/helpers';
import { api } from '../services/api';
import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import type { Forecast, InventoryItem, PlanningDefaults } from '../types';
import {
  Plus,
  CheckCircle,
  Package,
  Factory,
  Clock,
  DollarSign,
  Users,
} from 'lucide-react';
import { format } from 'date-fns';

export function ProductionPlanningPage() {
  const { data: plans, generate } = usePlans();
  const { data: latestPlan, refetch: refetchLatestPlan } = useLatestPlan();
  const { data: products } = useProducts();
  const { data: machines } = useMachines();
  const { data: inventoryRows } = useInventory();
  const [forecastRows, setForecastRows] = useState<Forecast[]>([]);
  const [forecastPlanningError, setForecastPlanningError] = useState<string | null>(null);

  useEffect(() => {
    api.getForecasts({ horizon_days: 7 })
      .then((result) => setForecastRows(result.forecasts || []))
      .catch((error: unknown) => {
        setForecastPlanningError(error instanceof Error ? error.message : 'Unable to load demand forecasts.');
      });
  }, []);

  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [formData, setFormData] = useState({
    start_date: format(new Date(), 'yyyy-MM-dd'),
    end_date: format(new Date(new Date().setDate(new Date().getDate() + 6)), 'yyyy-MM-dd'),
    product_ids: [] as string[],
    machine_ids: [] as string[],
    max_overtime_hours: 8,
  });
  const [generateError, setGenerateError] = useState<string | null>(null);
  // Default the window to the backend's planning reference date / open-order
  // window, so historical datasets don't produce an empty plan.
  const [planningDefaults, setPlanningDefaults] = useState<PlanningDefaults | null>(null);
  useEffect(() => {
    api.getPlanningDefaults()
      .then((defaults: PlanningDefaults) => {
        setPlanningDefaults(defaults);
        setFormData((current) => ({ ...current, start_date: defaults.suggested_start, end_date: defaults.suggested_end }));
      })
      .catch(() => { /* keep the today-based fallback */ });
  }, []);
  const [activeTab, setActiveTab] = useState<'overview' | 'plan' | 'assignments'>('overview');

  const handleGenerate = async () => {
    setGenerating(true);
    setGenerateError(null);
    try {
      await generate({
        start_date: formData.start_date,
        end_date: formData.end_date,
        product_ids: formData.product_ids.length > 0 ? formData.product_ids : undefined,
        machine_ids: formData.machine_ids.length > 0 ? formData.machine_ids : undefined,
        max_overtime_hours: formData.max_overtime_hours,
      });
      await refetchLatestPlan(); // show the new plan (the list endpoint has no items)
      setShowGenerateModal(false);
    } catch (error) {
      setGenerateError(error instanceof Error ? error.message : 'Failed to generate plan');
    } finally {
      setGenerating(false);
    }
  };

  const plan = latestPlan || plans[0];

  // ---- Overview chart data (all derived from the plan the API returned) ----
  const costByProduct = useMemo(() => {
    const totals = new Map<string, number>();
    (plan?.items || []).forEach((item) => {
      const key = item.product_name || item.product_id;
      totals.set(key, (totals.get(key) || 0) + (item.cost || 0));
    });
    return [...totals.entries()]
      .map(([name, value]) => ({ name, value: Math.round(value) }))
      .filter((row) => row.value > 0)
      .sort((a, b) => b.value - a.value);
  }, [plan]);

  const machineUtilData = useMemo(() => {
    const byMachine = (plan?.notes?.machine_utilization_by_machine || {}) as Record<string, number>;
    return Object.entries(byMachine)
      .map(([machineId, value]) => ({
        name: machines?.find((m) => m.machine_id === machineId)?.name || machineId,
        utilization: Number(value) || 0,
      }))
      .sort((a, b) => b.utilization - a.utilization);
  }, [plan, machines]);

  const shortWorkerName = (name?: string | null, id?: string) =>
    (name || id || '').replace(/^.*_Operator_/, 'Op ');
  const workerUtilData = useMemo(() =>
    [...(plan?.worker_summary || [])]
      .sort((a, b) => b.utilization - a.utilization)
      .slice(0, 15)
      .map((w) => ({ name: shortWorkerName(w.worker_name, w.worker_id), utilization: w.utilization, hours: w.hours })),
  [plan]);
  const overtimeData = useMemo(() =>
    (plan?.worker_summary || [])
      .filter((w) => w.overtime_hours > 0)
      .sort((a, b) => b.overtime_hours - a.overtime_hours)
      .slice(0, 15)
      .map((w) => ({ name: shortWorkerName(w.worker_name, w.worker_id), overtime: w.overtime_hours })),
  [plan]);
  const overtimeByWorker = useMemo(() => {
    const map = new Map<string, number>();
    (plan?.worker_summary || []).forEach((w) => map.set(w.worker_id, w.overtime_hours));
    return map;
  }, [plan]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Production Planning</h1>
          <p className="text-secondary-500">Generate and manage optimized production plans</p>
        </div>
        <div className="flex items-center gap-2">
          <button className="btn-secondary" onClick={() => { setGenerateError(null); setShowGenerateModal(true); }} disabled={generating}>
            <Plus className="w-4 h-4" />
            Generate Plan
          </button>
        </div>
      </div>

      <section className="card overflow-hidden">
        <div className="flex flex-col gap-2 border-b border-secondary-200 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="font-semibold text-secondary-900">Forecast-based planning recommendation</h2>
            <p className="text-sm text-secondary-500">Advisory only. Existing production plans, including approved plans, are not changed.</p>
          </div>
          <Link to="/analytics/demand-forecast" className="text-sm font-medium text-primary-700 hover:underline">View forecast</Link>
        </div>
        {forecastPlanningError ? (
          <p role="alert" className="p-4 text-sm text-danger-700">{forecastPlanningError}</p>
        ) : forecastRows.length === 0 ? (
          <p className="p-4 text-sm text-secondary-500">No 7-day forecast is available. Generate one on the Demand Forecast page.</p>
        ) : (
          <div className="table-container">
            <table className="table">
              <thead>
                <tr><th>Product</th><th>Forecast Demand</th><th>Available Inventory</th><th>Safety Stock</th><th>Recommended Production</th><th>Expected Shortfall</th><th>Expected Surplus</th></tr>
              </thead>
              <tbody>
                {Array.from(new Set(forecastRows.map((row) => row.product_id))).map((id) => {
                  const rows = forecastRows.filter((row) => row.product_id === id);
                  const forecastDemand = rows.reduce((sum, row) => sum + row.predicted_demand, 0);
                  const inventory: InventoryItem | undefined = inventoryRows.find((item) => item.product_id === id);
                  const stock = inventory?.current_level || 0;
                  const safetyStock = inventory?.safety_stock || 0;
                  const recommendedProduction = Math.max(0, forecastDemand + safetyStock - stock);
                  const productName = rows[0]?.product_name || products?.find((product) => product.product_id === id)?.name || id;
                  return (
                    <tr key={id}>
                      <td className="font-medium">{productName}</td>
                      <td>{formatNumber(forecastDemand)}</td>
                      <td>{formatNumber(stock)}</td>
                      <td>{formatNumber(safetyStock)}</td>
                      <td className="font-semibold">{formatNumber(recommendedProduction)}</td>
                      <td>{formatNumber(Math.max(0, forecastDemand - stock))}</td>
                      <td>{formatNumber(Math.max(0, stock - forecastDemand - safetyStock))}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Plan Overview / KPIs */}
      {plan && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <KPICard
            title="Total Demand"
            value={formatNumber(plan.total_demand)}
            icon={<Package className="w-5 h-5" />}
            iconColor="bg-blue-100 text-blue-600"
          />
          <KPICard
            title="Planned Production"
            value={formatNumber(plan.total_production)}
            icon={<Factory className="w-5 h-5" />}
            iconColor="bg-green-100 text-green-600"
          />
          <KPICard
            title="Total Cost"
            value={formatCurrency(plan.total_cost)}
            icon={<DollarSign className="w-5 h-5" />}
            iconColor="bg-purple-100 text-purple-600"
          />
          <KPICard
            title="Fulfillment Rate"
            value={`${plan.fulfillment_rate.toFixed(1)}%`}
            icon={<CheckCircle className="w-5 h-5" />}
            iconColor="bg-orange-100 text-orange-600"
            status={plan.fulfillment_rate >= 95 ? 'Healthy' : plan.fulfillment_rate >= 80 ? 'Warning' : 'Critical'}
          />
        </div>
      )}

      {/* Tabs */}
      <div className="card">
        <div className="border-b border-secondary-200">
          <nav className="flex gap-4 p-4" aria-label="Plan tabs">
            <button
              onClick={() => setActiveTab('overview')}
              className={cn(
                'px-4 py-2 text-sm font-medium rounded-lg transition-colors',
                activeTab === 'overview'
                  ? 'bg-primary-50 text-primary-700'
                  : 'text-secondary-600 hover:text-secondary-900 hover:bg-secondary-100'
              )}
            >
              Overview
            </button>
            <button
              onClick={() => setActiveTab('plan')}
              className={cn(
                'px-4 py-2 text-sm font-medium rounded-lg transition-colors',
                activeTab === 'plan'
                  ? 'bg-primary-50 text-primary-700'
                  : 'text-secondary-600 hover:text-secondary-900 hover:bg-secondary-100'
              )}
            >
              Production Plan
            </button>
            <button
              onClick={() => setActiveTab('assignments')}
              className={cn(
                'px-4 py-2 text-sm font-medium rounded-lg transition-colors',
                activeTab === 'assignments'
                  ? 'bg-primary-50 text-primary-700'
                  : 'text-secondary-600 hover:text-secondary-900 hover:bg-secondary-100'
              )}
            >
              Assignments
            </button>
          </nav>
        </div>

        <div className="p-4">
          {activeTab === 'overview' && plan && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <ChartCard title="Cost Breakdown" subtitle={`Plan cost by product · total ${formatCurrency(plan.total_cost)}`} icon={<DollarSign className="w-5 h-5" />}>
                {costByProduct.length ? (
                  <DonutChartComponent data={costByProduct} nameKey="name" valueKey="value" height={256} showLabels={false} />
                ) : (
                  <div className="h-64 flex items-center justify-center text-secondary-400">No costed items in this plan</div>
                )}
              </ChartCard>
              <ChartCard title="Machine Utilization" subtitle={`Planned vs available units · plan average ${plan.machine_utilization.toFixed(1)}%`} icon={<Factory className="w-5 h-5" />}>
                {machineUtilData.length ? (
                  <BarChartComponent data={machineUtilData} keys={['utilization']} labels={['Utilization %']} height={256} />
                ) : (
                  <div className="h-64 flex items-center justify-center text-center text-secondary-400 px-6">
                    Per-machine utilization is recorded for plans generated after this update. Generate the plan again to see it.
                  </div>
                )}
              </ChartCard>
              <ChartCard title="Workforce Utilization" subtitle={`Regular hours used, top 15 workers · plan average ${plan.workforce_utilization.toFixed(1)}%`} icon={<Users className="w-5 h-5" />}>
                {workerUtilData.length ? (
                  <BarChartComponent data={workerUtilData} keys={['utilization']} labels={['Utilization %']} height={256} />
                ) : (
                  <div className="h-64 flex items-center justify-center text-secondary-400">No worker assignments in this plan</div>
                )}
              </ChartCard>
              <ChartCard title="Overtime Distribution" subtitle={`Overtime hours by worker · plan total ${formatNumber(plan.total_overtime)}h`} icon={<Clock className="w-5 h-5" />}>
                {overtimeData.length ? (
                  <BarChartComponent data={overtimeData} keys={['overtime']} labels={['Overtime (h)']} height={256} />
                ) : (
                  <div className="h-64 flex flex-col items-center justify-center text-secondary-400">
                    <Clock className="w-8 h-8 mb-2" />
                    No overtime needed in this plan
                  </div>
                )}
              </ChartCard>
            </div>
          )}

          {activeTab === 'plan' && plan && (
            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th>Order ID</th>
                    <th>Product</th>
                    <th>Demand</th>
                    <th>Planned</th>
                    <th>Machine</th>
                    <th>Due Date</th>
                    <th>Priority</th>
                    <th>Time (min)</th>
                    <th>Cost</th>
                    <th>Status</th>
                    <th>Worker</th>
                    <th>Shift</th>
                  </tr>
                </thead>
                <tbody>
                  {plan.items.map((item, index) => (
                    <tr key={index}>
                      <td className="font-mono text-sm">{item.order_id}</td>
                      <td>{item.product_name}</td>
                      <td>{formatNumber(item.demand)}</td>
                      <td>{formatNumber(item.planned_production)}</td>
                      <td>{item.machine_name}</td>
                      <td>{format(new Date(item.due_date), 'MMM d, yyyy')}</td>
                      <td>
                        <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', getPriorityColor(item.priority))}>
                          {item.priority}
                        </span>
                      </td>
                      <td>{item.production_time_minutes}</td>
                      <td>{formatCurrency(item.cost)}</td>
                      <td>
                        <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', getOrderStatusColor(item.status))}>
                          {item.status}
                        </span>
                      </td>
                      <td>{item.worker_name || '-'}</td>
                      <td>{item.shift || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {activeTab === 'assignments' && plan && (
            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th>Worker</th>
                    <th>Machine</th>
                    <th>Product</th>
                    <th>Date</th>
                    <th>Shift</th>
                    <th>Hours</th>
                    <th title="Worker's total overtime across the whole plan">Worker OT (plan)</th>
                    <th>Skill Match</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {plan.items.map((item) => (
                    <tr key={item.order_id}>
                      <td>{item.worker_name || 'Unassigned'}</td>
                      <td>{item.machine_name}</td>
                      <td>{item.product_name}</td>
                      <td>{format(new Date(item.due_date), 'MMM d, yyyy')}</td>
                      <td>{item.shift || '-'}</td>
                      <td>{Math.round(item.production_time_minutes / 60)}</td>
                      <td>{item.worker_id ? `${overtimeByWorker.get(item.worker_id) ?? 0}h` : '-'}</td>
                      {/* The planner only assigns workers qualified for the machine type. */}
                      <td>{item.worker_id ? '100%' : '-'}</td>
                      <td>
                        {item.worker_id ? (
                          <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-primary-100 text-primary-700">
                            Assigned
                          </span>
                        ) : (
                          <span
                            className="px-2 py-0.5 rounded-full text-xs font-medium bg-secondary-100 text-secondary-600"
                            title={item.from_inventory ? 'Filled from inventory: no production, no operator needed' : item.backlog ? 'Not produced in this window (backlog)' : 'No operator assigned'}
                          >
                            Unassigned
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Generate Plan Modal */}
      {showGenerateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-secondary-200 flex items-center justify-between">
              <h2 className="text-xl font-semibold text-secondary-900">Generate Production Plan</h2>
              <button onClick={() => setShowGenerateModal(false)} className="p-2 hover:bg-secondary-100 rounded-lg">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-6 space-y-4">
              {planningDefaults && (
                <p className="rounded-lg bg-primary-50 p-3 text-sm text-primary-800">
                  Planning reference date: <strong>{planningDefaults.reference_date}</strong>
                  {planningDefaults.reference_date_source === 'PLANNING_REFERENCE_DATE' ? ' (PLANNING_REFERENCE_DATE)' : ' (today)'}
                  {' · '}{formatNumber(planningDefaults.open_orders)} open orders due
                  {planningDefaults.open_orders_due_from ? ` ${planningDefaults.open_orders_due_from} to ${planningDefaults.open_orders_due_to}` : ' on/after that date'}
                  {' · '}max horizon {planningDefaults.max_horizon_days} days
                </p>
              )}
              {generateError && (
                <p role="alert" className="rounded-lg border border-danger-200 bg-danger-50 p-3 text-sm text-danger-700">{generateError}</p>
              )}
              <div>
                <label className="label">Start Date</label>
                <input
                  type="date"
                  value={formData.start_date}
                  onChange={(e) => setFormData({ ...formData, start_date: e.target.value })}
                  className="input"
                />
              </div>
              <div>
                <label className="label">End Date</label>
                <input
                  type="date"
                  value={formData.end_date}
                  onChange={(e) => setFormData({ ...formData, end_date: e.target.value })}
                  className="input"
                />
              </div>
              <div>
                <label className="label">Products (optional)</label>
                <select
                  multiple
                  value={formData.product_ids}
                  onChange={(e) => setFormData({ ...formData, product_ids: Array.from(e.target.selectedOptions).map(o => o.value) })}
                  className="input"
                >
                  {products?.map(p => (
                    <option key={p.product_id} value={p.product_id}>{p.name} ({p.product_id})</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">Machines (optional)</label>
                <select
                  multiple
                  value={formData.machine_ids}
                  onChange={(e) => setFormData({ ...formData, machine_ids: Array.from(e.target.selectedOptions).map(o => o.value) })}
                  className="input"
                >
                  {machines?.map(m => (
                    <option key={m.machine_id} value={m.machine_id}>{m.name} ({m.machine_id})</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">Max Overtime Hours per Day</label>
                <input
                  type="number"
                  value={formData.max_overtime_hours}
                  onChange={(e) => setFormData({ ...formData, max_overtime_hours: parseInt(e.target.value) })}
                  className="input"
                  min={0}
                  max={12}
                />
              </div>
              <div className="flex justify-end gap-3 pt-4">
                <button onClick={() => setShowGenerateModal(false)} className="btn-secondary">
                  Cancel
                </button>
                <button onClick={handleGenerate} disabled={generating} className="btn-primary">
                  {generating ? 'Generating...' : 'Generate Plan'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
