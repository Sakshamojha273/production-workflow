from datetime import datetime
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.production_plan import ProductionPlan, PlanStatus
from app.models.production_plan_item import ProductionPlanItem
from app.models.optimization_run import OptimizationRun
from app.optimization.production_optimizer import ProductionOptimizer
from app.schemas.planning import PlanningRequest, PlanningResponse, PlanListResponse, PlanItemResponse

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


def _plan_response(plan: ProductionPlan, items: Optional[List[PlanItemResponse]] = None) -> PlanningResponse:
    response = PlanningResponse.model_validate(plan, from_attributes=True)
    response.items = items or []
    return response


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


@router.get("/latest", response_model=PlanningResponse)
async def get_latest_plan(db: AsyncSession = Depends(get_db)):
    """Get the latest production plan"""
    stmt = _baseline_plans().order_by(ProductionPlan.created_at.desc()).limit(1)
    result = await db.execute(stmt)
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=404, detail="No production plan found")

    return _plan_response(plan, await _get_plan_items(plan.id, db))


@router.get("/{plan_id}", response_model=PlanningResponse)
async def get_plan(plan_id: str, db: AsyncSession = Depends(get_db)):
    """Get production plan by ID"""
    stmt = select(ProductionPlan).where(ProductionPlan.plan_id == plan_id)
    result = await db.execute(stmt)
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    return _plan_response(plan, await _get_plan_items(plan.id, db))


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

    return _plan_response(plan, await _get_plan_items(plan.id, db))


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
