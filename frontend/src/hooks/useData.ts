import { useState, useEffect, useCallback } from 'react';
import { api } from '../services/api';
import type { DashboardResponse, OrderListResponse, Product, Machine, Worker, InventoryItem, Forecast, ProductionPlan, Scenario, DataQualityReport, MaintenanceRecord } from '../types';

export function useDashboard() {
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await api.getDashboard();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch dashboard');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

export function useAnalyticsSummary() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await api.getAnalyticsSummary();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch analytics');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

export function useCharts() {
  const [data, setData] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await api.getCharts();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch charts');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

export function useOrders(params?: {
  page?: number;
  page_size?: number;
  product_id?: string;
  machine_id?: string;
  priority?: string;
  status?: string;
  start_date?: string;
  end_date?: string;
  search?: string;
}) {
  const [data, setData] = useState<OrderListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Serialize params so a new object literal each render doesn't refetch forever.
  const paramsKey = params ? JSON.stringify(params) : '';

  const fetch = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await api.getOrders(paramsKey ? JSON.parse(paramsKey) : undefined);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch orders');
    } finally {
      setLoading(false);
    }
  }, [paramsKey]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

export function useProducts() {
  const [data, setData] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await api.getProducts();
      setData(result.products);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch products');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

export function useMachines() {
  const [data, setData] = useState<Machine[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await api.getMachines();
      setData(result.machines);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch machines');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

export function useWorkers() {
  const [data, setData] = useState<Worker[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await api.getWorkers();
      setData(result.workers);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch workers');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

export function useInventory() {
  const [data, setData] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await api.getInventory();
      setData(result.inventory);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch inventory');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

export function useForecasts(params?: {
  product_id?: string;
  start_date?: string;
  end_date?: string;
  horizon_days?: number;
}) {
  const [data, setData] = useState<Forecast[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Serialize params so a new object literal each render doesn't refetch forever.
  const paramsKey = params ? JSON.stringify(params) : '';

  const fetch = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await api.getForecasts(paramsKey ? JSON.parse(paramsKey) : undefined);
      setData(result.forecasts);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch forecasts');
    } finally {
      setLoading(false);
    }
  }, [paramsKey]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  const generate = useCallback(async (data: { product_ids?: string[]; horizon_days: number; model: string }) => {
    try {
      setLoading(true);
      setError(null);
      const result = await api.generateForecast(data);
      setData(result.forecasts);
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate forecast');
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { data, loading, error, refetch: fetch, generate };
}

export function usePlans() {
  const [data, setData] = useState<ProductionPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await api.getPlans();
      setData(result.plans);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch plans');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
  }, [fetch]);

  const generate = useCallback(async (planData: {
    start_date: string;
    end_date: string;
    product_ids?: string[];
    machine_ids?: string[];
    max_overtime_hours?: number;
    priority_weights?: Record<string, number>;
  }) => {
    try {
      setLoading(true);
      setError(null);
      const result = await api.generatePlan(planData);
      await fetch(); // Refresh list
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate plan');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [fetch]);

  return { data, loading, error, refetch: fetch, generate };
}

export function useLatestPlan() {
  const [data, setData] = useState<ProductionPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await api.getLatestPlan();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch latest plan');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

export function useScenarios() {
  const [data, setData] = useState<Scenario[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await api.getScenarios();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch scenarios');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
  }, [fetch]);

  const create = useCallback(async (scenarioData: {
    name: string;
    description?: string;
    demand_change_pct: number;
    machine_availability_change_pct: number;
    worker_availability_change_pct: number;
    overtime_limit_change_pct: number;
    production_target_change_pct: number;
    inventory_change_pct: number;
    machine_failure_ids?: string[];
  }) => {
    try {
      setLoading(true);
      setError(null);
      const result = await api.createScenario(scenarioData);
      await fetch();
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create scenario');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [fetch]);

  const run = useCallback(async (scenarioId: string, baselineRunId: string) => {
    try {
      setLoading(true);
      setError(null);
      const result = await api.runScenario(scenarioId, baselineRunId);
      await fetch();
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to run scenario');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [fetch]);

  return { data, loading, error, refetch: fetch, create, run };
}

export function useDataQuality() {
  const [data, setData] = useState<DataQualityReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await api.getDataQualityReports();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch data quality reports');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
  }, [fetch]);

  const upload = useCallback(async (file: File) => {
    try {
      setLoading(true);
      setError(null);
      const result = await api.uploadDataset(file);
      await fetch();
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to upload dataset');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [fetch]);

  return { data, loading, error, refetch: fetch, upload };
}

export function useMaintenance(params?: {
  machine_id?: string;
  status?: string;
  start_date?: string;
  end_date?: string;
}) {
  const [data, setData] = useState<MaintenanceRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Serialize params so a new object literal each render doesn't refetch forever.
  const paramsKey = params ? JSON.stringify(params) : '';

  const fetch = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await api.getMaintenance(paramsKey ? JSON.parse(paramsKey) : undefined);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch maintenance');
    } finally {
      setLoading(false);
    }
  }, [paramsKey]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

export function useMachineRisk() {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await api.getMachineRisk();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch machine risk');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

export function useRiskDistribution() {
  const [data, setData] = useState<{ low: number; medium: number; high: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await api.getRiskDistribution();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch risk distribution');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

export function useMaintenanceTimeline(days: number = 30) {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await api.getMaintenanceTimeline(days);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch maintenance timeline');
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}