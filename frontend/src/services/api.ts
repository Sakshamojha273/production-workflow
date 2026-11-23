import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import type { ApiError } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

class ApiService {
  private client: AxiosInstance;
  private token: string | null = null;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 180000,
    });

    this.client.interceptors.request.use(
      (config: InternalAxiosRequestConfig) => {
        // getToken() also restores the token from localStorage after a page
        // reload; every /api route except /auth/* now requires it.
        const token = this.getToken();
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError<ApiError>) => {
        // Surface the API's own reason (FastAPI `detail`) instead of axios's
        // generic "Request failed with status code NNN", so every page that
        // shows err.message shows something useful.
        const detail = error.response?.data?.detail as unknown;
        if (typeof detail === 'string' && detail) {
          error.message = detail;
        } else if (Array.isArray(detail) && detail.length) {
          error.message = detail.map((d: { msg?: string }) => d?.msg || JSON.stringify(d)).join('; ');
        }
        // A 401 from the login endpoints is a wrong password, not an expired
        // session: let LoginPage show the error instead of reloading the page.
        const url = error.config?.url || '';
        const isAuthRequest = url.includes('/auth/login') || url.includes('/auth/demo-login');
        if (error.response?.status === 401 && !isAuthRequest) {
          this.clearToken();
          if (window.location.pathname !== '/login') {
            window.location.href = '/login';
          }
        }
        return Promise.reject(error);
      }
    );
  }

  setToken(token: string) {
    this.token = token;
    localStorage.setItem('token', token);
  }

  clearToken() {
    this.token = null;
    localStorage.removeItem('token');
  }

  getToken(): string | null {
    if (!this.token) {
      this.token = localStorage.getItem('token');
    }
    return this.token;
  }

  isAuthenticated(): boolean {
    return !!this.getToken();
  }

  // Auth
  async login(email: string, password: string) {
    const response = await this.client.post('/auth/login', { email, password });
    this.setToken(response.data.access_token);
    return response.data;
  }

  async demoLogin() {
    const response = await this.client.post('/auth/demo-login');
    this.setToken(response.data.access_token);
    return response.data;
  }

  async getCurrentUser() {
    const response = await this.client.get('/auth/me');
    return response.data;
  }

  // Dashboard
  async getDashboard() {
    const response = await this.client.get('/dashboard');
    return response.data;
  }

  async getAnalyticsSummary() {
    const response = await this.client.get('/analytics/summary');
    return response.data;
  }

  async getCharts() {
    const response = await this.client.get('/analytics/charts');
    return response.data;
  }

  // Orders
  async getOrders(params?: {
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
    const response = await this.client.get('/orders', { params });
    return response.data;
  }

  async getOrder(orderId: string) {
    const response = await this.client.get(`/orders/${orderId}`);
    return response.data;
  }

  // Products
  async getProducts() {
    const response = await this.client.get('/products');
    return response.data;
  }

  async getProduct(productId: string) {
    const response = await this.client.get(`/products/${productId}`);
    return response.data;
  }

  // Machines
  async getMachines() {
    const response = await this.client.get('/machines');
    return response.data;
  }

  async getMachine(machineId: string) {
    const response = await this.client.get(`/machines/${machineId}`);
    return response.data;
  }

  // Workers
  async getWorkers() {
    const response = await this.client.get('/workers');
    return response.data;
  }

  async getWorker(workerId: string) {
    const response = await this.client.get(`/workers/${workerId}`);
    return response.data;
  }

  // Inventory
  async getInventory() {
    const response = await this.client.get('/inventory');
    return response.data;
  }

  async getInventoryItem(productId: string) {
    const response = await this.client.get(`/inventory/${productId}`);
    return response.data;
  }

  // Forecast
  async getForecasts(params?: {
    product_id?: string;
    start_date?: string;
    end_date?: string;
    horizon_days?: number;
  }) {
    const response = await this.client.get('/forecast', { params });
    return response.data;
  }

  async generateForecast(data: {
    product_ids?: string[];
    horizon_days: number;
    model?: string;
  }) {
    const response = await this.client.post('/forecast/generate', data);
    return response.data;
  }

  async getDemandHistory(params?: { product_id?: string; days?: number }) {
    const response = await this.client.get('/forecast/history', { params });
    return response.data;
  }

  async getForecastMetrics(params?: { product_id?: string }) {
    const response = await this.client.get('/forecast/metrics', { params });
    return response.data;
  }

  async getForecastAccuracy(productId: string, days: number = 30) {
    const response = await this.client.get(`/forecast/accuracy/${productId}`, { params: { days } });
    return response.data;
  }

  // Planning
  async getPlans(status?: string, limit: number = 50) {
    const response = await this.client.get('/planning', { params: { status, limit } });
    return response.data;
  }

  async getPlanningDefaults() {
    const response = await this.client.get('/planning/defaults');
    return response.data;
  }

  async getLatestPlan() {
    const response = await this.client.get('/planning/latest');
    return response.data;
  }

  async getPlan(planId: string) {
    const response = await this.client.get(`/planning/${planId}`);
    return response.data;
  }

  async generatePlan(data: {
    start_date: string;
    end_date: string;
    product_ids?: string[];
    machine_ids?: string[];
    max_overtime_hours?: number;
    priority_weights?: Record<string, number>;
  }) {
    const response = await this.client.post('/planning/generate', data);
    return response.data;
  }

  async approvePlan(planId: string) {
    const response = await this.client.post(`/planning/${planId}/approve`);
    return response.data;
  }

  // Scenario
  async getScenarios(status?: string) {
    const response = await this.client.get('/scenario', { params: { status } });
    return response.data;
  }

  async getScenario(scenarioId: string) {
    const response = await this.client.get(`/scenario/${scenarioId}`);
    return response.data;
  }

  async createScenario(data: {
    name: string;
    description?: string;
    demand_change_pct: number;
    machine_availability_change_pct: number;
    worker_availability_change_pct: number;
    overtime_limit_change_pct: number;
    production_target_change_pct: number;
    inventory_change_pct: number;
    machine_failure_ids?: string[];
  }) {
    const response = await this.client.post('/scenario', data);
    return response.data;
  }

  async runScenario(scenarioId: string, baselineRunId: string) {
    const response = await this.client.post(`/scenario/${scenarioId}/run`, { baseline_run_id: baselineRunId });
    return response.data;
  }

  // Data
  async uploadDataset(file: File) {
    const formData = new FormData();
    formData.append('file', file);
    const response = await this.client.post('/data/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  }

  async getDataQualityReports(limit: number = 50) {
    const response = await this.client.get('/data/quality', { params: { limit } });
    return response.data;
  }

  async getDataQualityReport(reportId: string) {
    const response = await this.client.get(`/data/quality/${reportId}`);
    return response.data;
  }

  // Reports (CSV built server-side from live data)
  async listReports() {
    const response = await this.client.get('/reports');
    return response.data;
  }

  /** Downloads a CSV through the authenticated client; returns blob, filename and row count. */
  async downloadReport(reportId: string, params?: { start_date?: string; end_date?: string }) {
    const response = await this.client.get(`/reports/${reportId}`, { params, responseType: 'blob' });
    const disposition = String(response.headers['content-disposition'] || '');
    const match = disposition.match(/filename="?([^";]+)"?/);
    return {
      blob: response.data as Blob,
      filename: match?.[1] || `${reportId}.csv`,
      rows: Number(response.headers['x-row-count'] ?? NaN),
    };
  }

  async runResearch(query: string, onEvent: (event: Record<string, unknown>) => void) {
    const token = this.getToken();
    const response = await fetch(`${API_BASE_URL}/research`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ query }),
    });

    if (!response.ok) {
      if (response.status === 401) {
        this.clearToken();
        if (window.location.pathname !== '/login') window.location.href = '/login';
      }
      let detail = `Research request failed (HTTP ${response.status}).`;
      try {
        const body = await response.json() as { detail?: unknown };
        if (typeof body.detail === 'string') detail = body.detail;
      } catch {
        // Keep the HTTP status message when the server does not return JSON.
      }
      throw new Error(detail);
    }

    if (!response.body) {
      throw new Error('The server did not return a research event stream.');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let receivedReport = false;
    let finished = false;

    const consumeLine = (line: string) => {
      if (!line.startsWith('data:')) return;
      let event: Record<string, unknown>;
      try {
        const parsed: unknown = JSON.parse(line.slice(5).trim());
        if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
          throw new Error('Invalid event shape');
        }
        event = parsed as Record<string, unknown>;
      } catch {
        throw new Error('The server returned an invalid research event.');
      }

      if (event.event === 'error') {
        throw new Error(typeof event.message === 'string' ? event.message : 'TinyFish research failed.');
      }
      if (event.event === 'final_result') receivedReport = true;
      if (event.event === 'done') finished = true;
      onEvent(event);
    };

    try {
      while (!finished) {
        const { done, value } = await reader.read();
        buffer += decoder.decode(value, { stream: !done });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        lines.forEach((line) => consumeLine(line.replace(/\r$/, '')));
        if (done) {
          if (buffer) consumeLine(buffer.replace(/\r$/, ''));
          break;
        }
      }
    } finally {
      reader.releaseLock();
    }

    if (!receivedReport) {
      throw new Error('TinyFish ended the run without a research report.');
    }
  }

  async searchWeb(query: string) {
    const response = await this.client.post('/search', { query });
    return response.data;
  }

  // Settings (read-only backend configuration)
  async getSettings() {
    const response = await this.client.get('/settings');
    return response.data;
  }

  // Maintenance
  async getMaintenance(params?: {
    machine_id?: string;
    status?: string;
    start_date?: string;
    end_date?: string;
  }) {
    const response = await this.client.get('/maintenance', { params });
    return response.data;
  }

  async getMaintenanceTimeline(days: number = 30) {
    const response = await this.client.get('/maintenance/timeline', { params: { days } });
    return response.data;
  }

  async getMachineRisk(machineIds?: string) {
    const response = await this.client.get('/maintenance/machine-risk', { params: { machine_ids: machineIds } });
    return response.data;
  }

  async getRiskDistribution() {
    const response = await this.client.get('/maintenance/risk-distribution');
    return response.data;
  }
}

export const api = new ApiService();