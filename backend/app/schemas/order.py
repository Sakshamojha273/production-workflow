from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime
from enum import Enum


class OrderPriority(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class OrderStatus(str, Enum):
    COMPLETED = "Completed"
    IN_PROGRESS = "In Progress"
    PENDING = "Pending"
    DELAYED = "Delayed"


class OrderResponse(BaseModel):
    order_id: str
    date: date
    product_id: str
    product_name: str
    category: str
    demand: int
    production_quantity: int
    machine_id: str
    machine_name: str
    machine_type: str
    machine_capacity: int
    machine_availability: float
    maintenance_status: str
    worker_id: str
    worker_name: str
    department: str
    shift: str
    worker_availability: float
    production_time_minutes: int
    overtime_hours: int
    production_cost: float
    machine_vibration: float
    machine_temperature_c: float
    machine_risk_score: float
    next_day_demand: int
    priority: OrderPriority
    due_date: date
    status: OrderStatus
    inventory_level: int
    safety_stock: int
    
    class Config:
        from_attributes = True


class OrderListResponse(BaseModel):
    orders: List[OrderResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class OrderFilter(BaseModel):
    page: int = 1
    page_size: int = 50
    product_id: Optional[str] = None
    machine_id: Optional[str] = None
    priority: Optional[OrderPriority] = None
    status: Optional[OrderStatus] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    search: Optional[str] = None