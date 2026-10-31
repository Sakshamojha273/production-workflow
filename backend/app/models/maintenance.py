from sqlalchemy import Column, String, Integer, Float, DateTime, Date, Text, Enum, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid
from datetime import datetime
import enum


class MaintenanceType(str, enum.Enum):
    PREVENTIVE = "Preventive"
    CORRECTIVE = "Corrective"
    PREDICTIVE = "Predictive"
    EMERGENCY = "Emergency"


class MaintenanceStatus(str, enum.Enum):
    SCHEDULED = "Scheduled"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"
    OVERDUE = "Overdue"


class Maintenance(Base):
    __tablename__ = "maintenance"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    maintenance_id = Column(String(50), unique=True, nullable=False, index=True)
    machine_id = Column(String(50), ForeignKey("machines.machine_id"), nullable=False)
    type = Column(Enum(MaintenanceType), nullable=False)
    status = Column(Enum(MaintenanceStatus), default=MaintenanceStatus.SCHEDULED)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    description = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    cost = Column(Float, default=0.0)
    performed_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    machine = relationship("Machine", backref="maintenance_records")
    
    __table_args__ = (
        Index("ix_maintenance_machine_date", "machine_id", "start_date"),
        Index("ix_maintenance_status", "status"),
    )