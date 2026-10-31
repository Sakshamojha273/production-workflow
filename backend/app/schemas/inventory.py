from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from enum import Enum


class InventoryStatus(str, Enum):
    HEALTHY = "Healthy"
    LOW = "Low"
    CRITICAL = "Critical"


class InventoryResponse(BaseModel):
    product_id: str
    product_name: str
    category: str
    current_level: int
    safety_stock: int
    reorder_point: int
    max_stock: int
    unit_cost: float
    coverage_days: float
    status: InventoryStatus
    last_updated: datetime
    
    class Config:
        from_attributes = True


class InventoryListResponse(BaseModel):
    inventory: List[InventoryResponse]
    total: int