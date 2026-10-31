from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Enum, Index
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator
from typing import Any
import uuid
from datetime import datetime
import enum
import json


class JSONEncodedText(TypeDecorator[Any]):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> str | None:
        return None if value is None else json.dumps(value)

    def process_result_value(self, value: str | None, dialect: Dialect) -> Any:
        return None if value is None else json.loads(value)


class DataQualityStatus(str, enum.Enum):
    PENDING = "Pending"
    PROCESSING = "Processing"
    COMPLETED = "Completed"
    FAILED = "Failed"


class DataQualityReport(Base):
    __tablename__ = "data_quality_reports"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(String(50), unique=True, nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    total_rows = Column(Integer, default=0)
    total_columns = Column(Integer, default=0)
    missing_values = Column(Integer, default=0)
    duplicate_rows = Column(Integer, default=0)
    invalid_records = Column(Integer, default=0)
    outliers = Column(Integer, default=0)
    quality_score = Column(Float, default=0.0)
    missing_by_column = Column(JSONEncodedText(), nullable=True)
    column_types = Column(JSONEncodedText(), nullable=True)
    sample_data = Column(JSONEncodedText(), nullable=True)
    status = Column(Enum(DataQualityStatus), default=DataQualityStatus.PENDING)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index("ix_data_quality_reports_status", "status"),
    )