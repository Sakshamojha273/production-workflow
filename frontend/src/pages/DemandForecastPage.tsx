import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { AlertTriangle, Brain, Calendar, Package, RefreshCw, TrendingUp } from 'lucide-react';
import axios from 'axios';
import { ChartCard } from '../components/ChartCard';
import { KPICard } from '../components/KPICard';
import { api } from '../services/api';
import type { DemandHistoryPoint, Forecast, ForecastMetrics, Product } from '../types';
import { formatNumber } from '../utils/helpers';
import { useProducts } from '../hooks/useData';

const HORIZONS = [7, 14, 30] as const;

export function DemandForecastPage() {
  const { data: products = [] } = useProducts();
  const [horizon, setHorizon] = useState<number>(7);
  const [productId, setProductId] = useState('');
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<'product' | 'forecast' | 'growth'>('product');
  const [forecasts, setForecasts] = useState<Forecast[]>([]);
  const [history, setHistory] = useState<DemandHistoryPoint[]>([]);
  const [metrics, setMetrics] = useState<ForecastMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [forecastResult, historyResult, metricResult] = await Promise.all([
        api.getForecasts({ horizon_days: horizon, product_id: productId || undefined }),
        api.getDemandHistory({ days: 365, product_id: productId || undefined }),
        api.getForecastMetrics({ product_id: productId || undefined }),
      ]);
      setForecasts(forecastResult.forecasts || []);
      setHistory(historyResult.history || []);
      setMetrics(metricResult);
    } catch (err) {
      setError(errorMessage(err, 'Unable to load demand forecasts.'));
    } finally {
      setLoading(false);
    }
  }, [horizon, productId]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    setNotice(null);
    try {
      const result = await api.generateForecast({
        horizon_days: horizon,
        product_ids: productId ? [productId] : undefined,
      });
      setForecasts(result.forecasts || []);
      await loadData();
      setNotice('Forecast generated from historical demand and selected by chronological backtesting.');
    } catch (err) {
      setError(errorMessage(err, 'Forecast generation failed.'));
    } finally {
      setGenerating(false);
    }
  };

  const selectedForecasts = useMemo(
    () => forecasts.filter((forecast) => forecast.forecast_horizon_days <= horizon),
    [forecasts, horizon],
  );
  const latestHistoryDate = history.reduce(
    (latest, point) => point.date > latest ? point.date : latest,
    '',
  );
  const recentHistoryStart = latestHistoryDate
    ? addDays(latestHistoryDate, -29)
    : '';
  const recentHistory = useMemo(
    () => history.filter((point) => point.date >= recentHistoryStart),
    [history, recentHistoryStart],
  );
  const chartStartDate = latestHistoryDate ? addDays(latestHistoryDate, -34) : '';
  const chartHistory = useMemo(
    () => history.filter((point) => point.date >= chartStartDate),
    [chartStartDate, history],
  );
  const chartData = useMemo(() => makeChartData(chartHistory, selectedForecasts), [
    chartHistory,
    selectedForecasts,
  ]);

  const productSummaries = useMemo(() => {
    const historyByProduct = new Map<string, number[]>();
    recentHistory.forEach((point) => {
      if (!point.product_id) return;
      historyByProduct.set(point.product_id, [
        ...(historyByProduct.get(point.product_id) || []),
        point.demand,
      ]);
    });
    const forecastByProduct = new Map<string, Forecast[]>();
    selectedForecasts.forEach((forecast) => {
      forecastByProduct.set(forecast.product_id, [
        ...(forecastByProduct.get(forecast.product_id) || []),
        forecast,
      ]);
    });

    const productList: Product[] = products;
    return productList
      .filter((product) => !productId || product.product_id === productId)
      .map((product) => {
        const actual = historyByProduct.get(product.product_id) || [];
        const predictions = forecastByProduct.get(product.product_id) || [];
        const historicalAverage = actual.length
          ? actual.reduce((sum, value) => sum + value, 0) / actual.length
          : 0;
        const forecastAverage = predictions.length
          ? predictions.reduce((sum, value) => sum + value.predicted_demand, 0) / predictions.length
          : 0;
        return {
          product,
          historicalAverage,
          forecastAverage,
          growth: historicalAverage ? ((forecastAverage - historicalAverage) / historicalAverage) * 100 : null,
          peak: predictions.length ? Math.max(...predictions.map((forecast) => forecast.predicted_demand)) : 0,
          model: predictions[0]?.model_name || predictions[0]?.model_used || metrics?.selected_model || '—',
        };
      })
      .filter((row) => (forecastByProduct.get(row.product.product_id) || []).length > 0)
      .filter((row) => row.product.name.toLowerCase().includes(search.toLowerCase()))
      .sort((left, right) => {
        if (sortBy === 'forecast') return right.forecastAverage - left.forecastAverage;
        if (sortBy === 'growth') return (right.growth ?? -Infinity) - (left.growth ?? -Infinity);
        return left.product.name.localeCompare(right.product.name);
      });
  }, [metrics?.selected_model, productId, products, recentHistory, search, selectedForecasts, sortBy]);

  const forecastDemand = selectedForecasts.reduce((sum, item) => sum + item.predicted_demand, 0);
  // Growth definition (shared with the Dashboard KPI in backend analytics.py):
  // forecast total / number of forecast days, vs. trailing-30-day total /
  // number of observed days. Forecast rows are per product per day, so the
  // divisor must be the number of distinct dates, not the number of rows.
  const forecastDayCount = new Set(selectedForecasts.map((item) => item.forecast_date)).size;
  const averageDailyDemand = forecastDayCount ? forecastDemand / forecastDayCount : 0;
  const actualDailyTotals = new Map<string, number>();
  recentHistory.forEach((point) => {
    actualDailyTotals.set(point.date, (actualDailyTotals.get(point.date) || 0) + point.demand);
  });
  const actualAverage = actualDailyTotals.size
    ? [...actualDailyTotals.values()].reduce((sum, value) => sum + value, 0) / actualDailyTotals.size
    : 0;
  const growth = actualAverage ? ((averageDailyDemand - actualAverage) / actualAverage) * 100 : null;
  const peakForecast = selectedForecasts.reduce<Forecast | null>(
    (peak, item) => (!peak || item.predicted_demand > peak.predicted_demand ? item : peak),
    null,
  );
  const selectedMetrics = metrics?.selected_model ? metrics.metrics[metrics.selected_model] : null;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Demand Forecast</h1>
          <p className="mt-1 text-secondary-500">
            Demand predictions based on uploaded historical production demand and chronological backtesting.
          </p>
        </div>
        <button className="btn-primary" onClick={handleGenerate} disabled={generating || loading} aria-busy={generating}>
          <Brain className="h-4 w-4" />
          {generating ? 'Generating forecast…' : selectedForecasts.length ? 'Generate New Forecast' : 'Generate Forecast'}
        </button>
      </div>

      <section className="card flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-2" aria-label="Forecast horizon">
          {HORIZONS.map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setHorizon(value)}
              aria-pressed={horizon === value}
              className={`rounded-lg px-4 py-2 text-sm font-medium ${
                horizon === value
                  ? 'bg-primary-600 text-white'
                  : 'bg-secondary-100 text-secondary-700 hover:bg-secondary-200'
              }`}
            >
              {value} Days
            </button>
          ))}
        </div>
        <label className="flex items-center gap-3 text-sm font-medium text-secondary-700">
          <span>Product</span>
          <select
            className="input min-w-48"
            value={productId}
            onChange={(event) => setProductId(event.target.value)}
          >
            <option value="">All Products</option>
            {products.map((product) => (
              <option key={product.product_id} value={product.product_id}>
                {product.name}
              </option>
            ))}
          </select>
        </label>
      </section>
      {latestHistoryDate && (
        <p className="text-sm text-secondary-500">
          Historical demand through <strong className="font-medium text-secondary-700">{latestHistoryDate}</strong>
          {' · '}Growth compares the forecast daily average with the trailing 30-day daily average.
        </p>
      )}

      {error && (
        <div role="alert" className="rounded-lg border border-danger-200 bg-danger-50 p-4 text-danger-700">
          <AlertTriangle className="mr-2 inline h-4 w-4" />
          {error}
        </div>
      )}
      {notice && <p role="status" className="rounded-lg bg-success-50 p-3 text-sm text-success-700">{notice}</p>}

      {loading ? (
        <div className="card space-y-5 p-6" role="status" aria-live="polite">
          <span className="sr-only">Loading demand history and forecasts…</span>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 6 }, (_, index) => <div key={index} className="h-28 animate-pulse rounded-lg bg-secondary-100" />)}
          </div>
          <div className="h-80 animate-pulse rounded-lg bg-secondary-100" />
        </div>
      ) : history.length === 0 ? (
        <div className="card p-10 text-center">
          <Package className="mx-auto mb-3 h-10 w-10 text-secondary-300" />
          <h2 className="font-semibold text-secondary-900">No historical demand available</h2>
          <p className="mt-1 text-sm text-secondary-500">
            Upload a dataset with valid dates, products, and demand quantities before generating a forecast.
          </p>
          <Link to="/data/upload" className="btn-primary mt-4 inline-flex">Upload demand data</Link>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            <KPICard title="Forecast Demand" value={formatNumber(forecastDemand)} icon={<TrendingUp className="h-5 w-5" />} iconColor="bg-purple-100 text-purple-600" description={`Total over ${horizon} days`} />
            <KPICard title="Average Daily Forecast" value={formatNumber(averageDailyDemand)} icon={<Calendar className="h-5 w-5" />} iconColor="bg-blue-100 text-blue-600" description="Based on generated daily forecasts" />
            <KPICard title="Expected Demand Growth" value={growth === null ? '—' : `${growth >= 0 ? '+' : ''}${growth.toFixed(1)}%`} icon={<TrendingUp className="h-5 w-5" />} iconColor="bg-green-100 text-green-600" description="Estimate vs. trailing 30-day daily average; not guaranteed business growth" />
            <KPICard title="Peak Demand Day" value={peakForecast ? formatNumber(peakForecast.predicted_demand) : '—'} icon={<Package className="h-5 w-5" />} iconColor="bg-orange-100 text-orange-600" description={peakForecast?.forecast_date || 'Generate a forecast'} />
            <KPICard title="Backtest WAPE" value={selectedMetrics?.wape == null ? '—' : `${selectedMetrics.wape.toFixed(1)}%`} icon={<TrendingUp className="h-5 w-5" />} iconColor="bg-indigo-100 text-indigo-600" description="Lower is better; historical time-based test" />
            <KPICard title="Selected Model" value={metrics?.selected_model || '—'} icon={<Brain className="h-5 w-5" />} iconColor="bg-pink-100 text-pink-600" description="Selected by backtest WAPE" />
          </div>

          {selectedForecasts.length === 0 ? (
            <div className="card p-8 text-center text-secondary-600">
              No forecast is saved for this horizon yet. Generate one to view future demand.
            </div>
          ) : (
            <ChartCard title="Historical vs. Forecast Demand" subtitle={`Daily demand · trailing ${chartHistory.length ? Math.min(35, new Set(chartHistory.map((point) => point.date)).size) : 0} days plus forecast. Shaded band is an estimated prediction interval.`} icon={<TrendingUp className="h-5 w-5" />}>
              <ForecastChart data={chartData} />
            </ChartCard>
          )}

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            <section className="card overflow-hidden">
              <div className="flex flex-col gap-3 border-b border-secondary-200 p-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="font-semibold text-secondary-900">Product Forecast</h2>
                  <p className="text-sm text-secondary-500">Select a product above to focus the chart.</p>
                </div>
                <input
                  aria-label="Search products"
                  className="input sm:max-w-56"
                  placeholder="Search products…"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                />
                <select aria-label="Sort products" className="input sm:max-w-48" value={sortBy} onChange={(event) => setSortBy(event.target.value as typeof sortBy)}>
                  <option value="product">Sort by product</option>
                  <option value="forecast">Sort by forecast avg</option>
                  <option value="growth">Sort by growth</option>
                </select>
              </div>
              <div className="table-container">
                <table className="table">
                  <thead><tr><th>Product</th><th>Current Avg</th><th>Forecast Avg</th><th>Growth</th><th>Peak</th><th>Model</th></tr></thead>
                  <tbody>
                    {productSummaries.map((row) => (
                      <tr key={row.product.product_id}>
                        <td>
                          <button className="font-medium text-primary-700 hover:underline" onClick={() => setProductId(row.product.product_id)}>
                            {row.product.name}{productId === row.product.product_id ? ' (selected)' : ''}
                          </button>
                        </td>
                        <td>{formatNumber(row.historicalAverage)}</td>
                        <td>{formatNumber(row.forecastAverage)}</td>
                        <td>{row.growth === null ? '—' : `${row.growth >= 0 ? '+' : ''}${row.growth.toFixed(1)}%`}</td>
                        <td>{formatNumber(row.peak)}</td>
                        <td>{row.model}</td>
                      </tr>
                    ))}
                    {productSummaries.length === 0 && <tr><td colSpan={6} className="text-center text-secondary-500">No matching product forecasts.</td></tr>}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="card overflow-hidden">
              <div className="border-b border-secondary-200 p-4">
                <h2 className="font-semibold text-secondary-900">Model Backtesting</h2>
                <p className="mt-1 text-sm text-secondary-500">Metrics from expanding-window chronological validation.</p>
              </div>
              <div className="table-container">
                <table className="table">
                  <thead><tr><th>Model</th><th>MAE</th><th>RMSE</th><th>MAPE</th><th>WAPE</th><th>Bias</th></tr></thead>
                  <tbody>
                    {Object.entries(metrics?.metrics || {}).map(([name, item]) => (
                      <tr key={name} className={name === metrics?.selected_model ? 'bg-primary-50' : ''}>
                        <td className="font-medium">{name}{name === metrics?.selected_model ? ' (selected)' : ''}</td>
                        <td>{metric(item.mae)}</td><td>{metric(item.rmse)}</td>
                        <td>{item.mape == null ? '—' : `${item.mape.toFixed(1)}%`}</td>
                        <td>{item.wape == null ? '—' : `${item.wape.toFixed(1)}%`}</td>
                        <td>{metric(item.bias)}</td>
                      </tr>
                    ))}
                    {!Object.keys(metrics?.metrics || {}).length && (
                      <tr><td colSpan={6} className="text-center text-secondary-500">Insufficient history for backtesting.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          </div>

          <section className="card p-5 text-sm text-secondary-600">
            <h2 className="mb-2 font-semibold text-secondary-900">How to read this forecast</h2>
            <p><strong>Forecast:</strong> estimated future demand generated from historical daily demand.</p>
            <p><strong>Prediction interval:</strong> an estimated range derived from historical validation residuals; it is not a guaranteed confidence interval.</p>
            <p><strong>Model accuracy:</strong> historical backtest performance. Models are compared using the same chronological validation windows.</p>
            {metrics?.method && <p className="mt-2 text-xs">{metrics.method}</p>}
          </section>
        </>
      )}

      <button type="button" onClick={() => void loadData()} className="btn-secondary" disabled={loading || generating}>
        <RefreshCw className="h-4 w-4" /> Refresh forecast data
      </button>
    </div>
  );
}

function formatChartDate(value: string) {
  const [year, month, day] = value.split('-').map(Number);
  return new Date(Date.UTC(year, month - 1, day)).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  });
}

function metric(value: number | null) {
  return value == null ? '—' : formatNumber(value);
}

function addDays(isoDate: string, offset: number) {
  const date = new Date(`${isoDate}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + offset);
  return date.toISOString().slice(0, 10);
}

function errorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    const detail: unknown = error.response?.data?.detail;
    if (typeof detail === 'string') return detail;
  }
  return error instanceof Error ? error.message : fallback;
}

function makeChartData(history: DemandHistoryPoint[], forecasts: Forecast[]) {
  const points = new Map<string, { date: string; actual?: number; forecast?: number; lower?: number; upper?: number; range?: number }>();
  history.forEach((point) => {
    const current = points.get(point.date) || { date: point.date };
    current.actual = (current.actual || 0) + point.demand;
    points.set(point.date, current);
  });
  forecasts.forEach((point) => {
    const current = points.get(point.forecast_date) || { date: point.forecast_date };
    current.forecast = (current.forecast || 0) + point.predicted_demand;
    current.lower = (current.lower || 0) + (point.lower_bound ?? point.predicted_demand);
    current.upper = (current.upper || 0) + (point.upper_bound ?? point.predicted_demand);
    current.range = current.upper - current.lower;
    points.set(point.forecast_date, current);
  });
  return [...points.values()].sort((left, right) => left.date.localeCompare(right.date));
}

function ForecastTooltip({
  active,
  label,
  payload,
}: {
  active?: boolean;
  label?: string;
  payload?: { payload?: { actual?: number; forecast?: number; lower?: number; upper?: number } }[];
}) {
  const point = payload?.[0]?.payload;
  if (!active || !point) return null;
  return (
    <div className="rounded-lg border border-secondary-200 bg-white p-3 text-sm shadow-lg">
      <p className="mb-1 font-semibold text-secondary-900">{label ? formatChartDate(label) : ''}</p>
      <p>Actual: {point.actual == null ? '—' : formatNumber(point.actual)}</p>
      <p>Forecast: {point.forecast == null ? '—' : formatNumber(point.forecast)}</p>
      <p>Lower bound: {point.lower == null ? '—' : formatNumber(point.lower)}</p>
      <p>Upper bound: {point.upper == null ? '—' : formatNumber(point.upper)}</p>
    </div>
  );
}

function ForecastChart({ data }: { data: ReturnType<typeof makeChartData> }) {
  return (
    <div className="h-80">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 12, right: 24, left: 8, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={formatChartDate} minTickGap={24} />
          <YAxis tick={{ fontSize: 11 }} tickFormatter={(value: number) => formatNumber(value)} width={64} />
          <Tooltip content={<ForecastTooltip />} />
          <Legend />
          <Area dataKey="lower" stackId="interval" stroke="none" fill="#fff" fillOpacity={0} legendType="none" />
          <Area dataKey="range" stackId="interval" name="Estimated prediction interval" stroke="none" fill="#bfdbfe" fillOpacity={0.65} />
          <Line dataKey="actual" name="Historical demand" stroke="#64748b" strokeWidth={2} dot={false} connectNulls />
          <Line dataKey="forecast" name="Forecast demand" stroke="#2563eb" strokeWidth={2.5} dot={false} connectNulls />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
