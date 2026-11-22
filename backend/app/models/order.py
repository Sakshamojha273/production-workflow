from sqlalchemy import Column, String, Integer, Float, DateTime, Date, Text, Enum, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid
from datetime import datetime
import enum


class OrderPriority(str, enum.Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class OrderStatus(str, enum.Enum):
    COMPLETED = "Completed"
    IN_PROGRESS = "In Progress"
    PENDING = "Pending"
    DELAYED = "Delayed"


class Order(Base):
    __tablename__ = "orders"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(String(50), unique=True, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    product_id = Column(String(50), ForeignKey("products.product_id"), nullable=False)
    demand = Column(Integer, nullable=False)
    production_quantity = Column(Integer, default=0)
    machine_id = Column(String(50), ForeignKey("machines.machine_id"), nullable=False)
    machine_availability = Column(Float, default=1.0)  # fractional availability (0-1)
    maintenance_status = Column(String(50), default="Operational")
    worker_id = Column(String(50), ForeignKey("workers.worker_id"), nullable=False)
    shift = Column(String(20), nullable=False)
    worker_availability = Column(Float, default=1.0)  # fractional availability (0-1)
    production_time_minutes = Column(Integer, default=0)
    overtime_hours = Column(Integer, default=0)
    production_cost = Column(Float, default=0.0)
    machine_vibration = Column(Float, default=0.0)
    machine_temperature_c = Column(Float, default=0.0)
    machine_risk_score = Column(Float, default=0.0)
    next_day_demand = Column(Integer, default=0)
    priority = Column(Enum(OrderPriority), default=OrderPriority.MEDIUM)
    due_date = Column(Date, nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING)
    inventory_level = Column(Integer, default=0)
    safety_stock = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    product = relationship("Product", backref="orders")
    machine = relationship("Machine", backref="orders")
    worker = relationship("Worker", backref="orders")
    
    __table_args__ = (
        Index("ix_orders_date_product", "date", "product_id"),
        Index("ix_orders_machine_date", "machine_id", "date"),
        Index("ix_orders_status", "status"),
    )