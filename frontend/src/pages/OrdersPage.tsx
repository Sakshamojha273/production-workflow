import { useState, useMemo, useEffect } from 'react';
import { useOrders, useProducts, useMachines } from '../hooks/useData';
import { cn, formatNumber, formatCurrency, format, getPriorityColor, getOrderStatusColor } from '../utils/helpers';
import {
  Search,
  Download,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

export function OrdersPage() {
  const { data: products } = useProducts();
  const { data: machines } = useMachines();

  const [filters, setFilters] = useState({
    search: '',
    product_id: '',
    machine_id: '',
    priority: '',
    status: '',
    start_date: '',
    end_date: '',
  });
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 50;

  // Debounce free-text search so typing doesn't fire one request per key.
  const [debouncedSearch, setDebouncedSearch] = useState('');
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(filters.search.trim()), 300);
    return () => clearTimeout(t);
  }, [filters.search]);

  // Any filter change goes back to page 1.
  const updateFilter = (key: keyof typeof filters, value: string) => {
    setFilters(f => ({ ...f, [key]: value }));
    setCurrentPage(1);
  };

  // Filtering and pagination happen on the server (GET /orders supports
  // page/page_size and all filters and returns the true total).
  const queryParams = useMemo(() => {
    const p: Record<string, string | number> = { page: currentPage, page_size: pageSize };
    if (debouncedSearch) p.search = debouncedSearch;
    (['product_id', 'machine_id', 'priority', 'status', 'start_date', 'end_date'] as const).forEach(k => {
      if (filters[k]) p[k] = filters[k];
    });
    return p;
  }, [currentPage, debouncedSearch, filters]);

  const { data, loading, error, refetch } = useOrders(queryParams);

  const paginatedOrders = data?.orders ?? [];
  const totalOrders = data?.total ?? 0;
  const totalPages = data?.total_pages ?? 0;

  const handleExport = () => {
    const headers = ['Order ID', 'Date', 'Product', 'Demand', 'Production', 'Machine', 'Due Date', 'Priority', 'Status', 'Cost'];
    const csv = [
      headers.join(','),
      ...paginatedOrders.map(o => [
        o.order_id,
        format(new Date(o.date), 'yyyy-MM-dd'),
        o.product_name,
        o.demand,
        o.production_quantity,
        o.machine_name,
        format(new Date(o.due_date), 'yyyy-MM-dd'),
        o.priority,
        o.status,
        o.production_cost,
      ].join(','))
    ].join('\n');
    
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `orders-page${currentPage}-${format(new Date(), 'yyyy-MM-dd')}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Orders</h1>
          <p className="text-secondary-500">Manage and track production orders</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleExport} className="btn-secondary">
            <Download className="w-4 h-4" />
            Export page CSV
          </button>
          <button onClick={refetch} className="btn-secondary" disabled={loading}>
            Refresh
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="card p-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="relative sm:col-span-2 lg:col-span-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-secondary-400" />
            <input
              type="text"
              placeholder="Search orders..."
              value={filters.search}
              onChange={e => updateFilter('search', e.target.value)}
              className="input pl-10"
            />
          </div>
          <select value={filters.product_id} onChange={e => updateFilter('product_id', e.target.value)} className="input">
            <option value="">All Products</option>
            {products?.map(p => <option key={p.product_id} value={p.product_id}>{p.name}</option>)}
          </select>
          <select value={filters.machine_id} onChange={e => updateFilter('machine_id', e.target.value)} className="input">
            <option value="">All Machines</option>
            {machines?.map(m => <option key={m.machine_id} value={m.machine_id}>{m.name}</option>)}
          </select>
          <select value={filters.priority} onChange={e => updateFilter('priority', e.target.value)} className="input">
            <option value="">All Priorities</option>
            <option value="High">High</option>
            <option value="Medium">Medium</option>
            <option value="Low">Low</option>
          </select>
          <select value={filters.status} onChange={e => updateFilter('status', e.target.value)} className="input">
            <option value="">All Statuses</option>
            <option value="Completed">Completed</option>
            <option value="In Progress">In Progress</option>
            <option value="Pending">Pending</option>
            <option value="Delayed">Delayed</option>
          </select>
          {/* Date range takes two grid columns so the native date inputs aren't clipped. */}
          <div className="flex gap-2 sm:col-span-2 min-w-0">
            <input type="date" aria-label="Start date" title="Start date" value={filters.start_date} onChange={e => updateFilter('start_date', e.target.value)} className="input min-w-0 flex-1" />
            <input type="date" aria-label="End date" title="End date" value={filters.end_date} onChange={e => updateFilter('end_date', e.target.value)} className="input min-w-0 flex-1" />
          </div>
        </div>
      </div>

      {/* Orders Table */}
      <div className="card">
        <div className="p-4 border-b border-secondary-200 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-secondary-900">Orders ({totalOrders.toLocaleString('en-US')})</h3>
          {loading && <span className="text-sm text-secondary-500">Loading...</span>}
          {error && !loading && <span className="text-sm text-danger-600">{error}</span>}
        </div>
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Order ID</th>
                <th>Date</th>
                <th>Product</th>
                <th>Demand</th>
                <th>Production</th>
                <th>Machine</th>
                <th>Due Date</th>
                <th>Priority</th>
                <th>Status</th>
                <th>Cost</th>
              </tr>
            </thead>
            <tbody>
              {paginatedOrders.map((order) => (
                <tr key={order.order_id}>
                  <td className="font-mono text-sm">{order.order_id}</td>
                  <td>{format(new Date(order.date), 'MMM d, yyyy')}</td>
                  <td>{order.product_name}</td>
                  <td>{formatNumber(order.demand)}</td>
                  <td>{formatNumber(order.production_quantity)}</td>
                  <td>{order.machine_name}</td>
                  <td>{format(new Date(order.due_date), 'MMM d, yyyy')}</td>
                  <td>
                    <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', getPriorityColor(order.priority))}>
                      {order.priority}
                    </span>
                  </td>
                  <td>
                    <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', getOrderStatusColor(order.status))}>
                      {order.status}
                    </span>
                  </td>
                  <td>{formatCurrency(order.production_cost)}</td>
                </tr>
              ))}
              {paginatedOrders.length === 0 && !loading && (
                <tr>
                  <td colSpan={10} className="text-center py-8 text-secondary-500">No orders found</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="p-4 border-t border-secondary-200 flex items-center justify-between">
            <p className="text-sm text-secondary-500">
              Page {currentPage} of {totalPages.toLocaleString('en-US')} · showing {((currentPage - 1) * pageSize + 1).toLocaleString('en-US')}–{Math.min(currentPage * pageSize, totalOrders).toLocaleString('en-US')} of {totalOrders.toLocaleString('en-US')} orders
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                className="btn-secondary text-sm"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
                className="btn-secondary text-sm"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}