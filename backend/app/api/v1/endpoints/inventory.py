from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.models.inventory import Inventory
from app.models.product import Product
from app.schemas.inventory import InventoryListResponse, InventoryResponse, InventoryStatus

router = APIRouter()


@router.get("", response_model=InventoryListResponse)
async def get_inventory(db: AsyncSession = Depends(get_db)):
    """Get all inventory levels"""
    stmt = select(Inventory, Product.name, Product.category).join(
        Product, Inventory.product_id == Product.product_id
    ).order_by(Product.name)
    
    result = await db.execute(stmt)
    data = result.all()
    
    inventory_responses = []
    for inv, product_name, category in data:
        # Calculate coverage days (simplified)
        coverage_days = inv.current_level / max(1, inv.safety_stock / 7)  # Assume safety stock covers 7 days
        
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
    
    coverage_days = inv.current_level / max(1, inv.safety_stock / 7)
    
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