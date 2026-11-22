export interface User {
  id: string;
  email: string;
  name: string;
  role: string;
}

export interface KPICard {
  title: string;
  value: string;
  trend?: number | null;
  trend_direction: 'up' | 'down' | 'neutral';
  description?: string;
  status: 'Healthy' | 'Warning' | 'Critical';
}

export interface DashboardResponse {
  kpis: KPICard[];
  charts: Record<string, any>;
  timestamp: string;
}

export interface Order {
  order_id: string;
  date: string;
  product_id: string;
  product_name: string;
  category: string;
  demand: number;
  production_quantity: number;
  machine_id: string;
  machine_name: string;
  machine_type: string;
  machine_capacity: number;
  machine_availability: number;
  maintenance_status: string;
  worker_id: string;
  worker_name: string;
  department: string;
  shift: string;
  worker_availability: number;
  production_time_minutes: number;
  overtime_hours: number;
  production_cost: number;
  machine_vibration: number;
  machine_temperature_c: number;
  machine_risk_score: number;
  next_day_demand: number;
  priority: 'Low' | 'Medium' | 'High' | 'Critical';
  due_date: string;
  status: 'Completed' | 'In Progress' | 'Pending' | 'Delayed';
  inventory_level: number;
  safety_stock: number;
}

export interface OrderListResponse {
  orders: Order[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface Product {
  product_id: string;
  name: string;
  category: string;
  base_demand: number;
  base_cost: number;
  created_at: string;
  updated_at: string;
}

export interface Machine {
  machine_id: string;
  name: string;
  type: string;
  capacity: number;
  availability: number;
  utilization: number;
  status: 'Operational' | 'Maintenance' | 'Offline';
  vibration: number;
  temperature_c: number;
  risk_score: number;
  last_maintenance?: string;
  next_maintenance?: string;
  created_at: string;
  updated_at: string;
}

export interface Worker {
  worker_id: string;
  name: string;
  department: string;
  shift: string;
  availability: 'Available' | 'Unavailable' | 'On Leave';
  max_hours_per_week: number;
  current_hours: number;
  overtime_hours: number;
  /** Regular-hour utilization % in the latest production plan. */
  utilization?: number;
  skills: WorkerSkill[];
  created_at: string;
  updated_at: string;
}

export interface WorkerSkill {
  machine_type: string;
  proficiency: number;
  certified: boolean;
}

export interface InventoryItem {
  product_id: string;
  product_name: string;
  category: string;
  current_level: number;
  safety_stock: number;
  reorder_point: number;
  max_stock: number;
  unit_cost: number;
  coverage_days: number;
  status: 'Healthy' | 'Low' | 'Critical';
  last_updated: string;
}

export interface Forecast {
  product_id: string;
  product_name: string;
  forecast_date: string;
  forecast_horizon_days: number;
  predicted_demand: number;
  lower_bound?: number;
  upper_bound?: number;
  confidence_level: number;
  model_used: string;
  model_name?: string;
  mae?: number;
  rmse?: number;
  created_at: string;
}

export interface DemandHistoryPoint {
  date: string;
  product_id: string | null;
  product_name: string;
  demand: number;
}

export interface ForecastMetrics {
  selected_model: string | null;
  metrics: Record<string, {
    mae: number | null;
    rmse: number | null;
    mape: number | null;
    wape: number | null;
    bias: number | null;
  }>;
  backtest_windows: number;
  eligible_products: number;
  method: string;
}

export interface PlanItem {
  order_id: string;
  product_id: string;
  product_name: string;
  demand: number;
  planned_production: number;
  machine_id: string;
  machine_name: string;
  due_date: string;
  priority: string;
  production_time_minutes: number;
  cost: number;
  status: string;
  worker_id?: string;
  worker_name?: string;
  shift?: string;
  from_inventory?: number;
  backlog?: number;
  late_units?: number;
  completion_date?: string | null;
  schedule?: { date: string; machine_id: string; quantity: number }[];
}

export interface ProductionPlan {
  plan_id: string;
  optimization_run_id?: string;
  start_date: string;
  end_date: string;
  total_demand: number;
  total_production: number;
  total_cost: number;
  total_overtime: number;
  late_orders: number;
  machine_utilization: number;
  workforce_utilization: number;
  fulfillment_rate: number;
  status: string;
  items: PlanItem[];
  worker_summary?: WorkerPlanSummary[];
  created_at: string;
  notes?: Record<string, unknown> | null;
}

export interface WorkerPlanSummary {
  worker_id: string;
  worker_name?: string | null;
  hours: number;
  overtime_hours: number;
  utilization: number;
}

export interface PlanningDefaults {
  reference_date: string;
  reference_date_source: 'PLANNING_REFERENCE_DATE' | 'today';
  suggested_start: string;
  suggested_end: string;
  max_horizon_days: number;
  open_orders: number;
  open_orders_due_from?: string | null;
  open_orders_due_to?: string | null;
  data_start?: string | null;
  data_end?: string | null;
}

export interface Scenario {
  scenario_id: string;
  name: string;
  description?: string;
  demand_change_pct: number;
  machine_availability_change_pct: number;
  worker_availability_change_pct: number;
  overtime_limit_change_pct: number;
  production_target_change_pct: number;
  inventory_change_pct: number;
  machine_failure_ids?: string[];
  status: string;
  comparison_results?: any;
  created_at: string;
  updated_at: string;
  completed_at?: string;
}

export interface ScenarioComparison {
  scenario_id: string;
  scenario_name: string;
  baseline_run_id: string;
  scenario_run_id: string;
  metrics: ComparisonMetric[];
  created_at: string;
}

export interface ComparisonMetric {
  metric: string;
  baseline: number;
  scenario: number;
  change_pct: number;
  improvement: boolean;
}

export interface DataQualityReport {
  report_id: string;
  filename: string;
  total_rows: number;
  total_columns: number;
  missing_values: number;
  duplicate_rows: number;
  invalid_records: number;
  outliers: number;
  quality_score: number;
  missing_by_column: Record<string, number>;
  column_types: Record<string, string>;
  sample_data: any[];
  status: string;
  created_at: string;
  completed_at?: string;
}

export interface MaintenanceRecord {
  maintenance_id: string;
  machine_id: string;
  machine_name: string;
  type: string;
  status: string;
  start_date: string;
  end_date: string;
  description?: string;
  reason?: string;
  cost: number;
  performed_by?: string;
}

export interface Report {
  report_id: string;
  report_type: string;
  format: string;
  file_path?: string;
  download_url?: string;
  status: string;
  created_at: string;
  completed_at?: string;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ApiError {
  detail: string;
}