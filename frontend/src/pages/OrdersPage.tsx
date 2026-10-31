import { useState, useMemo } from 'react';
import { useOrders, useProducts, useMachines } from '../hooks/useData';
import { cn, formatNumber, formatCurrency, format, getPriorityColor, getOrderStatusColor } from '../utils/helpers';
import {
  Search,
  Download,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

export function OrdersPage() {
  const { data, loading, refetch } = useOrders({ page_size: 100 });
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

  const filteredOrders = useMemo(() => {
    if (!data?.orders) return [];
    return data.orders.filter(order => {
      if (filters.search && !order.order_id.toLowerCase().includes(filters.search.toLowerCase()) &&
          !order.product_name.toLowerCase().includes(filters.search.toLowerCase())) {
        return false;
      }
      if (filters.product_id && order.product_id !== filters.product_id) return false;
      if (filters.machine_id && order.machine_id !== filters.machine_id) return false;
      if (filters.priority && order.priority !== filters.priority) return false;
      if (filters.status && order.status !== filters.status) return false;
      if (filters.start_date && new Date(order.date) < new Date(filters.start_date)) return false;
      if (filters.end_date && new Date(order.date) > new Date(filters.end_date)) return false;
      return true;
    });
  }, [data?.orders, filters]);

  const paginatedOrders = filteredOrders.slice((currentPage - 1) * pageSize, currentPage * pageSize);
  const totalPages = Math.ceil(filteredOrders.length / pageSize);

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
    link.download = `orders-${format(new Date(), 'yyyy-MM-dd')}.csv`;
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
            Export CSV
          </button>
          <button onClick={refetch} className="btn-secondary" disabled={loading}>
            Refresh
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="card p-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-secondary-400" />
            <input
              type="text"
              placeholder="Search orders..."
              value={filters.search}
              onChange={e => setFilters({ ...filters, search: e.target.value })}
              className="input pl-10"
            />
          </div>
          <select value={filters.product_id} onChange={e => setFilters({ ...filters, product_id: e.target.value })} className="input">
            <option value="">All Products</option>
            {products?.map(p => <option key={p.product_id} value={p.product_id}>{p.name}</option>)}
          </select>
          <select value={filters.machine_id} onChange={e => setFilters({ ...filters, machine_id: e.target.value })} className="input">
            <option value="">All Machines</option>
            {machines?.map(m => <option key={m.machine_id} value={m.machine_id}>{m.name}</option>)}
          </select>
          <select value={filters.priority} onChange={e => setFilters({ ...filters, priority: e.target.value })} className="input">
            <option value="">All Priorities</option>
            <option value="High">High</option>
            <option value="Medium">Medium</option>
            <option value="Low">Low</option>
          </select>
          <select value={filters.status} onChange={e => setFilters({ ...filters, status: e.target.value })} className="input">
            <option value="">All Statuses</option>
            <option value="Completed">Completed</option>
            <option value="In Progress">In Progress</option>
            <option value="Pending">Pending</option>
            <option value="Delayed">Delayed</option>
          </select>
          <div className="flex gap-2">
            <input type="date" value={filters.start_date} onChange={e => setFilters({ ...filters, start_date: e.target.value })} className="input" placeholder="Start Date" />
            <input type="date" value={filters.end_date} onChange={e => setFilters({ ...filters, end_date: e.target.value })} className="input" placeholder="End Date" />
          </div>
        </div>
      </div>

      {/* Orders Table */}
      <div className="card">
        <div className="p-4 border-b border-secondary-200 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-secondary-900">Orders ({filteredOrders.length})</h3>
          {loading && <span className="text-sm text-secondary-500">Loading...</span>}
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
              {paginatedOrders.map((order, index) => (
                <tr key={index}>
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
              {paginatedOrders.length === 0 && (
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
              Page {currentPage} of {totalPages} ({filteredOrders.length} orders)
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