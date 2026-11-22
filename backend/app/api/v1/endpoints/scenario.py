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


def scenario_verdict(fulfillment_delta: float, cost_delta: float, cost_pct: Optional[float] = None) -> tuple:
    """Overall verdict from the fulfilment-rate and total-cost deltas.

    Improvement: fulfilment >= baseline AND cost <= baseline (one strictly better).
    Worse:       fulfilment <= baseline AND cost >= baseline (one strictly worse).
    Trade-off:   one better, the other worse (e.g. cheaper but fewer orders filled).
    No change:   both equal.
    A cost cut that comes from producing less is therefore never an "Improvement".
    """
    eps = 1e-9
    f = 0 if abs(fulfillment_delta) < eps else (1 if fulfillment_delta > 0 else -1)
    c = 0 if abs(cost_delta) < eps else (1 if cost_delta > 0 else -1)
    cost_txt = f"{cost_pct:+.1f}%" if cost_pct is not None else f"{cost_delta:+,.0f}"
    reason = f"Fulfilment {fulfillment_delta:+.1f} pts, cost {cost_txt}"
    if f == 0 and c == 0:
        return "No change", reason
    if f >= 0 and c <= 0:
        return "Improvement", reason
    if f <= 0 and c >= 0:
        return "Worse", reason
    return "Trade-off", reason


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

        delta = scenario_val - baseline_val
        # A % change from a zero baseline is undefined (was reported as 0.0%
        # even for 0 -> 87 late orders); report None and let the UI show the
        # absolute change instead.
        change_pct = (delta / baseline_val) * 100 if baseline_val != 0 else None

        # None = unchanged (previously labelled a "Regression").
        if abs(delta) < 1e-9:
            improvement = None
        else:
            improvement = (delta < 0) if lower_better else (delta > 0)

        metrics.append({
            "metric": label,
            "baseline": baseline_val,
            "scenario": scenario_val,
            "change": round(delta, 2),
            "change_pct": round(change_pct, 2) if change_pct is not None else None,
            "improvement": improvement
        })

    by_label = {m["metric"]: m for m in metrics}
    verdict, verdict_reason = scenario_verdict(
        by_label["Fulfillment Rate %"]["change"],
        by_label["Total Cost"]["change"],
        by_label["Total Cost"]["change_pct"],
    )

    return ScenarioComparison(
        scenario_id=scenario.scenario_id,
        scenario_name=scenario.name,
        baseline_run_id=baseline.run_id,
        scenario_run_id=scenario_run.run_id,
        metrics=metrics,
        verdict=verdict,
        verdict_reason=verdict_reason,
        created_at=datetime.utcnow()
    )
