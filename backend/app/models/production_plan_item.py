from sqlalchemy import Column, String, Integer, Float, DateTime, Date, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid
from datetime import datetime


class ProductionPlanItem(Base):
    """One row per order in a generated plan (solver output, persisted as-is)."""

    __tablename__ = "production_plan_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    production_plan_id = Column(UUID(as_uuid=True), ForeignKey("production_plans.id", ondelete="CASCADE"), nullable=False)
    order_id = Column(String(50), nullable=False)
    product_id = Column(String(50), nullable=False)
    product_name = Column(String(200), nullable=True)
    machine_id = Column(String(50), nullable=True)  # machine with the largest share of the order
    machine_name = Column(String(100), nullable=True)
    demand = Column(Integer, default=0)
    planned_production = Column(Integer, default=0)
    from_inventory = Column(Integer, default=0)
    backlog = Column(Integer, default=0)
    late_units = Column(Integer, default=0)
    due_date = Column(Date, nullable=False)
    completion_date = Column(Date, nullable=True)
    priority = Column(String(20), nullable=False)
    production_time_minutes = Column(Integer, default=0)
    cost = Column(Float, default=0.0)
    status = Column(String(20), nullable=False)
    worker_id = Column(String(50), nullable=True)
    worker_name = Column(String(100), nullable=True)
    shift = Column(String(20), nullable=True)
    schedule = Column(Text, nullable=True)  # JSON list of {date, machine_id, quantity}
    created_at = Column(DateTime, default=datetime.utcnow)

    production_plan = relationship("ProductionPlan", backref="plan_items")

    __table_args__ = (
        Index("ix_production_plan_items_plan", "production_plan_id"),
    )
