from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum


class MachineStatus(str, Enum):
    OPERATIONAL = "Operational"
    MAINTENANCE = "Maintenance"
    OFFLINE = "Offline"


class MachineResponse(BaseModel):
    machine_id: str
    name: str
    type: str
    capacity: int
    availability: int
    availability_factor: Optional[float] = 1.0
    utilization: float
    status: MachineStatus
    vibration: float
    temperature_c: float
    risk_score: float
    last_maintenance: Optional[datetime] = None
    next_maintenance: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class MachineListResponse(BaseModel):
    machines: List[MachineResponse]
    total: int