from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.analytics import AnalyticsService
from app.schemas.dashboard import DashboardResponse

router = APIRouter()


@router.get("", response_model=DashboardResponse)
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    """Get dashboard data including KPIs and charts"""
    analytics = AnalyticsService(db)
    
    kpis = await analytics.get_dashboard_kpis()
    charts = await analytics.get_chart_data()
    
    return DashboardResponse(
        kpis=[{"title": k, **v} for k, v in kpis.items()],
        charts=charts,
        timestamp=datetime.utcnow()
    )


from datetime import datetime