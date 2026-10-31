from sqlalchemy import Column, String, Integer, Float, DateTime, Date, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid
from datetime import datetime


class DemandHistory(Base):
    __tablename__ = "demand_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(String(50), ForeignKey("products.product_id"), nullable=False)
    date = Column(Date, nullable=False)
    demand = Column(Integer, nullable=False)
    production_quantity = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    product = relationship("Product", backref="demand_history")
    
    __table_args__ = (
        Index("ix_demand_history_product_date", "product_id", "date", unique=True),
    )