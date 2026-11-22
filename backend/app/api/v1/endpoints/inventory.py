from datetime import timedelta
from typing import Dict, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.config import reference_date
from app.core.database import get_db
from app.models.demand_history import DemandHistory
from app.models.inventory import Inventory
from app.models.product import Product
from app.schemas.inventory import InventoryListResponse, InventoryResponse, InventoryStatus

router = APIRouter()

# Average daily demand is taken over this many calendar days.
COVERAGE_WINDOW_DAYS = 28


async def _avg_daily_demand(db: AsyncSession, product_id: Optional[str] = None) -> Dict[str, float]:
    """Mean daily demand per product over the last COVERAGE_WINDOW_DAYS calendar
    days of history ending at the reference date (or at the product's last
    recorded day if its history ends earlier). Days without orders count as 0."""
    ref = reference_date()
    stmt = select(DemandHistory.product_id, func.max(DemandHistory.date)).where(DemandHistory.date <= ref)
    if product_id:
        stmt = stmt.where(DemandHistory.product_id == product_id)
    ends = {pid: end for pid, end in (await db.execute(stmt.group_by(DemandHistory.product_id))).all()}
    averages: Dict[str, float] = {}
    for pid, end in ends.items():
        start = end - timedelta(days=COVERAGE_WINDOW_DAYS - 1)
        total = (await db.execute(
            select(func.sum(DemandHistory.demand)).where(
                DemandHistory.product_id == pid,
                DemandHistory.date >= start,
                DemandHistory.date <= end,
            )
        )).scalar() or 0
        averages[pid] = float(total) / COVERAGE_WINDOW_DAYS
    return averages


def _coverage_days(current_level: int, avg_daily: Optional[float]) -> float:
    """Days of demand the current stock covers: units / average daily demand."""
    if not avg_daily or avg_daily <= 0:
        return 0.0
    return current_level / avg_daily


@router.get("", response_model=InventoryListResponse)
async def get_inventory(db: AsyncSession = Depends(get_db)):
    """Get all inventory levels"""
    stmt = select(Inventory, Product.name, Product.category).join(
        Product, Inventory.product_id == Product.product_id
    ).order_by(Product.name)
    
    result = await db.execute(stmt)
    data = result.all()
    
    avg_daily = await _avg_daily_demand(db)
    inventory_responses = []
    for inv, product_name, category in data:
        coverage_days = _coverage_days(inv.current_level, avg_daily.get(inv.product_id))
        
        # Determine status
        if inv.current_level > inv.safety_stock * 1.5:
            status = InventoryStatus.HEALTHY
        elif inv.current_level > inv.safety_stock:
            status = InventoryStatus.LOW
        else:
            status = InventoryStatus.CRITICAL
        
        inventory_responses.append(InventoryResponse(
            product_id=inv.product_id,
            product_name=product_name,
            category=category,
            current_level=inv.current_level,
            safety_stock=inv.safety_stock,
            reorder_point=inv.reorder_point,
            max_stock=inv.max_stock,
            unit_cost=inv.unit_cost,
            coverage_days=round(coverage_days, 1),
            status=status,
            last_updated=inv.last_updated
        ))
    
    return InventoryListResponse(
        inventory=inventory_responses,
        total=len(inventory_responses)
    )


@router.get("/{product_id}", response_model=InventoryResponse)
async def get_inventory_item(product_id: str, db: AsyncSession = Depends(get_db)):
    """Get inventory for specific product"""
    stmt = select(Inventory, Product.name, Product.category).join(
        Product, Inventory.product_id == Product.product_id
    ).where(Inventory.product_id == product_id)
    
    result = await db.execute(stmt)
    data = result.first()
    
    if not data:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Inventory not found")
    
    inv, product_name, category = data

    avg_daily = await _avg_daily_demand(db, product_id)
    coverage_days = _coverage_days(inv.current_level, avg_daily.get(product_id))
    
    if inv.current_level > inv.safety_stock * 1.5:
        status = InventoryStatus.HEALTHY
    elif inv.current_level > inv.safety_stock:
        status = InventoryStatus.LOW
    else:
        status = InventoryStatus.CRITICAL
    
    return InventoryResponse(
        product_id=inv.product_id,
        product_name=product_name,
        category=category,
        current_level=inv.current_level,
        safety_stock=inv.safety_stock,
        reorder_point=inv.reorder_point,
        max_stock=inv.max_stock,
        unit_cost=inv.unit_cost,
        coverage_days=round(coverage_days, 1),
        status=status,
        last_updated=inv.last_updated
    )