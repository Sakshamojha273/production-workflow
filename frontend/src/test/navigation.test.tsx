import { render, screen, fireEvent, waitFor, renderHook } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

// The shared setup pins useLocation to /dashboard; use the real router here.
vi.mock('react-router-dom', async () => vi.importActual('react-router-dom'));

vi.mock('../services/api', () => ({
  api: {
    getOrders: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 100, total_pages: 0 }),
  },
}));

import { api } from '../services/api';
import { MainLayout } from '../layouts/MainLayout';
import { useOrders } from '../hooks/useData';

function renderLayout(path = '/dashboard') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<MainLayout />}>
          <Route path="*" element={<div>page</div>} />
        </Route>
      </Routes>
    </MemoryRouter>
  );
}

describe('sidebar navigation', () => {
  it('expands a group on click from a page outside it, and collapses it again', () => {
    renderLayout('/dashboard');
    expect(screen.queryByText('Orders')).toBeNull();

    const operations = screen.getByRole('button', { name: /Operations/ });
    expect(operations.getAttribute('aria-expanded')).toBe('false');

    fireEvent.click(operations);
    expect(operations.getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByRole('link', { name: 'Orders' }).getAttribute('href')).toBe('/operations/orders');

    fireEvent.click(operations);
    expect(screen.queryByText('Orders')).toBeNull();
  });

  it('every group can be opened from the dashboard', () => {
    renderLayout('/dashboard');
    for (const [group, child] of [
      ['Planning', 'Production Planning'],
      ['AI & Analytics', 'Demand Forecast'],
      ['Operations', 'Maintenance'],
      ['Data', 'Data Quality'],
    ]) {
      fireEvent.click(screen.getByRole('button', { name: new RegExp(group.replace('&', '\\&')) }));
      expect(screen.getByRole('link', { name: child })).toBeTruthy();
    }
  });

  it('keeps the active group open by default and lets the user close it', () => {
    renderLayout('/operations/orders');
    const operations = screen.getByRole('button', { name: /Operations/ });
    expect(operations.getAttribute('aria-expanded')).toBe('true');
    fireEvent.click(operations);
    expect(operations.getAttribute('aria-expanded')).toBe('false');
  });
});

describe('useOrders', () => {
  beforeEach(() => vi.mocked(api.getOrders).mockClear());

  it('does not refetch forever when given a new params object every render', async () => {
    const { result, rerender } = renderHook(() => useOrders({ page_size: 100 }));
    await waitFor(() => expect(result.current.loading).toBe(false));
    rerender();
    rerender();
    await new Promise((r) => setTimeout(r, 100));
    expect(vi.mocked(api.getOrders)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(api.getOrders)).toHaveBeenCalledWith({ page_size: 100 });
  });
});
