from pydantic import BaseModel, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class DataQualityStatus(str, Enum):
    PENDING = "Pending"
    PROCESSING = "Processing"
    COMPLETED = "Completed"
    FAILED = "Failed"


class _NullSafeProfile(BaseModel):
    """Reports saved by older failed uploads have NULL profile columns; read them as empty."""

    @field_validator("missing_by_column", "column_types", mode="before", check_fields=False)
    @classmethod
    def _empty_dict(cls, value: Any) -> Any:
        return {} if value is None else value

    @field_validator("sample_data", mode="before", check_fields=False)
    @classmethod
    def _empty_list(cls, value: Any) -> Any:
        return [] if value is None else value

    @field_validator("total_rows", "total_columns", "missing_values", "duplicate_rows",
                     "invalid_records", "outliers", mode="before", check_fields=False)
    @classmethod
    def _zero_int(cls, value: Any) -> Any:
        return 0 if value is None else value

    @field_validator("quality_score", mode="before", check_fields=False)
    @classmethod
    def _zero_float(cls, value: Any) -> Any:
        return 0.0 if value is None else value


class DataUploadResponse(_NullSafeProfile):
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


class DataQualityResponse(_NullSafeProfile):
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
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True