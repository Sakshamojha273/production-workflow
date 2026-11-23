import { useState } from 'react';
import { Outlet, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { cn } from '../utils/helpers';
import type { LucideIcon } from 'lucide-react';
import {
  LayoutDashboard,
  Factory,
  Brain,
  Activity,
  Package,
  Settings,
  FileText,
  Database,
  ChevronLeft,
  ChevronRight,
  Menu,
  LogOut,
  User,
  Bell,
  HelpCircle,
} from 'lucide-react';

type NavigationItem =
  | { name: string; href: string; icon: LucideIcon }
  | { name: string; icon: LucideIcon; children: { name: string; href: string }[] };

const navigation: NavigationItem[] = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  {
    name: 'Planning',
    icon: Factory,
    children: [
      { name: 'Production Planning', href: '/planning/production' },
      { name: 'Workforce Scheduling', href: '/planning/workforce' },
      { name: 'What-If Analysis', href: '/planning/what-if' },
    ],
  },
  {
    name: 'AI & Analytics',
    icon: Brain,
    children: [
      { name: 'Demand Forecast', href: '/analytics/demand-forecast' },
      { name: 'Machine Health', href: '/analytics/machine-health' },
      { name: 'Web Search', href: '/analytics/search' },
      { name: 'Web Research', href: '/analytics/research' },
      { name: 'Analytics', href: '/analytics/overview' },
    ],
  },
  {
    name: 'Operations',
    icon: Package,
    children: [
      { name: 'Orders', href: '/operations/orders' },
      { name: 'Machines', href: '/operations/machines' },
      { name: 'Workforce', href: '/operations/workforce' },
      { name: 'Inventory', href: '/operations/inventory' },
      { name: 'Maintenance', href: '/operations/maintenance' },
    ],
  },
  {
    name: 'Data',
    icon: Database,
    children: [
      { name: 'Upload Dataset', href: '/data/upload' },
      { name: 'Data Quality', href: '/data/quality' },
    ],
  },
  { name: 'Reports', href: '/reports', icon: FileText },
  { name: 'Settings', href: '/settings', icon: Settings },
];

export function MainLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const navigate = useNavigate();
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({});
  const location = useLocation();

  const isActive = (href: string) => location.pathname === href || location.pathname.startsWith(href + '/');

  const toggleSidebar = () => setSidebarOpen(!sidebarOpen);

  // A group is expanded if the user toggled it open, or (until they toggle it) if it contains the current page.
  const isGroupOpen = (name: string, containsActive: boolean) => openGroups[name] ?? containsActive;

  const toggleGroup = (name: string, containsActive: boolean) => {
    if (!sidebarOpen) {
      setSidebarOpen(true);
      setOpenGroups((prev) => ({ ...prev, [name]: true }));
      return;
    }
    setOpenGroups((prev) => ({ ...prev, [name]: !isGroupOpen(name, containsActive) }));
  };

  return (
    <div className="min-h-screen bg-secondary-50 flex">
      {/* Sidebar */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-40 bg-white border-r border-secondary-200 transition-all duration-300',
          sidebarOpen ? 'w-64' : 'w-20',
          mobileMenuOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        )}
      >
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className={cn('flex items-center gap-3 p-4 border-b border-secondary-200', sidebarOpen ? '' : 'justify-center')}>
            <div className="brand-logo brand-logo-sidebar" aria-label="SmartPlan AI">
              <Activity className="brand-logo-icon w-6 h-6 text-white" aria-hidden="true" />
            </div>
            {sidebarOpen && (
              <div>
                <h1 className="text-lg font-bold text-secondary-900">SmartPlan AI</h1>
                <p className="text-xs text-secondary-500">Production Planning</p>
              </div>
            )}
          </div>

          {/* Navigation */}
          <nav className="flex-1 p-3 space-y-1 overflow-y-auto" role="navigation" aria-label="Main navigation">
            {navigation.map((item) => {
              const isItemActive = 'children' in item
                ? item.children.some((child) => isActive(child.href))
                : isActive(item.href);

              if ('children' in item) {
                const expanded = isGroupOpen(item.name, isItemActive);
                const groupId = `nav-group-${item.name.replace(/\W+/g, '-').toLowerCase()}`;
                return (
                  <div key={item.name}>
                    <button
                      type="button"
                      onClick={() => toggleGroup(item.name, isItemActive)}
                      title={sidebarOpen ? undefined : item.name}
                      aria-label={sidebarOpen ? undefined : item.name}
                      aria-controls={groupId}
                      className={cn(
                        'flex items-center gap-3 w-full rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                        isItemActive
                          ? 'bg-primary-50 text-primary-700'
                          : 'text-secondary-600 hover:bg-secondary-100 hover:text-secondary-900',
                        !sidebarOpen && 'justify-center'
                      )}
                      aria-expanded={sidebarOpen && expanded}
                    >
                      <item.icon className="w-5 h-5 flex-shrink-0" aria-hidden="true" />
                      {sidebarOpen && <span className="flex-1 text-left">{item.name}</span>}
                      {sidebarOpen && (
                        <ChevronRight
                          className={cn('w-4 h-4 transition-transform', expanded && 'rotate-90')}
                          aria-hidden="true"
                        />
                      )}
                    </button>
                    {sidebarOpen && expanded && (
                      <div id={groupId} className="mt-1 ml-10 space-y-0.5 animate-in slide-in-from-top-2 duration-200">
                        {item.children.map((child) => (
                          <NavLink
                            key={child.name}
                            to={child.href}
                            onClick={() => setMobileMenuOpen(false)}
                            className={({ isActive }) =>
                              cn(
                                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors',
                                isActive
                                  ? 'bg-primary-100 text-primary-700 font-medium'
                                  : 'text-secondary-600 hover:bg-secondary-100 hover:text-secondary-900'
                              )
                            }
                          >
                            <span>{child.name}</span>
                          </NavLink>
                        ))}
                      </div>
                    )}
                  </div>
                );
              }

              return (
                <NavLink
                  key={item.name}
                  to={item.href}
                  onClick={() => setMobileMenuOpen(false)}
                  title={sidebarOpen ? undefined : item.name}
                  aria-label={sidebarOpen ? undefined : item.name}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-3 w-full rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                      isActive
                        ? 'bg-primary-50 text-primary-700'
                        : 'text-secondary-600 hover:bg-secondary-100 hover:text-secondary-900',
                      !sidebarOpen && 'justify-center'
                    )
                  }
                >
                  <item.icon className="w-5 h-5 flex-shrink-0" aria-hidden="true" />
                  {sidebarOpen && <span>{item.name}</span>}
                </NavLink>
              );
            })}
          </nav>

          {/* Footer */}
          <div className={cn('p-3 border-t border-secondary-200', sidebarOpen ? '' : 'hidden')}>
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center">
                <User className="w-4 h-4 text-primary-700" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-secondary-900 truncate">Admin User</p>
                <p className="text-xs text-secondary-500 truncate">admin@smartplan.ai</p>
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* Mobile overlay */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 lg:hidden"
          onClick={() => setMobileMenuOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Main content */}
      <div className={cn('flex-1 flex flex-col min-w-0', sidebarOpen ? 'lg:pl-64' : 'lg:pl-20')}>
        {/* Top bar */}
        <header className="sticky top-0 z-20 bg-white border-b border-secondary-200">
          <div className="flex items-center justify-between h-16 px-4 sm:px-6">
            <div className="flex items-center gap-4">
              <button
                onClick={() => {
                  setSidebarOpen(true);
                  setMobileMenuOpen((open) => !open);
                }}
                className="lg:hidden p-2 rounded-lg hover:bg-secondary-100"
                aria-label="Toggle menu"
                aria-expanded={mobileMenuOpen}
              >
                <Menu className="w-5 h-5 text-secondary-600" />
              </button>
              <button
                onClick={toggleSidebar}
                className="hidden lg:flex p-2 rounded-lg hover:bg-secondary-100"
                aria-label={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
              >
                {sidebarOpen ? <ChevronLeft className="w-5 h-5 text-secondary-600" /> : <ChevronRight className="w-5 h-5 text-secondary-600" />}
              </button>
              <div className="hidden sm:block">
                <h1 className="text-xl font-semibold text-secondary-900">SmartPlan AI</h1>
                <p className="text-xs text-secondary-500">AI-Powered Production Planning & Workforce Optimization</p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {/* Notifications and help have no backend yet: shown disabled instead of as dead buttons. */}
              <button className="p-2 rounded-lg opacity-50 cursor-not-allowed" disabled aria-label="Notifications (coming soon)" title="Notifications (coming soon)">
                <Bell className="w-5 h-5 text-secondary-600" />
              </button>
              <button className="p-2 rounded-lg opacity-50 cursor-not-allowed" disabled aria-label="Help (coming soon)" title="Help (coming soon)">
                <HelpCircle className="w-5 h-5 text-secondary-600" />
              </button>
              <div className="hidden sm:flex items-center gap-2 p-2 rounded-lg">
                <div className="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center">
                  <User className="w-4 h-4 text-primary-700" />
                </div>
                <span className="text-sm font-medium text-secondary-700">Admin</span>
                <button
                  type="button"
                  className="p-1 rounded hover:bg-secondary-100"
                  aria-label="Sign out"
                  title="Sign out"
                  onClick={() => { api.clearToken(); navigate('/login'); }}
                >
                  <LogOut className="w-4 h-4 text-secondary-500" />
                </button>
              </div>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}