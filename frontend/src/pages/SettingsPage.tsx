import { useState } from 'react';
import { cn } from '../utils/helpers';
import {
  User,
  Bell,
  Shield,
  Palette,
  Database,
  Globe,
  Key,
  Moon,
  Sun,
  Save,
  AlertCircle,
  CheckCircle,
  Download,
  Plus,
} from 'lucide-react';

export function SettingsPage() {
  const [activeTab, setActiveTab] = useState('profile');
  const [notifications, setNotifications] = useState({
    email: true,
    push: true,
    dailySummary: true,
    alerts: true,
    weeklyReport: false,
  });
  const [theme, setTheme] = useState<'light' | 'dark' | 'system'>('system');
  const [saving, setSaving] = useState(false);

  const tabs = [
    { id: 'profile', label: 'Profile', icon: User },
    { id: 'notifications', label: 'Notifications', icon: Bell },
    { id: 'appearance', label: 'Appearance', icon: Palette },
    { id: 'security', label: 'Security', icon: Shield },
    { id: 'data', label: 'Data & Storage', icon: Database },
    { id: 'integrations', label: 'Integrations', icon: Globe },
  ];

  const handleSave = async () => {
    setSaving(true);
    await new Promise(resolve => setTimeout(resolve, 1000));
    setSaving(false);
    // Show success toast
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Settings</h1>
          <p className="text-secondary-500">Manage your account and application preferences</p>
        </div>
        <button onClick={handleSave} disabled={saving} className="btn-primary">
          {saving ? (
            <span className="flex items-center gap-2">
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
              Saving...
            </span>
          ) : (
            <span className="flex items-center gap-2">
              <Save className="w-4 h-4" />
              Save Changes
            </span>
          )}
        </button>
      </div>

      <div className="card">
        <div className="border-b border-secondary-200">
          <nav className="flex gap-1 p-2" aria-label="Settings tabs">
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'flex items-center gap-2 px-4 py-3 text-sm font-medium rounded-lg transition-colors',
                  activeTab === tab.id
                    ? 'bg-primary-50 text-primary-700'
                    : 'text-secondary-600 hover:text-secondary-900 hover:bg-secondary-100'
                )}
              >
                <tab.icon className="w-4 h-4" />
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        <div className="p-6">
          {/* Profile Tab */}
          {activeTab === 'profile' && (
            <div className="space-y-6 max-w-2xl">
              <div className="flex items-center gap-6 p-4 bg-secondary-50 rounded-lg">
                <div className="w-20 h-20 rounded-full bg-primary-100 flex items-center justify-center">
                  <User className="w-10 h-10 text-primary-600" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-secondary-900">Admin User</h3>
                  <p className="text-secondary-500">admin@smartplan.ai</p>
                  <p className="text-xs text-secondary-400 mt-1">Administrator</p>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="label">Full Name</label>
                  <input type="text" defaultValue="Admin User" className="input" />
                </div>
                <div>
                  <label className="label">Email</label>
                  <input type="email" defaultValue="admin@smartplan.ai" className="input" />
                </div>
                <div>
                  <label className="label">Role</label>
                  <select className="input" disabled>
                    <option>Administrator</option>
                  </select>
                </div>
                <div>
                  <label className="label">Department</label>
                  <input type="text" defaultValue="Operations" className="input" />
                </div>
              </div>

              <div className="pt-4 border-t border-secondary-200">
                <h4 className="font-medium text-secondary-900 mb-3">Change Password</h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="label">Current Password</label>
                    <input type="password" className="input" placeholder="••••••••" />
                  </div>
                  <div>
                    <label className="label">New Password</label>
                    <input type="password" className="input" placeholder="••••••••" />
                  </div>
                  <div>
                    <label className="label">Confirm New Password</label>
                    <input type="password" className="input" placeholder="••••••••" />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Notifications Tab */}
          {activeTab === 'notifications' && (
            <div className="space-y-6 max-w-2xl">
              <div>
                <h4 className="font-medium text-secondary-900 mb-3">Email Notifications</h4>
                <div className="space-y-4">
                  {[
                    { key: 'email', label: 'Email Notifications', desc: 'Receive notifications via email' },
                    { key: 'dailySummary', label: 'Daily Summary', desc: 'Daily production summary report' },
                    { key: 'alerts', label: 'Critical Alerts', desc: 'Immediate alerts for critical issues' },
                    { key: 'weeklyReport', label: 'Weekly Report', desc: 'Weekly analytics and insights report' },
                  ].map(item => (
                    <label key={item.key} className="flex items-center justify-between p-4 bg-secondary-50 rounded-lg cursor-pointer hover:bg-secondary-100 transition-colors">
                      <div>
                        <p className="font-medium text-secondary-900">{item.label}</p>
                        <p className="text-sm text-secondary-500">{item.desc}</p>
                      </div>
                      <input
                        type="checkbox"
                        checked={notifications[item.key as keyof typeof notifications]}
                        onChange={e => setNotifications({ ...notifications, [item.key]: e.target.checked })}
                        className="w-5 h-5 rounded border-secondary-300 text-primary-600 focus:ring-primary-500"
                      />
                    </label>
                  ))}
                </div>
              </div>

              <div>
                <h4 className="font-medium text-secondary-900 mb-3">Push Notifications</h4>
                <label className="flex items-center justify-between p-4 bg-secondary-50 rounded-lg cursor-pointer hover:bg-secondary-100 transition-colors">
                  <div>
                    <p className="font-medium text-secondary-900">Push Notifications</p>
                    <p className="text-sm text-secondary-500">Receive browser push notifications</p>
                  </div>
                  <input
                    type="checkbox"
                    checked={notifications.push}
                    onChange={e => setNotifications({ ...notifications, push: e.target.checked })}
                    className="w-5 h-5 rounded border-secondary-300 text-primary-600 focus:ring-primary-500"
                  />
                </label>
              </div>
            </div>
          )}

          {/* Appearance Tab */}
          {activeTab === 'appearance' && (
            <div className="space-y-6 max-w-2xl">
              <div>
                <h4 className="font-medium text-secondary-900 mb-3">Theme</h4>
                <div className="grid grid-cols-3 gap-4">
                  {[
                    { id: 'light', label: 'Light', icon: Sun, desc: 'Always use light mode' },
                    { id: 'dark', label: 'Dark', icon: Moon, desc: 'Always use dark mode' },
                    { id: 'system', label: 'System', icon: Globe, desc: 'Match system preference' },
                  ].map(option => (
                    <label key={option.id} className={cn(
                      'relative p-4 border-2 rounded-lg cursor-pointer transition-all',
                      theme === option.id
                        ? 'border-primary-500 bg-primary-50'
                        : 'border-secondary-200 hover:border-primary-300'
                    )}>
                      <input
                        type="radio"
                        name="theme"
                        value={option.id}
                        checked={theme === option.id}
                        onChange={e => setTheme(e.target.value as any)}
                        className="sr-only"
                      />
                      <div className="flex items-center gap-3">
                        <div className={cn('p-2 rounded-lg', theme === option.id ? 'bg-primary-100' : 'bg-secondary-100')}>
                          <option.icon className={cn('w-5 h-5', theme === option.id ? 'text-primary-600' : 'text-secondary-500')} />
                        </div>
                        <div>
                          <p className="font-medium text-secondary-900">{option.label}</p>
                          <p className="text-sm text-secondary-500">{option.desc}</p>
                        </div>
                      </div>
                      {theme === option.id && (
                        <div className="absolute top-2 right-2 w-5 h-5 rounded-full bg-primary-500 flex items-center justify-center">
                          <CheckCircle className="w-3 h-3 text-white" />
                        </div>
                      )}
                    </label>
                  ))}
                </div>
              </div>

              <div>
                <h4 className="font-medium text-secondary-900 mb-3">Density</h4>
                <div className="grid grid-cols-3 gap-4">
                  {['comfortable', 'compact', 'spacious'].map(density => (
                    <label key={density} className="p-4 border-2 rounded-lg cursor-pointer hover:border-primary-300 transition-colors">
                      <input type="radio" name="density" value={density} className="sr-only" />
                      <p className="font-medium text-secondary-900 capitalize">{density}</p>
                    </label>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Security Tab */}
          {activeTab === 'security' && (
            <div className="space-y-6 max-w-2xl">
              <div className="p-4 bg-secondary-50 rounded-lg">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-success-100 text-success-600">
                    <Shield className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="font-medium text-secondary-900">Two-Factor Authentication</h4>
                    <p className="text-sm text-secondary-500">Enabled • Last used: Today</p>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <button className="btn-secondary">
                  <Key className="w-4 h-4" />
                  Change Password
                </button>
                <button className="btn-secondary">
                  <Shield className="w-4 h-4" />
                  Manage 2FA
                </button>
                <button className="btn-secondary">
                  <AlertCircle className="w-4 h-4" />
                  View Login History
                </button>
                <button className="btn-secondary">
                  <Key className="w-4 h-4" />
                  API Keys
                </button>
              </div>

              <div className="pt-4 border-t border-secondary-200">
                <h4 className="font-medium text-secondary-900 mb-3">Active Sessions</h4>
                <div className="space-y-2">
                  <div className="p-3 bg-secondary-50 rounded-lg flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-primary-100 flex items-center justify-center">
                        <Globe className="w-5 h-5 text-primary-600" />
                      </div>
                      <div>
                        <p className="font-medium text-secondary-900">Current Session</p>
                        <p className="text-sm text-secondary-500">Chrome on macOS • San Francisco, CA</p>
                      </div>
                    </div>
                    <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-success-100 text-success-700">Active</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Data Tab */}
          {activeTab === 'data' && (
            <div className="space-y-6 max-w-2xl">
              <div>
                <h4 className="font-medium text-secondary-900 mb-3">Data Retention</h4>
                <div className="space-y-3">
                  <label className="flex items-center justify-between p-4 bg-secondary-50 rounded-lg cursor-pointer">
                    <div>
                      <p className="font-medium text-secondary-900">Auto-delete old data</p>
                      <p className="text-sm text-secondary-500">Automatically remove data older than retention period</p>
                    </div>
                    <input type="checkbox" className="w-5 h-5 rounded border-secondary-300 text-primary-600 focus:ring-primary-500" />
                  </label>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="label">Retention Period</label>
                      <select className="input">
                        <option>1 Year</option>
                        <option>2 Years</option>
                        <option>5 Years</option>
                        <option>7 Years</option>
                        <option>Indefinite</option>
                      </select>
                    </div>
                  </div>
                </div>
              </div>

              <div>
                <h4 className="font-medium text-secondary-900 mb-3">Export Data</h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <button className="btn-secondary">
                    <Database className="w-4 h-4" />
                    Export All Data (CSV)
                  </button>
                  <button className="btn-secondary">
                    <Download className="w-4 h-4" />
                    Export Configuration
                  </button>
                </div>
              </div>

              <div className="p-4 bg-danger-50 border border-danger-200 rounded-lg">
                <h4 className="font-medium text-danger-800 mb-2">Danger Zone</h4>
                <p className="text-sm text-danger-700 mb-3">These actions are irreversible</p>
                <div className="flex items-center gap-4">
                  <button className="btn-danger">
                    <AlertCircle className="w-4 h-4" />
                    Delete All Data
                  </button>
                  <button className="btn-danger">
                    <AlertCircle className="w-4 h-4" />
                    Reset Application
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Integrations Tab */}
          {activeTab === 'integrations' && (
            <div className="space-y-6 max-w-2xl">
              <div>
                <h4 className="font-medium text-secondary-900 mb-3">Connected Services</h4>
                <div className="space-y-3">
                  {[
                    { name: 'ERP System', status: 'connected', desc: 'SAP S/4HANA • Last sync: 2 hours ago' },
                    { name: 'MES System', status: 'connected', desc: 'Siemens Opcenter • Last sync: 1 hour ago' },
                    { name: 'IoT Platform', status: 'disconnected', desc: 'AWS IoT Core • Not configured' },
                    { name: 'BI Tool', status: 'connected', desc: 'Power BI • Last sync: 30 min ago' },
                  ].map((integration, index) => (
                    <div key={index} className="p-4 border border-secondary-200 rounded-lg flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-primary-100 text-primary-600">
                          <Globe className="w-5 h-5" />
                        </div>
                        <div>
                          <p className="font-medium text-secondary-900">{integration.name}</p>
                          <p className="text-sm text-secondary-500">{integration.desc}</p>
                        </div>
                      </div>
                      <span className={cn('px-2 py-1 rounded-full text-xs font-medium',
                        integration.status === 'connected' ? 'bg-success-100 text-success-700' : 'bg-secondary-100 text-secondary-700'
                      )}>
                        {integration.status === 'connected' ? 'Connected' : 'Disconnected'}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <h4 className="font-medium text-secondary-900 mb-3">API Configuration</h4>
                <div className="space-y-4">
                  <div>
                    <label className="label">API Base URL</label>
                    <input type="text" defaultValue="https://api.smartplan.ai/v1" className="input" />
                  </div>
                  <div>
                    <label className="label">API Key</label>
                    <div className="relative">
                      <input type="password" defaultValue="sk_live_••••••••••••••••" className="input pr-10" />
                      <button className="absolute right-3 top-1/2 -translate-y-1/2 text-secondary-400">Show</button>
                    </div>
                  </div>
                  <button className="btn-secondary">Regenerate API Key</button>
                </div>
              </div>

              <div>
                <h4 className="font-medium text-secondary-900 mb-3">Webhooks</h4>
                <button className="btn-primary">
                  <Plus className="w-4 h-4" />
                  Add Webhook
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}