from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from enum import Enum
import json
import uuid


class PlanStatus(str, Enum):
    DRAFT = "Draft"
    GENERATED = "Generated"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    EXECUTING = "Executing"
    COMPLETED = "Completed"


class PlanningRequest(BaseModel):
    start_date: date
    end_date: date
    product_ids: Optional[List[str]] = None
    machine_ids: Optional[List[str]] = None
    max_overtime_hours: Optional[int] = Field(default=8, ge=0, le=24)
    priority_weights: Optional[Dict[str, float]] = None

    @model_validator(mode="after")
    def check_window(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class PlanScheduleEntry(BaseModel):
    date: date
    machine_id: str
    quantity: int


class PlanItemResponse(BaseModel):
    order_id: str
    product_id: str
    product_name: str
    demand: int
    planned_production: int
    machine_id: str
    machine_name: str
    due_date: date
    priority: str
    production_time_minutes: int
    cost: float
    status: str
    worker_id: Optional[str] = None
    worker_name: Optional[str] = None
    shift: Optional[str] = None
    # Added fields (optional, backwards compatible)
    from_inventory: int = 0
    backlog: int = 0
    late_units: int = 0
    completion_date: Optional[date] = None
    schedule: List[PlanScheduleEntry] = []

    class Config:
        from_attributes = True

    @field_validator("schedule", mode="before")
    @classmethod
    def parse_schedule(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            return json.loads(value)
        return value

    @field_validator("product_name", "machine_id", "machine_name", mode="before")
    @classmethod
    def none_to_empty(cls, value):
        return "" if value is None else value


class PlanningResponse(BaseModel):
    plan_id: str
    optimization_run_id: Optional[str] = None
    start_date: date
    end_date: date
    total_demand: int
    total_production: int
    total_cost: float
    total_overtime: int
    late_orders: int
    machine_utilization: float
    workforce_utilization: float
    fulfillment_rate: float
    status: PlanStatus
    items: List[PlanItemResponse] = []
    created_at: datetime
    notes: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

    @field_validator("optimization_run_id", mode="before")
    @classmethod
    def uuid_to_str(cls, value):
        if isinstance(value, uuid.UUID):
            return str(value)
        return value

    @field_validator("notes", mode="before")
    @classmethod
    def parse_notes(cls, value):
        if value is None or isinstance(value, dict):
            return value
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return {"text": str(value)}
        return parsed if isinstance(parsed, dict) else {"value": parsed}


class PlanListResponse(BaseModel):
    plans: List[PlanningResponse]
    total: int
