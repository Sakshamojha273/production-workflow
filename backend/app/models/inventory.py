from sqlalchemy import Column, String, Integer, Float, DateTime, Date, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid
from datetime import datetime


class Inventory(Base):
    __tablename__ = "inventory"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(String(50), ForeignKey("products.product_id"), unique=True, nullable=False)
    current_level = Column(Integer, default=0)
    safety_stock = Column(Integer, default=0)
    reorder_point = Column(Integer, default=0)
    max_stock = Column(Integer, default=0)
    unit_cost = Column(Float, default=0.0)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    product = relationship("Product", backref="inventory")
    
    __table_args__ = (
        Index("ix_inventory_product", "product_id"),
    )