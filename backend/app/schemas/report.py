from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime
from enum import Enum


class ReportType(str, Enum):
    PRODUCTION = "production"
    WORKFORCE = "workforce"
    MACHINE_UTILIZATION = "machine_utilization"
    MAINTENANCE = "maintenance"
    DEMAND_FORECAST = "demand_forecast"
    OPTIMIZATION = "optimization"
    COST = "cost"


class ReportFormat(str, Enum):
    CSV = "csv"
    PDF = "pdf"


class ReportRequest(BaseModel):
    report_type: ReportType
    start_date: date
    end_date: date
    format: ReportFormat = ReportFormat.CSV
    filters: Optional[dict] = None


class ReportResponse(BaseModel):
    report_id: str
    report_type: ReportType
    format: ReportFormat
    file_path: Optional[str] = None
    download_url: Optional[str] = None
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True