import { useCallback, useEffect, useState } from 'react';
import { Lock, RefreshCw } from 'lucide-react';
import { api } from '../services/api';

interface SettingItem { key: string; value: string | number | boolean | null; note?: string }
interface SettingGroup { name: string; items: SettingItem[] }

function show(value: SettingItem['value']): string {
  if (value === null || value === undefined || value === '') return 'not set';
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  return String(value);
}

/** Read-only view of the running backend configuration (backend/.env). */
export function SettingsPage() {
  const [groups, setGroups] = useState<SettingGroup[]>([]);
  const [source, setSource] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getSettings();
      setGroups(data.groups || []);
      setSource(data.source || '');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load settings');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Settings</h1>
          <p className="text-secondary-500">Configuration the backend is running with</p>
        </div>
        <button className="btn-secondary" onClick={load} disabled={loading}>
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      <div className="card p-4 flex items-start gap-3 text-sm text-secondary-600" data-testid="settings-readonly">
        <Lock className="w-4 h-4 mt-0.5 flex-shrink-0" />
        <span>Read-only. To change a value edit {source || 'backend/.env'}. Secrets are never shown.</span>
      </div>

      {error && <div className="card p-4 text-sm text-danger-700 bg-danger-50">{error}</div>}
      {loading && !groups.length && <div className="text-secondary-500">Loading settings...</div>}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {groups.map((group) => (
          <div key={group.name} className="card">
            <div className="p-4 border-b border-secondary-200">
              <h3 className="text-lg font-semibold text-secondary-900">{group.name}</h3>
            </div>
            <dl className="divide-y divide-secondary-100">
              {group.items.map((item) => (
                <div key={item.key} className="px-4 py-3 flex items-start justify-between gap-4">
                  <dt className="font-mono text-xs text-secondary-500 break-all">{item.key}</dt>
                  <dd className="text-sm text-secondary-900 text-right">
                    {show(item.value)}
                    {item.note && <div className="text-xs text-secondary-400">{item.note}</div>}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>
    </div>
  );
}
