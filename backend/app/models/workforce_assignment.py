from sqlalchemy import Column, String, Integer, Float, DateTime, Date, ForeignKey, Enum, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid
from datetime import datetime
import enum


class AssignmentStatus(str, enum.Enum):
    ASSIGNED = "Assigned"
    CONFIRMED = "Confirmed"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


class WorkforceAssignment(Base):
    __tablename__ = "workforce_assignments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    production_plan_id = Column(UUID(as_uuid=True), ForeignKey("production_plans.id"), nullable=False)
    worker_id = Column(String(50), ForeignKey("workers.worker_id"), nullable=False)
    machine_id = Column(String(50), ForeignKey("machines.machine_id"), nullable=False)
    product_id = Column(String(50), ForeignKey("products.product_id"), nullable=False)
    date = Column(Date, nullable=False)
    shift = Column(String(20), nullable=False)
    assigned_hours = Column(Float, default=0.0)
    overtime_hours = Column(Float, default=0.0)
    skill_match = Column(Float, default=1.0)
    status = Column(Enum(AssignmentStatus), default=AssignmentStatus.ASSIGNED)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    production_plan = relationship("ProductionPlan", backref="workforce_assignments")
    worker = relationship("Worker", backref="assignments")
    machine = relationship("Machine", backref="assignments")
    product = relationship("Product", backref="assignments")
    
    __table_args__ = (
        Index("ix_workforce_assignments_plan_date", "production_plan_id", "date"),
        Index("ix_workforce_assignments_worker_date", "worker_id", "date"),
    )