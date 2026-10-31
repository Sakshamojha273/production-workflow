from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Enum, Index
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
import uuid
from datetime import datetime
import enum


class OptimizationStatus(str, enum.Enum):
    PENDING = "Pending"
    RUNNING = "Running"
    COMPLETED = "Completed"
    FAILED = "Failed"
    TIMEOUT = "Timeout"


class OptimizationRun(Base):
    __tablename__ = "optimization_runs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(String(50), unique=True, nullable=False, index=True)
    scenario_id = Column(UUID(as_uuid=True), nullable=True)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    status = Column(Enum(OptimizationStatus), default=OptimizationStatus.PENDING)
    objective_value = Column(Float, nullable=True)
    solve_time_seconds = Column(Float, nullable=True)
    total_cost = Column(Float, default=0.0)
    total_overtime = Column(Integer, default=0)
    late_orders = Column(Integer, default=0)
    machine_utilization = Column(Float, default=0.0)
    workforce_utilization = Column(Float, default=0.0)
    fulfillment_rate = Column(Float, default=0.0)
    num_variables = Column(Integer, default=0)
    num_constraints = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    parameters = Column(Text, nullable=True)  # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index("ix_optimization_runs_status", "status"),
        Index("ix_optimization_runs_dates", "start_date", "end_date"),
    )