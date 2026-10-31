from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.machine import Machine
from app.schemas.machine import MachineListResponse, MachineResponse

router = APIRouter()


@router.get("", response_model=MachineListResponse)
async def get_machines(db: AsyncSession = Depends(get_db)):
    """Get all machines"""
    stmt = select(Machine).order_by(Machine.name)
    result = await db.execute(stmt)
    machines = result.scalars().all()
    
    return MachineListResponse(
        machines=[MachineResponse.from_orm(m) for m in machines],
        total=len(machines)
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
    
    return MachineResponse.from_orm(machine)