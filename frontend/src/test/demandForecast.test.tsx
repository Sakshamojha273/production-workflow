import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { DemandForecastPage } from '../pages/DemandForecastPage';
import { api } from '../services/api';

vi.mock('recharts', async () => {
  const React = await import('react');
  const Container = ({ children }: { children?: React.ReactNode }) => React.createElement('div', null, children);
  const Shape = () => null;
  return {
    Area: Shape,
    CartesianGrid: Shape,
    ComposedChart: Container,
    Legend: Shape,
    Line: Shape,
    ResponsiveContainer: Container,
    Tooltip: Shape,
    XAxis: Shape,
    YAxis: Shape,
  };
});

vi.mock('../services/api', () => ({
  api: {
    getForecasts: vi.fn(),
    getDemandHistory: vi.fn(),
    getForecastMetrics: vi.fn(),
    generateForecast: vi.fn(),
  },
}));

vi.mock('../hooks/useData', () => ({
  useProducts: () => ({
    data: [{ product_id: 'P1', name: 'Widget', category: 'Parts' }],
  }),
}));

const forecast = {
  product_id: 'P1',
  product_name: 'Widget',
  forecast_date: '2027-01-01',
  forecast_horizon_days: 1,
  predicted_demand: 12,
  lower_bound: 9,
  upper_bound: 15,
  confidence_level: 0.8,
  model_used: 'MovingAverage',
  model_name: 'MovingAverage',
  created_at: '2026-12-31T12:00:00',
};

describe('DemandForecastPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getForecasts).mockResolvedValue({ forecasts: [forecast] });
    vi.mocked(api.getDemandHistory).mockResolvedValue({
      history: [{ date: '2026-12-31', product_id: 'P1', product_name: 'Widget', demand: 10 }],
    });
    vi.mocked(api.getForecastMetrics).mockResolvedValue({
      selected_model: 'MovingAverage',
      metrics: {
        MovingAverage: { mae: 2, rmse: 2, mape: 20, wape: 20, bias: 0 },
      },
      backtest_windows: 3,
      eligible_products: 1,
      method: 'Chronological test',
    });
    vi.mocked(api.generateForecast).mockResolvedValue({ forecasts: [forecast] });
  });

  it('renders API-backed demand and accuracy metrics', async () => {
    render(<MemoryRouter><DemandForecastPage /></MemoryRouter>);

    expect(await screen.findByRole('heading', { name: 'Historical vs. Forecast Demand' })).toBeInTheDocument();
    expect(screen.getByText('Selected Model')).toBeInTheDocument();
    expect(screen.getAllByText('MovingAverage').length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: '7 Days' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('loads the selected horizon and generates a forecast', async () => {
    render(<MemoryRouter><DemandForecastPage /></MemoryRouter>);

    fireEvent.click(await screen.findByRole('button', { name: '14 Days' }));
    await waitFor(() => {
      expect(api.getForecasts).toHaveBeenCalledWith(expect.objectContaining({ horizon_days: 14 }));
    });

    fireEvent.click(screen.getByRole('button', { name: 'Generate New Forecast' }));
    await waitFor(() => {
      expect(api.generateForecast).toHaveBeenCalledWith({ horizon_days: 14, product_ids: undefined });
    });
    expect(await screen.findByRole('status')).toHaveTextContent(/Forecast generated/);
  });

  it('explains when there is no historical demand', async () => {
    vi.mocked(api.getDemandHistory).mockResolvedValue({ history: [] });
    vi.mocked(api.getForecasts).mockResolvedValue({ forecasts: [] });

    render(<MemoryRouter><DemandForecastPage /></MemoryRouter>);

    expect(await screen.findByRole('heading', { name: 'No historical demand available' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Upload demand data' })).toHaveAttribute('href', '/data/upload');
  });
});
