from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum


class WorkerAvailability(str, Enum):
    AVAILABLE = "Available"
    UNAVAILABLE = "Unavailable"
    ON_LEAVE = "On Leave"


class WorkerSkillResponse(BaseModel):
    machine_type: str
    proficiency: float
    certified: bool


class WorkerResponse(BaseModel):
    worker_id: str
    name: str
    department: str
    shift: str
    availability: WorkerAvailability
    availability_factor: Optional[float] = 1.0
    max_hours_per_week: int
    current_hours: int
    overtime_hours: int
    skills: List[WorkerSkillResponse] = []
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class WorkerListResponse(BaseModel):
    workers: List[WorkerResponse]
    total: int