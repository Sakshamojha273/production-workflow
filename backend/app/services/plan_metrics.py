"""Utilization metrics derived from the latest baseline production plan.

Machine and worker utilization are properties of a *plan*, not of the raw
order history, so the Dashboard, Machines page and Workforce roster read them
from the most recent directly generated plan (what-if scenario plans are
excluded, matching GET /planning/latest).

Definitions (same as app/optimization/planning_model.py):
- machine utilization  = planned units / available units over the horizon
  (per machine; stored in the plan's ``notes`` JSON as
  ``machine_utilization_by_machine`` when the plan is generated).
- worker utilization   = regular (non-overtime) hours assigned /
  (shift_hours x availability_factor x horizon days).
- worker current_hours / overtime_hours = assigned hours in the plan,
  normalised to a 7-day week so they compare with ``max_hours_per_week``.
"""
import json
from typing import Dict, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.optimization_run import OptimizationRun
from app.models.production_plan import ProductionPlan
from app.models.workforce_assignment import WorkforceAssignment


async def latest_baseline_plan(db: AsyncSession) -> Optional[ProductionPlan]:
    stmt = (
        select(ProductionPlan)
        .outerjoin(OptimizationRun, ProductionPlan.optimization_run_id == OptimizationRun.id)
        .where(OptimizationRun.scenario_id.is_(None))
        .order_by(ProductionPlan.created_at.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


def plan_horizon_days(plan: ProductionPlan) -> int:
    return max(1, (plan.end_date - plan.start_date).days + 1)


def machine_utilization_by_machine(plan: Optional[ProductionPlan]) -> Dict[str, float]:
    if not plan or not plan.notes:
        return {}
    try:
        notes = json.loads(plan.notes)
    except (TypeError, ValueError):
        return {}
    data = notes.get("machine_utilization_by_machine") or {}
    return {str(k): float(v) for k, v in data.items()}


async def worker_metrics(
    db: AsyncSession, plan: Optional[ProductionPlan], availability: Dict[str, float]
) -> Dict[str, Dict[str, float]]:
    """Per-worker hours and utilization in ``plan``.

    ``availability`` maps worker_id -> availability_factor (0-1); workers that
    have no assignment in the plan get zeros.
    """
    if not plan:
        return {}
    rows = (await db.execute(
        select(
            WorkforceAssignment.worker_id,
            func.sum(WorkforceAssignment.assigned_hours),
            func.sum(WorkforceAssignment.overtime_hours),
        )
        .where(WorkforceAssignment.production_plan_id == plan.id)
        .group_by(WorkforceAssignment.worker_id)
    )).all()
    days = plan_horizon_days(plan)
    week_scale = 7.0 / days
    metrics: Dict[str, Dict[str, float]] = {}
    for worker_id, hours, overtime in rows:
        hours = float(hours or 0.0)
        overtime = float(overtime or 0.0)
        factor = min(max(float(availability.get(worker_id, 1.0) or 0.0), 0.0), 1.0)
        capacity = settings.PLANNING_SHIFT_HOURS * factor * days
        metrics[worker_id] = {
            "weekly_hours": hours * week_scale,
            "weekly_overtime": overtime * week_scale,
            "utilization": round(100.0 * (hours - overtime) / capacity, 2) if capacity > 0 else 0.0,
        }
    return metrics
