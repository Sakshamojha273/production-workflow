from datetime import datetime
from typing import Optional, List
import json
import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.scenario import Scenario, ScenarioStatus
from app.models.optimization_run import OptimizationRun, OptimizationStatus
from app.optimization.production_optimizer import ProductionOptimizer
from app.schemas.scenario import ScenarioRequest, ScenarioResponse, ScenarioComparison, ScenarioRunRequest

router = APIRouter()


@router.get("", response_model=List[ScenarioResponse])
async def get_scenarios(
    status: Optional[ScenarioStatus] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get all scenarios"""
    stmt = select(Scenario).order_by(Scenario.created_at.desc())

    if status:
        stmt = stmt.where(Scenario.status == status)

    result = await db.execute(stmt)
    scenarios = result.scalars().all()

    return [ScenarioResponse.model_validate(s, from_attributes=True) for s in scenarios]


@router.get("/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(scenario_id: str, db: AsyncSession = Depends(get_db)):
    """Get scenario by ID"""
    stmt = select(Scenario).where(Scenario.scenario_id == scenario_id)
    result = await db.execute(stmt)
    scenario = result.scalar_one_or_none()

    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    return ScenarioResponse.model_validate(scenario, from_attributes=True)


@router.post("", response_model=ScenarioResponse)
async def create_scenario(
    request: ScenarioRequest,
    db: AsyncSession = Depends(get_db)
):
    """Create a new what-if scenario"""
    scenario = Scenario(
        scenario_id=f"SCN-{uuid.uuid4().hex[:8].upper()}",
        name=request.name,
        description=request.description,
        demand_change_pct=request.demand_change_pct,
        machine_availability_change_pct=request.machine_availability_change_pct,
        worker_availability_change_pct=request.worker_availability_change_pct,
        overtime_limit_change_pct=request.overtime_limit_change_pct,
        production_target_change_pct=request.production_target_change_pct,
        inventory_change_pct=request.inventory_change_pct,
        # Stored as JSON text (Text column).
        machine_failure_ids=json.dumps(request.machine_failure_ids) if request.machine_failure_ids else None,
        status=ScenarioStatus.DRAFT
    )

    db.add(scenario)
    await db.commit()
    await db.refresh(scenario)

    return ScenarioResponse.model_validate(scenario, from_attributes=True)


async def _find_run(db: AsyncSession, run_ref: str) -> Optional[OptimizationRun]:
    """Look a run up by its code (OPT-xxxx) or by its UUID."""
    stmt = select(OptimizationRun).where(OptimizationRun.run_id == run_ref)
    run = (await db.execute(stmt)).scalar_one_or_none()
    if run:
        return run
    try:
        run_uuid = uuid.UUID(run_ref)
    except (TypeError, ValueError):
        return None
    return (await db.execute(select(OptimizationRun).where(OptimizationRun.id == run_uuid))).scalar_one_or_none()


@router.post("/{scenario_id}/run", response_model=ScenarioComparison)
async def run_scenario(
    scenario_id: str,
    body: Optional[ScenarioRunRequest] = Body(default=None),
    baseline_run_id: Optional[str] = Query(default=None, description="Deprecated: send it in the JSON body"),
    db: AsyncSession = Depends(get_db)
):
    """Run a what-if scenario against a baseline optimisation run.

    The baseline may be given in the JSON body (``{"baseline_run_id": ...}``,
    used by the frontend) or, for backwards compatibility, as a query param.
    """
    run_ref = (body.baseline_run_id if body else None) or baseline_run_id
    if not run_ref:
        raise HTTPException(status_code=422, detail="baseline_run_id is required")

    scenario = (await db.execute(
        select(Scenario).where(Scenario.scenario_id == scenario_id)
    )).scalar_one_or_none()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    baseline_run = await _find_run(db, run_ref)
    if not baseline_run:
        raise HTTPException(status_code=404, detail="Baseline run not found")
    if baseline_run.status != OptimizationStatus.COMPLETED:
        raise HTTPException(
            status_code=409,
            detail=f"Baseline run {baseline_run.run_id} did not complete successfully; generate a plan first",
        )

    scenario.status = ScenarioStatus.RUNNING
    scenario.baseline_run_id = baseline_run.id
    await db.commit()

    try:
        failure_ids = json.loads(scenario.machine_failure_ids) if scenario.machine_failure_ids else []
        optimizer = ProductionOptimizer(db)
        new_run = await optimizer.run_scenario(
            baseline_run_id=baseline_run.id,
            demand_change_pct=scenario.demand_change_pct or 0,
            machine_availability_change_pct=scenario.machine_availability_change_pct or 0,
            worker_availability_change_pct=scenario.worker_availability_change_pct or 0,
            overtime_limit_change_pct=scenario.overtime_limit_change_pct or 0,
            production_target_change_pct=scenario.production_target_change_pct or 0,
            inventory_change_pct=scenario.inventory_change_pct or 0,
            machine_failure_ids=failure_ids,
            scenario_id=scenario.id,
        )
    except Exception as exc:
        await db.rollback()
        scenario.status = ScenarioStatus.FAILED
        await db.commit()
        raise HTTPException(status_code=500, detail=str(exc))

    if new_run.status != OptimizationStatus.COMPLETED:
        # Never report success for a failed re-optimisation.
        scenario.status = ScenarioStatus.FAILED
        scenario.comparison_results = json.dumps({"error": new_run.error_message, "scenario_run_id": new_run.run_id})
        await db.commit()
        raise HTTPException(
            status_code=422,
            detail=f"Scenario optimisation failed: {new_run.error_message or 'unknown error'}",
        )

    comparison = _compare_runs(baseline_run, new_run, scenario)
    scenario.status = ScenarioStatus.COMPLETED
    scenario.completed_at = datetime.utcnow()
    scenario.comparison_results = comparison.model_dump_json()
    await db.commit()

    return comparison


def _compare_runs(baseline: OptimizationRun, scenario_run: OptimizationRun, scenario: Scenario) -> ScenarioComparison:
    """Compare two optimization runs"""
    metrics = []

    metric_defs = [
        ("total_cost", "Total Cost", True),  # True = lower is better
        ("total_overtime", "Overtime Hours", True),
        ("late_orders", "Late Orders", True),
        ("machine_utilization", "Machine Utilization %", False),
        ("workforce_utilization", "Workforce Utilization %", False),
        ("fulfillment_rate", "Fulfillment Rate %", False),
    ]

    for attr, label, lower_better in metric_defs:
        baseline_val = getattr(baseline, attr) or 0
        scenario_val = getattr(scenario_run, attr) or 0

        if baseline_val != 0:
            change_pct = ((scenario_val - baseline_val) / baseline_val) * 100
        else:
            change_pct = 0

        improvement = (change_pct < 0) if lower_better else (change_pct > 0)

        metrics.append({
            "metric": label,
            "baseline": baseline_val,
            "scenario": scenario_val,
            "change_pct": round(change_pct, 2),
            "improvement": improvement
        })

    return ScenarioComparison(
        scenario_id=scenario.scenario_id,
        scenario_name=scenario.name,
        baseline_run_id=baseline.run_id,
        scenario_run_id=scenario_run.run_id,
        metrics=metrics,
        created_at=datetime.utcnow()
    )
