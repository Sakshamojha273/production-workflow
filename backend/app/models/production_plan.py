from sqlalchemy import Column, String, Integer, Float, DateTime, Date, ForeignKey, Text, Enum, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid
from datetime import datetime
import enum


class PlanStatus(str, enum.Enum):
    DRAFT = "Draft"
    GENERATED = "Generated"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    EXECUTING = "Executing"
    COMPLETED = "Completed"


class ProductionPlan(Base):
    __tablename__ = "production_plans"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id = Column(String(50), unique=True, nullable=False, index=True)
    optimization_run_id = Column(UUID(as_uuid=True), ForeignKey("optimization_runs.id"), nullable=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    total_demand = Column(Integer, default=0)
    total_production = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)
    total_overtime = Column(Integer, default=0)
    late_orders = Column(Integer, default=0)
    machine_utilization = Column(Float, default=0.0)
    workforce_utilization = Column(Float, default=0.0)
    fulfillment_rate = Column(Float, default=0.0)
    status = Column(Enum(PlanStatus), default=PlanStatus.DRAFT)
    notes = Column(Text, nullable=True)
    approved_by = Column(String(100), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    optimization_run = relationship("OptimizationRun", backref="production_plans")
    
    __table_args__ = (
        Index("ix_production_plans_dates", "start_date", "end_date"),
        Index("ix_production_plans_status", "status"),
    )