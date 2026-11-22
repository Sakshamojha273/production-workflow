"""Downloadable CSV reports built from the live database.

GET /api/reports              -> catalogue of reports with current row counts
GET /api/reports/{report_id}  -> the CSV file (Content-Disposition: attachment)

Reports: plan-summary, plan-items, orders, inventory, workforce-assignments.
Plan reports use the latest baseline plan (the one Production Planning shows).
"""
import csv
import io
from datetime import date
from typing import Callable, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.inventory import Inventory
from app.models.machine import Machine
from app.models.order import Order
from app.models.product import Product
from app.models.worker import Worker
from app.models.workforce_assignment import WorkforceAssignment
from app.services.plan_metrics import latest_baseline_plan, machine_utilization_by_machine

router = APIRouter()

Rows = Tuple[List[str], List[list]]


def _val(v):
    return getattr(v, "value", v)


async def _plan_summary(db: AsyncSession, start: Optional[date], end: Optional[date]) -> Rows:
    plan = await latest_baseline_plan(db)
    header = ["Metric", "Value"]
    if not plan:
        return header, []
    rows = [
        ["Plan ID", plan.plan_id],
        ["Start date", plan.start_date.isoformat()],
        ["End date", plan.end_date.isoformat()],
        ["Status", _val(plan.status)],
        ["Total demand (units)", plan.total_demand],
        ["Planned production (units)", plan.total_production],
        ["Total cost", round(float(plan.total_cost or 0), 2)],
        ["Overtime hours", round(float(plan.total_overtime or 0), 2)],
        ["Late orders", plan.late_orders],
        ["Machine utilization %", round(float(plan.machine_utilization or 0), 2)],
        ["Workforce utilization %", round(float(plan.workforce_utilization or 0), 2)],
        ["Fulfillment rate %", round(float(plan.fulfillment_rate or 0), 2)],
    ]
    for machine_id, util in sorted(machine_utilization_by_machine(plan).items()):
        rows.append([f"Machine utilization % ({machine_id})", round(float(util), 2)])
    return header, rows


async def _plan_items(db: AsyncSession, start: Optional[date], end: Optional[date]) -> Rows:
    from app.api.v1.endpoints.planning import _get_plan_items  # avoid import cycle

    header = ["Plan ID", "Order ID", "Product", "Demand", "Planned", "From inventory", "Backlog",
              "Machine", "Worker", "Shift", "Due date", "Completion date", "Priority", "Status", "Cost"]
    plan = await latest_baseline_plan(db)
    if not plan:
        return header, []
    rows = [[plan.plan_id, i.order_id, i.product_name, i.demand, i.planned_production, i.from_inventory,
             i.backlog, i.machine_name, i.worker_name or "Unassigned", i.shift or "", i.due_date,
             i.completion_date or "", i.priority, i.status, round(i.cost, 2)]
            for i in await _get_plan_items(plan.id, db)]
    return header, rows


async def _orders(db: AsyncSession, start: Optional[date], end: Optional[date]) -> Rows:
    stmt = (
        select(Order, Product.name, Machine.name)
        .outerjoin(Product, Product.product_id == Order.product_id)
        .outerjoin(Machine, Machine.machine_id == Order.machine_id)
        .order_by(Order.date, Order.order_id)
    )
    if start:
        stmt = stmt.where(Order.date >= start)
    if end:
        stmt = stmt.where(Order.date <= end)
    header = ["Order ID", "Date", "Product ID", "Product", "Demand", "Production", "Machine",
              "Worker ID", "Shift", "Due date", "Priority", "Status", "Overtime hours", "Cost"]
    rows = [[o.order_id, o.date, o.product_id, pname, o.demand, o.production_quantity, mname,
             o.worker_id, o.shift, o.due_date, _val(o.priority), _val(o.status),
             o.overtime_hours, round(float(o.production_cost or 0), 2)]
            for o, pname, mname in (await db.execute(stmt)).all()]
    return header, rows


async def _inventory(db: AsyncSession, start: Optional[date], end: Optional[date]) -> Rows:
    from app.api.v1.endpoints.inventory import get_inventory  # same numbers as the Inventory page

    header = ["Product ID", "Product", "Current level", "Safety stock", "Reorder point", "Unit cost",
              "Stock value", "Coverage days", "Status"]
    listing = await get_inventory(db)
    rows = [[i.product_id, i.product_name, i.current_level, i.safety_stock, i.reorder_point,
             round(float(i.unit_cost or 0), 2), round(float(i.unit_cost or 0) * i.current_level, 2),
             i.coverage_days, _val(i.status)] for i in listing.inventory]
    return header, rows


async def _workforce(db: AsyncSession, start: Optional[date], end: Optional[date]) -> Rows:
    header = ["Plan ID", "Date", "Worker ID", "Worker", "Machine", "Product", "Shift",
              "Assigned hours", "Overtime hours", "Skill match", "Status"]
    plan = await latest_baseline_plan(db)
    if not plan:
        return header, []
    stmt = (
        select(WorkforceAssignment, Worker.name, Machine.name, Product.name)
        .join(Worker, Worker.worker_id == WorkforceAssignment.worker_id)
        .join(Machine, Machine.machine_id == WorkforceAssignment.machine_id)
        .join(Product, Product.product_id == WorkforceAssignment.product_id)
        .where(WorkforceAssignment.production_plan_id == plan.id)
        .order_by(WorkforceAssignment.date, Worker.name)
    )
    rows = [[plan.plan_id, a.date, a.worker_id, wname, mname, pname, a.shift,
             round(float(a.assigned_hours or 0), 2), round(float(a.overtime_hours or 0), 2),
             round(float(a.skill_match or 0), 2), _val(a.status)]
            for a, wname, mname, pname in (await db.execute(stmt)).all()]
    return header, rows


REPORTS: Dict[str, Dict] = {
    "plan-summary": {"name": "Plan summary", "description": "KPIs of the latest production plan, incl. utilization per machine", "build": _plan_summary},
    "plan-items": {"name": "Plan items", "description": "Every order in the latest plan: quantity, machine, worker, shift, backlog, cost", "build": _plan_items},
    "orders": {"name": "Orders", "description": "All imported orders (optional date filter on order date)", "build": _orders, "date_filter": True},
    "inventory": {"name": "Inventory", "description": "Stock level, safety stock, reorder point, value and days of cover", "build": _inventory},
    "workforce-assignments": {"name": "Workforce assignments", "description": "Worker-to-machine assignments of the latest plan with hours and overtime", "build": _workforce},
}


@router.get("")
async def list_reports(db: AsyncSession = Depends(get_db)):
    plan = await latest_baseline_plan(db)
    counts = {
        "orders": (await db.execute(select(func.count(Order.id)))).scalar() or 0,
        "inventory": (await db.execute(select(func.count(Inventory.id)))).scalar() or 0,
    }
    return {
        "plan_id": plan.plan_id if plan else None,
        "plan_window": [plan.start_date, plan.end_date] if plan else None,
        "reports": [
            {
                "id": rid,
                "name": meta["name"],
                "description": meta["description"],
                "format": "csv",
                "date_filter": bool(meta.get("date_filter")),
                "rows": counts.get(rid),
                "available": (counts[rid] > 0) if rid in counts else plan is not None,
            }
            for rid, meta in REPORTS.items()
        ],
    }


@router.get("/{report_id}")
async def download_report(
    report_id: str,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    meta = REPORTS.get(report_id.removesuffix(".csv"))
    if not meta:
        raise HTTPException(status_code=404, detail=f"Unknown report '{report_id}'. Available: {', '.join(REPORTS)}")
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date")
    header, rows = await meta["build"](db, start_date, end_date)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows([["" if v is None else (v.isoformat() if isinstance(v, date) else v) for v in r] for r in rows])
    rid = report_id.removesuffix(".csv")
    filename = f"{rid}_{date.today().isoformat()}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "X-Row-Count": str(len(rows))},
    )
