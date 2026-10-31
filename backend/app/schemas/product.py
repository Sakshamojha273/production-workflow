from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime


class ProductResponse(BaseModel):
    product_id: str
    name: str
    category: str
    base_demand: int
    base_cost: float
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    products: list[ProductResponse]
    total: int