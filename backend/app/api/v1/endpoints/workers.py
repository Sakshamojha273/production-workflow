from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.worker import Worker, WorkerSkill
from app.schemas.worker import WorkerListResponse, WorkerResponse, WorkerSkillResponse
from app.services.plan_metrics import latest_baseline_plan, worker_metrics


def _factor(worker: Worker) -> float:
    return worker.availability_factor if worker.availability_factor is not None else 1.0


def _plan_fields(worker: Worker, metrics: dict, has_plan: bool) -> dict:
    """current_hours / overtime_hours / utilization from the latest plan.

    Hours are the worker's assigned hours in the plan normalised to a 7-day
    week (comparable with max_hours_per_week). Without any plan the stored
    values are returned unchanged."""
    if not has_plan:
        return {"current_hours": worker.current_hours or 0, "overtime_hours": worker.overtime_hours or 0, "utilization": 0.0}
    m = metrics.get(worker.worker_id)
    if not m:
        return {"current_hours": 0, "overtime_hours": 0, "utilization": 0.0}
    return {
        "current_hours": int(round(m["weekly_hours"])),
        "overtime_hours": int(round(m["weekly_overtime"])),
        "utilization": m["utilization"],
    }

router = APIRouter()


@router.get("", response_model=WorkerListResponse)
async def get_workers(db: AsyncSession = Depends(get_db)):
    """Get all workers"""
    stmt = select(Worker).order_by(Worker.name)
    result = await db.execute(stmt)
    workers = result.scalars().all()
    
    # Get skills for each worker
    worker_ids = [w.worker_id for w in workers]
    skills = {}
    if worker_ids:
        s_stmt = select(WorkerSkill).where(WorkerSkill.worker_id.in_(worker_ids))
        s_result = await db.execute(s_stmt)
        for skill in s_result.scalars().all():
            if skill.worker_id not in skills:
                skills[skill.worker_id] = []
            skills[skill.worker_id].append(WorkerSkillResponse(
                machine_type=skill.machine_type,
                proficiency=skill.proficiency,
                certified=bool(skill.certified)
            ))
    
    plan = await latest_baseline_plan(db)
    metrics = await worker_metrics(db, plan, {w.worker_id: _factor(w) for w in workers})

    worker_responses = []
    for worker in workers:
        worker_responses.append(WorkerResponse(
            worker_id=worker.worker_id,
            name=worker.name,
            department=worker.department,
            shift=worker.shift,
            availability=worker.availability,
            availability_factor=worker.availability_factor if worker.availability_factor is not None else 1.0,
            max_hours_per_week=worker.max_hours_per_week,
            **_plan_fields(worker, metrics, plan is not None),
            skills=skills.get(worker.worker_id, []),
            created_at=worker.created_at,
            updated_at=worker.updated_at
        ))
    
    return WorkerListResponse(
        workers=worker_responses,
        total=len(worker_responses),
        plan_id=plan.plan_id if plan else None,
        workforce_utilization=float(plan.workforce_utilization or 0) if plan else 0.0,
    )


@router.get("/{worker_id}", response_model=WorkerResponse)
async def get_worker(worker_id: str, db: AsyncSession = Depends(get_db)):
    """Get worker by ID"""
    stmt = select(Worker).where(Worker.worker_id == worker_id)
    result = await db.execute(stmt)
    worker = result.scalar_one_or_none()
    
    if not worker:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Worker not found")
    
    # Get skills
    s_stmt = select(WorkerSkill).where(WorkerSkill.worker_id == worker_id)
    s_result = await db.execute(s_stmt)
    skills = [WorkerSkillResponse(
        machine_type=s.machine_type,
        proficiency=s.proficiency,
        certified=bool(s.certified)
    ) for s in s_result.scalars().all()]

    plan = await latest_baseline_plan(db)
    metrics = await worker_metrics(db, plan, {worker.worker_id: _factor(worker)})
    
    return WorkerResponse(
        worker_id=worker.worker_id,
        name=worker.name,
        department=worker.department,
        shift=worker.shift,
        availability=worker.availability,
        availability_factor=worker.availability_factor if worker.availability_factor is not None else 1.0,
        max_hours_per_week=worker.max_hours_per_week,
        **_plan_fields(worker, metrics, plan is not None),
        skills=skills,
        created_at=worker.created_at,
        updated_at=worker.updated_at
    )