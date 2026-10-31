from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.analytics import AnalyticsService

router = APIRouter()


@router.get("/summary")
async def get_analytics_summary(db: AsyncSession = Depends(get_db)):
    """Get comprehensive analytics summary"""
    analytics = AnalyticsService(db)
    return await analytics.get_analytics_summary()


@router.get("/kpis")
async def get_kpis(db: AsyncSession = Depends(get_db)):
    """Get KPI data"""
    analytics = AnalyticsService(db)
    return await analytics.get_dashboard_kpis()


@router.get("/charts")
async def get_charts(db: AsyncSession = Depends(get_db)):
    """Get chart data"""
    analytics = AnalyticsService(db)
    return await analytics.get_chart_data()