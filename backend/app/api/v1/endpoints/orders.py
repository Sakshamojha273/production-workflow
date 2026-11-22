from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import Optional, List
from datetime import date

from app.core.database import get_db
from app.models.order import Order, OrderPriority, OrderStatus
from app.models.product import Product
from app.models.machine import Machine
from app.models.worker import Worker
from app.schemas.order import OrderListResponse, OrderResponse, OrderFilter

router = APIRouter()


@router.get("", response_model=OrderListResponse)
async def get_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    product_id: Optional[str] = None,
    machine_id: Optional[str] = None,
    priority: Optional[OrderPriority] = None,
    status: Optional[OrderStatus] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get paginated orders with filters"""
    
    # Build query
    stmt = select(Order)
    
    if product_id:
        stmt = stmt.where(Order.product_id == product_id)
    if machine_id:
        stmt = stmt.where(Order.machine_id == machine_id)
    if priority:
        stmt = stmt.where(Order.priority == priority)
    if status:
        stmt = stmt.where(Order.status == status)
    if start_date:
        stmt = stmt.where(Order.date >= start_date)
    if end_date:
        stmt = stmt.where(Order.date <= end_date)
    if search:
        # Order has no product_name column; match the product's name through Product.
        pattern = f"%{search.strip()}%"
        matching_products = select(Product.product_id).where(Product.name.ilike(pattern))
        stmt = stmt.where(
            or_(
                Order.order_id.ilike(pattern),
                Order.product_id.in_(matching_products),
            )
        )
    
    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar()
    
    # Apply pagination and ordering
    stmt = stmt.order_by(Order.date.desc(), Order.priority.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(stmt)
    orders = result.scalars().all()
    
    # Get related data for response
    product_ids = list(set(o.product_id for o in orders))
    machine_ids = list(set(o.machine_id for o in orders))
    worker_ids = list(set(o.worker_id for o in orders))
    
    products = {}
    if product_ids:
        p_stmt = select(Product).where(Product.product_id.in_(product_ids))
        p_result = await db.execute(p_stmt)
        products = {p.product_id: p for p in p_result.scalars().all()}
    
    machines = {}
    if machine_ids:
        m_stmt = select(Machine).where(Machine.machine_id.in_(machine_ids))
        m_result = await db.execute(m_stmt)
        machines = {m.machine_id: m for m in m_result.scalars().all()}
    
    workers = {}
    if worker_ids:
        w_stmt = select(Worker).where(Worker.worker_id.in_(worker_ids))
        w_result = await db.execute(w_stmt)
        workers = {w.worker_id: w for w in w_result.scalars().all()}
    
    # Build response
    order_responses = []
    for order in orders:
        product = products.get(order.product_id)
        machine = machines.get(order.machine_id)
        worker = workers.get(order.worker_id)
        
        order_responses.append(OrderResponse(
            order_id=order.order_id,
            date=order.date,
            product_id=order.product_id,
            product_name=product.name if product else order.product_id,
            category=product.category if product else order.category,
            demand=order.demand,
            production_quantity=order.production_quantity,
            machine_id=order.machine_id,
            machine_name=machine.name if machine else order.machine_name,
            machine_type=machine.type if machine else order.machine_type,
            machine_capacity=machine.capacity if machine else order.machine_capacity,
            machine_availability=order.machine_availability,
            maintenance_status=order.maintenance_status,
            worker_id=order.worker_id,
            worker_name=worker.name if worker else order.worker_name,
            department=worker.department if worker else order.department,
            shift=order.shift,
            worker_availability=order.worker_availability,
            production_time_minutes=order.production_time_minutes,
            overtime_hours=order.overtime_hours,
            production_cost=order.production_cost,
            machine_vibration=order.machine_vibration,
            machine_temperature_c=order.machine_temperature_c,
            machine_risk_score=order.machine_risk_score,
            next_day_demand=order.next_day_demand,
            priority=order.priority,
            due_date=order.due_date,
            status=order.status,
            inventory_level=order.inventory_level,
            safety_stock=order.safety_stock
        ))
    
    return OrderListResponse(
        orders=order_responses,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    )


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(order_id: str, db: AsyncSession = Depends(get_db)):
    """Get single order by ID"""
    stmt = select(Order).where(Order.order_id == order_id)
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()
    
    if not order:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Get related data
    product = await db.execute(select(Product).where(Product.product_id == order.product_id))
    product = product.scalar_one_or_none()
    
    machine = await db.execute(select(Machine).where(Machine.machine_id == order.machine_id))
    machine = machine.scalar_one_or_none()
    
    worker = await db.execute(select(Worker).where(Worker.worker_id == order.worker_id))
    worker = worker.scalar_one_or_none()
    
    return OrderResponse(
        order_id=order.order_id,
        date=order.date,
        product_id=order.product_id,
        product_name=product.name if product else order.product_id,
        category=product.category if product else order.category,
        demand=order.demand,
        production_quantity=order.production_quantity,
        machine_id=order.machine_id,
        machine_name=machine.name if machine else order.machine_name,
        machine_type=machine.type if machine else order.machine_type,
        machine_capacity=machine.capacity if machine else order.machine_capacity,
        machine_availability=order.machine_availability,
        maintenance_status=order.maintenance_status,
        worker_id=order.worker_id,
        worker_name=worker.name if worker else order.worker_name,
        department=worker.department if worker else order.department,
        shift=order.shift,
        worker_availability=order.worker_availability,
        production_time_minutes=order.production_time_minutes,
        overtime_hours=order.overtime_hours,
        production_cost=order.production_cost,
        machine_vibration=order.machine_vibration,
        machine_temperature_c=order.machine_temperature_c,
        machine_risk_score=order.machine_risk_score,
        next_day_demand=order.next_day_demand,
        priority=order.priority,
        due_date=order.due_date,
        status=order.status,
        inventory_level=order.inventory_level,
        safety_stock=order.safety_stock
    )