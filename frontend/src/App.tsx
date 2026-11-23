import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { MainLayout } from './layouts/MainLayout';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { ProductionPlanningPage } from './pages/ProductionPlanningPage';
import { DemandForecastPage } from './pages/DemandForecastPage';
import { MachineHealthPage } from './pages/MachineHealthPage';
import { WorkforcePage } from './pages/WorkforcePage';
import { WhatIfAnalysisPage } from './pages/WhatIfAnalysisPage';
import { OrdersPage } from './pages/OrdersPage';
import { MachinesPage } from './pages/MachinesPage';
import { InventoryPage } from './pages/InventoryPage';
import { MaintenancePage } from './pages/MaintenancePage';
import { DataUploadPage } from './pages/DataUploadPage';
import { DataQualityPage } from './pages/DataQualityPage';
import { ReportsPage } from './pages/ReportsPage';
import { SettingsPage } from './pages/SettingsPage';
import { WebResearchPage } from './pages/WebResearchPage';
import { WebSearchPage } from './pages/WebSearchPage';
import { api } from './services/api';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = api.isAuthenticated();
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute><MainLayout /></ProtectedRoute>}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/planning/production" element={<ProductionPlanningPage />} />
        <Route path="/planning/workforce" element={<WorkforcePage />} />
        <Route path="/planning/what-if" element={<WhatIfAnalysisPage />} />
        <Route path="/analytics/demand-forecast" element={<DemandForecastPage />} />
        <Route path="/analytics/machine-health" element={<MachineHealthPage />} />
        <Route path="/analytics/research" element={<WebResearchPage />} />
        <Route path="/analytics/search" element={<WebSearchPage />} />
        <Route path="/analytics/overview" element={<DashboardPage />} />
        <Route path="/operations/orders" element={<OrdersPage />} />
        <Route path="/operations/machines" element={<MachinesPage />} />
        <Route path="/operations/workforce" element={<WorkforcePage />} />
        <Route path="/operations/inventory" element={<InventoryPage />} />
        <Route path="/operations/maintenance" element={<MaintenancePage />} />
        <Route path="/data/upload" element={<DataUploadPage />} />
        <Route path="/data/quality" element={<DataQualityPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

export default App;