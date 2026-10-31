from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Enum, Index
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
import uuid
from datetime import datetime
import enum


class MachineStatus(str, enum.Enum):
    OPERATIONAL = "Operational"
    MAINTENANCE = "Maintenance"
    OFFLINE = "Offline"


class Machine(Base):
    __tablename__ = "machines"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    machine_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    type = Column(String(50), nullable=False)
    capacity = Column(Integer, nullable=False)
    availability = Column(Integer, default=1)  # 1 = in service, 0 = out of service
    availability_factor = Column(Float, default=1.0)  # mean fractional availability (0-1) from source data
    utilization = Column(Float, default=0.0)
    status = Column(Enum(MachineStatus), default=MachineStatus.OPERATIONAL)
    vibration = Column(Float, default=0.0)
    temperature_c = Column(Float, default=0.0)
    risk_score = Column(Float, default=0.0)
    last_maintenance = Column(DateTime, nullable=True)
    next_maintenance = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("ix_machines_type", "type"),
        Index("ix_machines_status", "status"),
    )