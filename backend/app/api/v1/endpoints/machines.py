from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.machine import Machine
from app.schemas.machine import MachineListResponse, MachineResponse
from app.services.plan_metrics import latest_baseline_plan, machine_utilization_by_machine

router = APIRouter()


@router.get("", response_model=MachineListResponse)
async def get_machines(db: AsyncSession = Depends(get_db)):
    """Get all machines"""
    stmt = select(Machine).order_by(Machine.name)
    result = await db.execute(stmt)
    machines = result.scalars().all()

    # Utilization is taken from the latest baseline production plan
    # (planned / available units over the plan horizon); 0 if no plan.
    plan = await latest_baseline_plan(db)
    utilization = machine_utilization_by_machine(plan)
    responses = []
    for m in machines:
        response = MachineResponse.model_validate(m, from_attributes=True)
        response.utilization = float(utilization.get(m.machine_id, 0.0))
        responses.append(response)

    return MachineListResponse(
        machines=responses,
        total=len(machines),
        plan_id=plan.plan_id if plan else None,
    )


@router.get("/{machine_id}", response_model=MachineResponse)
async def get_machine(machine_id: str, db: AsyncSession = Depends(get_db)):
    """Get machine by ID"""
    stmt = select(Machine).where(Machine.machine_id == machine_id)
    result = await db.execute(stmt)
    machine = result.scalar_one_or_none()
    
    if not machine:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Machine not found")
    
    response = MachineResponse.model_validate(machine, from_attributes=True)
    plan = await latest_baseline_plan(db)
    response.utilization = float(machine_utilization_by_machine(plan).get(machine.machine_id, 0.0))
    return response