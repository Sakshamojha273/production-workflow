from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class DataQualityStatus(str, Enum):
    PENDING = "Pending"
    PROCESSING = "Processing"
    COMPLETED = "Completed"
    FAILED = "Failed"


class DataUploadResponse(BaseModel):
    report_id: str
    filename: str
    total_rows: int
    total_columns: int
    missing_values: int
    duplicate_rows: int
    invalid_records: int
    outliers: int
    quality_score: float
    missing_by_column: Dict[str, int]
    column_types: Dict[str, str]
    sample_data: List[Dict[str, Any]]
    status: DataQualityStatus
    created_at: datetime
    
    class Config:
        from_attributes = True


class DataQualityResponse(BaseModel):
    report_id: str
    filename: str
    total_rows: int
    total_columns: int
    missing_values: int
    duplicate_rows: int
    invalid_records: int
    outliers: int
    quality_score: float
    missing_by_column: Dict[str, int]
    column_types: Dict[str, str]
    status: DataQualityStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True