from datetime import datetime, timedelta
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings, reference_date
from app.core.database import get_db
from app.models.order import Order
from app.models.worker import Worker
from app.models.workforce_assignment import WorkforceAssignment
from app.optimization.production_optimizer import OPEN_ORDER_STATUSES
from app.models.production_plan import ProductionPlan, PlanStatus
from app.models.production_plan_item import ProductionPlanItem
from app.models.optimization_run import OptimizationRun
from app.optimization.production_optimizer import ProductionOptimizer
from app.schemas.planning import (
    PlanningRequest, PlanningResponse, PlanListResponse, PlanItemResponse, PlanningDefaults, WorkerPlanSummary,
)

router = APIRouter()

# Failure messages that describe a problem with the request/data rather than the server.
_CLIENT_ERRORS = (
    "No open orders",
    "No available machines",
    "Planning horizon is limited",
    "end_date must be",
)


def _baseline_plans():
    """Plans generated directly (what-if scenario runs also persist plans; those
    are reachable by plan_id but are excluded from the list and "latest")."""
    return select(ProductionPlan).outerjoin(
        OptimizationRun, ProductionPlan.optimization_run_id == OptimizationRun.id
    ).where(OptimizationRun.scenario_id.is_(None))


def _plan_response(
    plan: ProductionPlan,
    items: Optional[List[PlanItemResponse]] = None,
    worker_summary: Optional[List[WorkerPlanSummary]] = None,
) -> PlanningResponse:
    response = PlanningResponse.model_validate(plan, from_attributes=True)
    response.items = items or []
    response.worker_summary = worker_summary or []
    return response


async def _worker_summary(plan: ProductionPlan, db: AsyncSession) -> List[WorkerPlanSummary]:
    """Hours, overtime and regular-hour utilization per worker in ``plan``."""
    rows = (await db.execute(
        select(
            WorkforceAssignment.worker_id,
            Worker.name,
            Worker.availability_factor,
            func.sum(WorkforceAssignment.assigned_hours),
            func.sum(WorkforceAssignment.overtime_hours),
        )
        .join(Worker, Worker.worker_id == WorkforceAssignment.worker_id)
        .where(WorkforceAssignment.production_plan_id == plan.id)
        .group_by(WorkforceAssignment.worker_id, Worker.name, Worker.availability_factor)
    )).all()
    days = max(1, (plan.end_date - plan.start_date).days + 1)
    summary = []
    for worker_id, name, factor, hours, overtime in rows:
        hours = float(hours or 0)
        overtime = float(overtime or 0)
        factor = min(max(float(factor if factor is not None else 1.0), 0.0), 1.0)
        capacity = settings.PLANNING_SHIFT_HOURS * factor * days
        summary.append(WorkerPlanSummary(
            worker_id=worker_id,
            worker_name=name,
            hours=round(hours, 2),
            overtime_hours=round(overtime, 2),
            utilization=round(100.0 * (hours - overtime) / capacity, 2) if capacity > 0 else 0.0,
        ))
    summary.sort(key=lambda w: w.hours, reverse=True)
    return summary


async def _full_plan_response(plan: ProductionPlan, db: AsyncSession) -> PlanningResponse:
    return _plan_response(plan, await _get_plan_items(plan.id, db), await _worker_summary(plan, db))


@router.get("", response_model=PlanListResponse)
async def get_plans(
    status: Optional[PlanStatus] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """Get production plans (summary only; items are returned by the single-plan endpoints)."""
    stmt = _baseline_plans()
    if status:
        stmt = stmt.where(ProductionPlan.status == status)
    stmt = stmt.order_by(ProductionPlan.created_at.desc()).limit(limit)

    result = await db.execute(stmt)
    plans = result.scalars().all()

    return PlanListResponse(
        plans=[_plan_response(p) for p in plans],
        total=len(plans)
    )


@router.get("/defaults", response_model=PlanningDefaults)
async def get_planning_defaults(db: AsyncSession = Depends(get_db)):
    """Suggested Generate Plan window: starts at the planning reference date
    (PLANNING_REFERENCE_DATE, else today) and spans 7 days. If no open order is
    due on/after that date, it starts at the earliest open-order due date
    instead, so the plan is never empty just because the dataset is historical."""
    ref = reference_date()
    span = min(7, settings.PLANNING_MAX_HORIZON_DAYS)
    open_from, open_to, open_count = (await db.execute(
        select(func.min(Order.due_date), func.max(Order.due_date), func.count(Order.id))
        .where(Order.status.in_(OPEN_ORDER_STATUSES), Order.due_date >= ref)
    )).one()
    in_window = (await db.execute(
        select(func.count(Order.id)).where(
            Order.status.in_(OPEN_ORDER_STATUSES),
            Order.due_date >= ref,
            Order.due_date <= ref + timedelta(days=span - 1),
        )
    )).scalar() or 0
    start = ref if in_window or open_from is None else open_from
    data_start, data_end = (await db.execute(select(func.min(Order.date), func.max(Order.date)))).one()
    return PlanningDefaults(
        reference_date=ref,
        reference_date_source="PLANNING_REFERENCE_DATE" if settings.PLANNING_REFERENCE_DATE else "today",
        suggested_start=start,
        suggested_end=start + timedelta(days=span - 1),
        max_horizon_days=settings.PLANNING_MAX_HORIZON_DAYS,
        open_orders=int(open_count or 0),
        open_orders_due_from=open_from,
        open_orders_due_to=open_to,
        data_start=data_start,
        data_end=data_end,
    )


@router.get("/latest", response_model=PlanningResponse)
async def get_latest_plan(db: AsyncSession = Depends(get_db)):
    """Get the latest production plan"""
    stmt = _baseline_plans().order_by(ProductionPlan.created_at.desc()).limit(1)
    result = await db.execute(stmt)
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=404, detail="No production plan found")

    return await _full_plan_response(plan, db)


@router.get("/{plan_id}", response_model=PlanningResponse)
async def get_plan(plan_id: str, db: AsyncSession = Depends(get_db)):
    """Get production plan by ID"""
    stmt = select(ProductionPlan).where(ProductionPlan.plan_id == plan_id)
    result = await db.execute(stmt)
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    return await _full_plan_response(plan, db)


@router.post("/generate", response_model=PlanningResponse)
async def generate_plan(
    request: PlanningRequest,
    db: AsyncSession = Depends(get_db)
):
    """Generate optimized production plan"""
    optimizer = ProductionOptimizer(db)

    plan, opt_run = await optimizer.generate_plan(
        start_date=request.start_date,
        end_date=request.end_date,
        product_ids=request.product_ids,
        machine_ids=request.machine_ids,
        max_overtime_hours=request.max_overtime_hours if request.max_overtime_hours is not None else 8,
        priority_weights=request.priority_weights
    )

    if not plan:
        message = opt_run.error_message or "Optimization failed"
        status_code = 422 if message.startswith(_CLIENT_ERRORS) else 500
        raise HTTPException(status_code=status_code, detail=message)

    return await _full_plan_response(plan, db)


@router.post("/{plan_id}/approve")
async def approve_plan(plan_id: str, db: AsyncSession = Depends(get_db)):
    """Approve a production plan"""
    stmt = select(ProductionPlan).where(ProductionPlan.plan_id == plan_id)
    result = await db.execute(stmt)
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan.status = PlanStatus.APPROVED
    plan.approved_by = "admin@smartplan.ai"  # Would get from auth
    plan.approved_at = datetime.utcnow()

    await db.commit()

    return {"message": "Plan approved successfully", "plan_id": plan_id}


async def _get_plan_items(plan_id: uuid.UUID, db: AsyncSession) -> List[PlanItemResponse]:
    """Return the persisted solver output for a plan (one item per order)."""
    stmt = select(ProductionPlanItem).where(
        ProductionPlanItem.production_plan_id == plan_id
    ).order_by(ProductionPlanItem.due_date, ProductionPlanItem.order_id)
    result = await db.execute(stmt)
    return [PlanItemResponse.model_validate(item, from_attributes=True) for item in result.scalars().all()]
