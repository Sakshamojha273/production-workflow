import React from 'react';
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import dashboardFixture from './fixtures/dashboard.json';
import chartsFixture from './fixtures/analyticsCharts.json';
import historyFixture from './fixtures/demandHistory.json';
import forecastsFixture from './fixtures/forecasts.json';

// Fixtures are real responses captured from the running backend
// (GET /api/dashboard, /api/analytics/charts, /api/forecast/history?days=30,
// /api/forecast?horizon_days=7) on the 10K dataset.

// jsdom has no layout, so give ResponsiveContainer a fixed size and let the
// real Recharts components render their children.
vi.mock('recharts', async () => {
  const actual = await vi.importActual<typeof import('recharts')>('recharts');
  const ResponsiveContainer = ({ children }: { children: React.ReactElement }) =>
    React.cloneElement(children, { width: 600, height: 300 } as Record<string, unknown>);
  return { ...actual, ResponsiveContainer };
});

vi.mock('../services/api', () => ({
  api: {
    getDashboard: vi.fn(),
    getCharts: vi.fn(),
    getDemandHistory: vi.fn(),
    getForecasts: vi.fn(),
  },
}));

import { api } from '../services/api';
import { DashboardPage } from '../pages/DashboardPage';
import { ErrorBoundary } from '../components/ErrorBoundary';

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

describe('DashboardPage with real API responses', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver = ResizeObserverStub;
    vi.mocked(api.getDashboard).mockResolvedValue(dashboardFixture as never);
    vi.mocked(api.getCharts).mockResolvedValue(chartsFixture as never);
    vi.mocked(api.getDemandHistory).mockResolvedValue(historyFixture as never);
    vi.mocked(api.getForecasts).mockResolvedValue(forecastsFixture as never);
  });

  it('fixture contains a KPI with a null trend (Current Demand)', () => {
    const currentDemand = dashboardFixture.kpis.find((kpi) => kpi.title === 'Current Demand');
    expect(currentDemand?.trend).toBeNull();
  });

  it('renders every KPI and chart after data loads instead of unmounting', async () => {
    const onError = vi.fn();
    render(
      <MemoryRouter>
        <ErrorBoundary onError={onError}>
          <DashboardPage />
        </ErrorBoundary>
      </MemoryRouter>,
    );

    expect(await screen.findByText('2,894')).toBeInTheDocument();
    expect(screen.getByText('Current Demand')).toBeInTheDocument();
    expect(screen.getByText('10,826')).toBeInTheDocument();
    expect(screen.getByText('Late Orders')).toBeInTheDocument();
    expect(screen.getByText('Demand vs Production')).toBeInTheDocument();
    expect(screen.getByText('Upcoming Maintenance')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(onError).not.toHaveBeenCalled();
  });
});

describe('ErrorBoundary', () => {
  it('shows a message instead of a blank page when a child throws', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const Boom = () => {
      throw new Error('kaboom');
    };
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );
    expect(screen.getByRole('alert')).toHaveTextContent('Something went wrong');
    expect(screen.getByRole('alert')).toHaveTextContent('kaboom');
    spy.mockRestore();
  });
});

describe('KPICard trend handling', () => {
  it('renders without a trend badge when the API sends trend: null', async () => {
    const { KPICard } = await import('../components/KPICard');
    render(<KPICard title="Current Demand" value="10,826" trend={null} />);
    expect(screen.getByText('10,826')).toBeInTheDocument();
    expect(screen.queryByText(/%$/)).not.toBeInTheDocument();
  });
});
