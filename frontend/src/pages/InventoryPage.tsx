import { format } from 'date-fns';
import { useInventory } from '../hooks/useData';
import { KPICard } from '../components/KPICard';
import { cn, formatNumber, formatCurrency, downloadFile, toCSV, parseServerTimestamp } from '../utils/helpers';
import {
  Box,
  Package,
  AlertTriangle,
  TrendingUp,
  Download,
  RefreshCw,
  Shield,
  Archive,
} from 'lucide-react';

export function InventoryPage() {
  const { data: inventory, loading, refetch } = useInventory();

  const healthy = inventory?.filter(i => i.status === 'Healthy').length || 0;
  const low = inventory?.filter(i => i.status === 'Low').length || 0;
  const critical = inventory?.filter(i => i.status === 'Critical').length || 0;
  const totalItems = inventory?.reduce((sum, i) => sum + i.current_level, 0) || 0;
  const totalValue = inventory?.reduce((sum, i) => sum + i.current_level * i.unit_cost, 0) || 0;
  const avgCoverage = inventory?.reduce((sum, i) => sum + i.coverage_days, 0) / (inventory?.length || 1);

  const handleExport = () => {
    downloadFile(toCSV(
      ['Product ID', 'Product', 'Category', 'Units', 'Safety Stock', 'Reorder Point', 'Unit Cost', 'Value', 'Coverage Days', 'Status'],
      (inventory || []).map(i => [i.product_id, i.product_name, i.category, i.current_level, i.safety_stock, i.reorder_point, i.unit_cost, (i.current_level * i.unit_cost).toFixed(2), i.coverage_days, i.status]),
    ), 'inventory.csv');
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Inventory</h1>
          <p className="text-secondary-500">Track inventory levels, safety stock, and coverage</p>
          <p className="text-xs text-secondary-400 mt-1">Coverage = units ÷ average daily demand (last 28 days). Unit cost = production cost ÷ units produced. Safety stock = 1.65 × σ(daily demand) × √lead time.</p>
        </div>
        <div className="flex items-center gap-2">
          <button className="btn-secondary" onClick={handleExport} disabled={!inventory?.length}>
            <Download className="w-4 h-4" />
            Export
          </button>
          <button className="btn-secondary" onClick={() => refetch()} disabled={loading}>
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <KPICard title="Total Products" value={inventory?.length.toString() || '0'} icon={<Package className="w-5 h-5" />} iconColor="bg-blue-100 text-blue-600" />
        <KPICard title="Total Units" value={formatNumber(totalItems)} icon={<Box className="w-5 h-5" />} iconColor="bg-green-100 text-green-600" />
        <KPICard title="Total Value" value={formatCurrency(totalValue)} icon={<Archive className="w-5 h-5" />} iconColor="bg-purple-100 text-purple-600" />
        <KPICard title="Avg Coverage" value={`${avgCoverage.toFixed(1)} days`} icon={<TrendingUp className="w-5 h-5" />} iconColor="bg-orange-100 text-orange-600" />
        <KPICard title="Critical Items" value={critical.toString()} icon={<AlertTriangle className="w-5 h-5" />} iconColor="bg-danger-100 text-danger-600" status={critical > 0 ? 'Critical' : 'Healthy'} />
      </div>

      {/* Status Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="card p-6 text-center bg-success-50 border-success-200">
          <Shield className="w-12 h-12 text-success-600 mx-auto mb-2" />
          <p className="text-3xl font-bold text-success-700">{healthy}</p>
          <p className="text-secondary-500">Healthy</p>
          <p className="text-xs text-success-600 mt-1">Above 1.5x safety stock</p>
        </div>
        <div className="card p-6 text-center bg-warning-50 border-warning-200">
          <Package className="w-12 h-12 text-warning-600 mx-auto mb-2" />
          <p className="text-3xl font-bold text-warning-700">{low}</p>
          <p className="text-secondary-500">Low Stock</p>
          <p className="text-xs text-warning-600 mt-1">Between 1x-1.5x safety stock</p>
        </div>
        <div className="card p-6 text-center bg-danger-50 border-danger-200">
          <AlertTriangle className="w-12 h-12 text-danger-600 mx-auto mb-2" />
          <p className="text-3xl font-bold text-danger-700">{critical}</p>
          <p className="text-secondary-500">Critical</p>
          <p className="text-xs text-danger-600 mt-1">Below safety stock</p>
        </div>
      </div>

      {/* Inventory Table */}
      <div className="card">
        <div className="p-4 border-b border-secondary-200">
          <h3 className="text-lg font-semibold text-secondary-900">Inventory Levels</h3>
        </div>
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Product</th>
                <th>Category</th>
                <th>Current Level</th>
                <th>Safety Stock</th>
                <th>Reorder Point</th>
                <th>Max Stock</th>
                <th>Coverage</th>
                <th>Unit Cost</th>
                <th>Total Value</th>
                <th>Status</th>
                <th>Last Updated</th>
              </tr>
            </thead>
            <tbody>
              {inventory?.map((item, index) => (
                <tr key={index} className={item.status === 'Critical' ? 'bg-danger-50' : item.status === 'Low' ? 'bg-warning-50' : ''}>
                  <td className="font-medium">{item.product_name}</td>
                  <td>{item.category}</td>
                  <td className="font-mono">{formatNumber(item.current_level)}</td>
                  <td>{formatNumber(item.safety_stock)}</td>
                  <td>{formatNumber(item.reorder_point)}</td>
                  <td>{formatNumber(item.max_stock)}</td>
                  <td className="font-medium">{item.coverage_days.toFixed(1)} days</td>
                  <td>{formatCurrency(item.unit_cost)}</td>
                  <td>{formatCurrency(item.current_level * item.unit_cost)}</td>
                  <td>
                    <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium',
                      item.status === 'Healthy' && 'bg-success-100 text-success-700',
                      item.status === 'Low' && 'bg-warning-100 text-warning-700',
                      item.status === 'Critical' && 'bg-danger-100 text-danger-700'
                    )}>
                      {item.status}
                    </span>
                  </td>
                  <td className="text-sm text-secondary-500">{format(parseServerTimestamp(item.last_updated), 'MMM d, yyyy')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Critical Items Alert */}
      {critical > 0 && (
        <div className="card border-danger-200 bg-danger-50">
          <div className="p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-6 h-6 text-danger-600 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="text-lg font-semibold text-danger-800">{critical} Critical Inventory Items</h3>
                <p className="text-danger-700 mt-1">The following products are below safety stock levels and require immediate attention:</p>
                <ul className="mt-2 list-disc list-inside text-danger-700 space-y-1">
                  {inventory?.filter(i => i.status === 'Critical').slice(0, 10).map((item, idx) => (
                    <li key={idx}>{item.product_name} - {formatNumber(item.current_level)} units (Safety: {formatNumber(item.safety_stock)})</li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
