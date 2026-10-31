from sqlalchemy import Column, String, Integer, Float, DateTime, Time, Enum, Index
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
import uuid
from datetime import datetime
import enum


class ShiftType(str, enum.Enum):
    DAY = "Day"
    NIGHT = "Night"
    EVENING = "Evening"


class Shift(Base):
    __tablename__ = "shifts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shift_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(50), nullable=False)
    type = Column(Enum(ShiftType), nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    max_workers = Column(Integer, default=20)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("ix_shifts_type", "type"),
    )