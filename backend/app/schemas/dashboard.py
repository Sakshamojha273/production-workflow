from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime
from enum import Enum


class KPITrend(str, Enum):
    UP = "up"
    DOWN = "down"
    NEUTRAL = "neutral"


class KPIStatus(str, Enum):
    HEALTHY = "Healthy"
    WARNING = "Warning"
    CRITICAL = "Critical"


class KPICard(BaseModel):
    title: str
    value: str
    trend: Optional[float] = None
    trend_direction: KPITrend = KPITrend.NEUTRAL
    description: Optional[str] = None
    status: KPIStatus = KPIStatus.HEALTHY


class DashboardResponse(BaseModel):
    kpis: List[KPICard]
    charts: dict
    timestamp: datetime
    
    class Config:
        from_attributes = True