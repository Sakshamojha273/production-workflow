from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from datetime import date, timedelta

from app.core.database import get_db
from app.models.maintenance import Maintenance, MaintenanceType, MaintenanceStatus
from app.models.machine import Machine
from app.ml.machine_risk import MachineRiskAnalyzer

router = APIRouter()


@router.get("")
async def get_maintenance(
    machine_id: Optional[str] = None,
    status: Optional[MaintenanceStatus] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get maintenance records"""
    stmt = select(Maintenance, Machine.name).join(
        Machine, Maintenance.machine_id == Machine.machine_id
    )
    
    if machine_id:
        stmt = stmt.where(Maintenance.machine_id == machine_id)
    if status:
        stmt = stmt.where(Maintenance.status == status)
    if start_date:
        stmt = stmt.where(Maintenance.start_date >= start_date)
    if end_date:
        stmt = stmt.where(Maintenance.start_date <= end_date)
    
    stmt = stmt.order_by(Maintenance.start_date.desc())
    
    result = await db.execute(stmt)
    data = result.all()
    
    return [{
        "maintenance_id": m.maintenance_id,
        "machine_id": m.machine_id,
        "machine_name": machine_name,
        "type": m.type.value,
        "status": m.status.value,
        "start_date": m.start_date.isoformat(),
        "end_date": m.end_date.isoformat(),
        "description": m.description,
        "reason": m.reason,
        "cost": m.cost,
        "performed_by": m.performed_by
    } for m, machine_name in data]


@router.get("/timeline")
async def get_maintenance_timeline(
    days: int = 30,
    db: AsyncSession = Depends(get_db)
):
    """Get upcoming maintenance timeline"""
    analyzer = MachineRiskAnalyzer(db)
    return await analyzer.get_maintenance_timeline(days)


@router.get("/machine-risk")
async def get_machine_risk(
    machine_ids: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get machine risk analysis"""
    analyzer = MachineRiskAnalyzer(db)
    
    ids = machine_ids.split(",") if machine_ids else None
    risks = await analyzer.analyze_machine_risk(ids)
    
    return risks


@router.get("/risk-distribution")
async def get_risk_distribution(db: AsyncSession = Depends(get_db)):
    """Get machine risk distribution"""
    analyzer = MachineRiskAnalyzer(db)
    return await analyzer.get_risk_distribution()