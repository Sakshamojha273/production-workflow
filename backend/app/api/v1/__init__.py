from fastapi import APIRouter
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
    maintenance
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(orders.router, prefix="/orders", tags=["Orders"])
api_router.include_router(products.router, prefix="/products", tags=["Products"])
api_router.include_router(machines.router, prefix="/machines", tags=["Machines"])
api_router.include_router(workers.router, prefix="/workers", tags=["Workers"])
api_router.include_router(inventory.router, prefix="/inventory", tags=["Inventory"])
api_router.include_router(forecast.router, prefix="/forecast", tags=["Forecast"])
api_router.include_router(planning.router, prefix="/planning", tags=["Planning"])
api_router.include_router(scenario.router, prefix="/scenario", tags=["Scenario"])
api_router.include_router(data.router, prefix="/data", tags=["Data"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
api_router.include_router(maintenance.router, prefix="/maintenance", tags=["Maintenance"])