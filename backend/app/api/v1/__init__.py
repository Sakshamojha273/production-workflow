from fastapi import APIRouter, Depends

from app.core.security import require_user
from app.api.v1.endpoints import (
    dashboard,
    orders,
    products,
    machines,
    workers,
    inventory,
    forecast,
    planning,
    scenario,
    data,
    reports,
    auth,
    analytics,
    maintenance,
    system_settings,
)

# Every router except /auth requires a valid bearer token (app/core/security.py).
api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"], dependencies=[Depends(require_user)])
api_router.include_router(orders.router, prefix="/orders", tags=["Orders"], dependencies=[Depends(require_user)])
api_router.include_router(products.router, prefix="/products", tags=["Products"], dependencies=[Depends(require_user)])
api_router.include_router(machines.router, prefix="/machines", tags=["Machines"], dependencies=[Depends(require_user)])
api_router.include_router(workers.router, prefix="/workers", tags=["Workers"], dependencies=[Depends(require_user)])
api_router.include_router(inventory.router, prefix="/inventory", tags=["Inventory"], dependencies=[Depends(require_user)])
api_router.include_router(forecast.router, prefix="/forecast", tags=["Forecast"], dependencies=[Depends(require_user)])
api_router.include_router(planning.router, prefix="/planning", tags=["Planning"], dependencies=[Depends(require_user)])
api_router.include_router(scenario.router, prefix="/scenario", tags=["Scenario"], dependencies=[Depends(require_user)])
api_router.include_router(data.router, prefix="/data", tags=["Data"], dependencies=[Depends(require_user)])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"], dependencies=[Depends(require_user)])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"], dependencies=[Depends(require_user)])
api_router.include_router(maintenance.router, prefix="/maintenance", tags=["Maintenance"], dependencies=[Depends(require_user)])
api_router.include_router(system_settings.router, prefix="/settings", tags=["Settings"], dependencies=[Depends(require_user)])
