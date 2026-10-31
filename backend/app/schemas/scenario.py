from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import json


class ScenarioStatus(str, Enum):
    DRAFT = "Draft"
    RUNNING = "Running"
    COMPLETED = "Completed"
    FAILED = "Failed"


class ScenarioRequest(BaseModel):
    name: str
    description: Optional[str] = None
    demand_change_pct: float = Field(default=0.0, ge=-100, le=100)
    machine_availability_change_pct: float = Field(default=0.0, ge=-100, le=100)
    worker_availability_change_pct: float = Field(default=0.0, ge=-100, le=100)
    overtime_limit_change_pct: float = Field(default=0.0, ge=-100, le=100)
    production_target_change_pct: float = Field(default=0.0, ge=-100, le=100)
    inventory_change_pct: float = Field(default=0.0, ge=-100, le=100)
    machine_failure_ids: Optional[List[str]] = None


class ScenarioRunRequest(BaseModel):
    # Accepts either the optimisation run code (e.g. "OPT-1A2B3C4D") or the
    # run UUID exposed as ProductionPlan.optimization_run_id.
    baseline_run_id: str


class ScenarioComparisonMetric(BaseModel):
    metric: str
    baseline: float
    scenario: float
    change_pct: float
    improvement: bool


class ScenarioComparison(BaseModel):
    scenario_id: str
    scenario_name: str
    baseline_run_id: str
    scenario_run_id: str
    metrics: List[ScenarioComparisonMetric]
    created_at: datetime


class ScenarioResponse(BaseModel):
    scenario_id: str
    name: str
    description: Optional[str]
    demand_change_pct: float
    machine_availability_change_pct: float
    worker_availability_change_pct: float
    overtime_limit_change_pct: float
    production_target_change_pct: float
    inventory_change_pct: float
    machine_failure_ids: Optional[List[str]]
    status: ScenarioStatus
    comparison_results: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

    @field_validator("machine_failure_ids", "comparison_results", mode="before")
    @classmethod
    def parse_json_text(cls, value):
        # Both columns are stored as JSON text in the database.
        if isinstance(value, str):
            return json.loads(value) if value else None
        return value