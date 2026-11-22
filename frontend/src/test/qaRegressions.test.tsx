/** Regression tests for the QA pass of 2026-11-22 (bugs B4–B9). */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

const uploadMock = vi.fn();
const createMock = vi.fn();

vi.mock('../services/api', () => ({
  api: {
    getForecasts: vi.fn().mockResolvedValue({ forecasts: [] }),
    demoLogin: vi.fn(),
    login: vi.fn(),
  },
}));

vi.mock('../hooks/useData', () => ({
  useDataQuality: () => ({ data: [], loading: false, upload: uploadMock, refetch: vi.fn() }),
  useScenarios: () => ({ data: [], loading: false, create: createMock, run: vi.fn() }),
  usePlans: () => ({ data: [] }),
  useOrders: () => ({ data: { orders: [], total: 0, total_pages: 0 }, loading: false, error: null, refetch: vi.fn() }),
  useProducts: () => ({ data: [] }),
  useMachines: () => ({ data: [] }),
}));

import { parseServerTimestamp, peakDailyTotal } from '../utils/helpers';
import { DataUploadPage } from '../pages/DataUploadPage';
import { WhatIfAnalysisPage } from '../pages/WhatIfAnalysisPage';
import { OrdersPage } from '../pages/OrdersPage';
import { LoginPage } from '../pages/LoginPage';

beforeEach(() => {
  uploadMock.mockReset();
  createMock.mockReset();
});

describe('B5 peakDailyTotal', () => {
  it('sums products per day before taking the peak', () => {
    const rows = [
      { forecast_date: '2026-11-01', predicted_demand: 2500 },
      { forecast_date: '2026-11-01', predicted_demand: 100 },
      { forecast_date: '2026-11-02', predicted_demand: 1500 },
      { forecast_date: '2026-11-02', predicted_demand: 1500 },
    ];
    expect(peakDailyTotal(rows)).toEqual({ date: '2026-11-02', total: 3000 });
    expect(peakDailyTotal([])).toBeNull();
  });
});

describe('B7 parseServerTimestamp', () => {
  it('reads a zone-less API timestamp as UTC', () => {
    expect(parseServerTimestamp('2026-11-22T06:25:00').getTime()).toBe(Date.UTC(2026, 10, 22, 6, 25));
    expect(parseServerTimestamp('2026-11-22T06:25:00.123456').getTime()).toBe(Date.UTC(2026, 10, 22, 6, 25, 0, 123));
  });
  it('leaves zoned timestamps alone', () => {
    expect(parseServerTimestamp('2026-11-22T06:25:00Z').getTime()).toBe(Date.UTC(2026, 10, 22, 6, 25));
    expect(parseServerTimestamp('2026-11-22T11:55:00+05:30').getTime()).toBe(Date.UTC(2026, 10, 22, 6, 25));
  });
});

describe('B4 upload error is cleared', () => {
  it('drops the old error after Cancel and a new file', async () => {
    uploadMock.mockRejectedValue(new Error('Failed to parse CSV: missing required columns: Demand'));
    const { container } = render(<DataUploadPage />);
    const pick = (name: string) => fireEvent.change(container.querySelector('input[type="file"]')!, {
      target: { files: [new File(['a,b\n1,2\n'], name, { type: 'text/csv' })] },
    });
    pick('bad.csv');
    fireEvent.click(screen.getByRole('button', { name: /Process Dataset/ }));
    expect(await screen.findByRole('alert')).toHaveTextContent('missing required columns: Demand');
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    pick('good.csv');
    await waitFor(() => expect(screen.getByText('good.csv')).toBeInTheDocument());
    expect(screen.queryByRole('alert')).toBeNull();
  });
});

describe('B6 What-If create errors are shown', () => {
  it('keeps the dialog open with the server message', async () => {
    createMock.mockRejectedValue(new Error('Input should be greater than or equal to -100'));
    render(<MemoryRouter><WhatIfAnalysisPage /></MemoryRouter>);
    fireEvent.click(screen.getAllByRole('button', { name: /Create Scenario/ })[0]);
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Bad' } });
    const createButtons = screen.getAllByRole('button', { name: /Create Scenario/ });
    fireEvent.click(createButtons[createButtons.length - 1]);
    const alert = await screen.findByText(/Could not create scenario/);
    expect(alert).toHaveTextContent('greater than or equal to -100');
    expect(screen.getByLabelText('Name')).toBeInTheDocument();
  });
});

describe('B8 Orders priority filter', () => {
  it('offers Critical', () => {
    render(<OrdersPage />);
    const options = screen.getAllByRole('option').map((o) => o.textContent);
    expect(options).toContain('Critical');
  });
});

describe('B9 demo credentials', () => {
  it('fills the demo account when ticked, even after the fields were cleared', () => {
    render(<LoginPage />);
    const email = screen.getByLabelText('Email') as HTMLInputElement;
    const password = screen.getByLabelText('Password') as HTMLInputElement;
    fireEvent.change(email, { target: { value: '' } });
    fireEvent.change(password, { target: { value: '' } });
    fireEvent.click(screen.getByLabelText('Use demo credentials'));
    expect(email.value).toBe('admin@smartplan.ai');
    expect(password.value).not.toBe('');
  });
});
