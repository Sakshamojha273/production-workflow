from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
import uuid
from datetime import datetime


class Product(Base):
    __tablename__ = "products"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False)
    base_demand = Column(Integer, default=0)
    base_cost = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("ix_products_category", "category"),
    )