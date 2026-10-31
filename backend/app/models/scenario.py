from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Enum, Index
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
import uuid
from datetime import datetime
import enum


class ScenarioStatus(str, enum.Enum):
    DRAFT = "Draft"
    RUNNING = "Running"
    COMPLETED = "Completed"
    FAILED = "Failed"


class Scenario(Base):
    __tablename__ = "scenarios"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scenario_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    baseline_run_id = Column(UUID(as_uuid=True), nullable=True)
    demand_change_pct = Column(Float, default=0.0)
    machine_availability_change_pct = Column(Float, default=0.0)
    worker_availability_change_pct = Column(Float, default=0.0)
    overtime_limit_change_pct = Column(Float, default=0.0)
    production_target_change_pct = Column(Float, default=0.0)
    inventory_change_pct = Column(Float, default=0.0)
    machine_failure_ids = Column(Text, nullable=True)  # JSON array
    status = Column(Enum(ScenarioStatus), default=ScenarioStatus.DRAFT)
    comparison_results = Column(Text, nullable=True)  # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index("ix_scenarios_status", "status"),
    )