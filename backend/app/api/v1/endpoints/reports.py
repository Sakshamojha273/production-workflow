from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
from datetime import date
import uuid
import pandas as pd
import io

from app.core.database import get_db
from app.models.order import Order
from app.models.production_plan import ProductionPlan
from app.models.workforce_assignment import WorkforceAssignment
from app.models.worker import Worker
from app.models.machine import Machine
from app.models.maintenance import Maintenance
from app.models.forecast import Forecast
from app.models.optimization_run import OptimizationRun
from app.schemas.report import ReportRequest, ReportResponse, ReportType, ReportFormat

router = APIRouter()


@router.post("", response_model=ReportResponse)
async def generate_report(
    request: ReportRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Generate a report"""
    report_id = f"RPT-{uuid.uuid4().hex[:8].upper()}"
    
    # Generate report in background
    background_tasks.add_task(
        _generate_report_file,
        report_id,
        request,
        db
    )
    
    return ReportResponse(
        report_id=report_id,
        report_type=request.report_type,
        format=request.format,
        status="Generating",
        created_at=datetime.utcnow()
    )


@router.get("", response_model=List[ReportResponse])
async def get_reports(
    report_type: Optional[ReportType] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """Get list of generated reports"""
    # In a real app, this would query a reports table
    # For now, return mock data
    return []


async def _generate_report_file(
    report_id: str,
    request: ReportRequest,
    db: AsyncSession
):
    """Background task to generate report file"""
    try:
        if request.report_type == ReportType.PRODUCTION:
            data = await _get_production_report_data(request.start_date, request.end_date, db)
        elif request.report_type == ReportType.WORKFORCE:
            data = await _get_workforce_report_data(request.start_date, request.end_date, db)
        elif request.report_type == ReportType.MACHINE_UTILIZATION:
            data = await _get_machine_utilization_report_data(request.start_date, request.end_date, db)
        elif request.report_type == ReportType.MAINTENANCE:
            data = await _get_maintenance_report_data(request.start_date, request.end_date, db)
        elif request.report_type == ReportType.DEMAND_FORECAST:
            data = await _get_forecast_report_data(request.start_date, request.end_date, db)
        elif request.report_type == ReportType.OPTIMIZATION:
            data = await _get_optimization_report_data(request.start_date, request.end_date, db)
        elif request.report_type == ReportType.COST:
            data = await _get_cost_report_data(request.start_date, request.end_date, db)
        else:
            data = []
        
        df = pd.DataFrame(data)
        
        if request.format == ReportFormat.CSV:
            output = io.StringIO()
            df.to_csv(output, index=False)
            content = output.getvalue()
            # Save to file storage (simplified)
        else:
            # PDF generation would go here
            pass
        
    except Exception as e:
        # Log error
        pass


async def _get_production_report_data(start: date, end: date, db: AsyncSession) -> List[dict]:
    stmt = select(Order).where(
        Order.date >= start,
        Order.date <= end
    )
    result = await db.execute(stmt)
    orders = result.scalars().all()
    
    return [{
        "Order ID": o.order_id,
        "Date": o.date,
        "Product": o.product_name,
        "Demand": o.demand,
        "Production": o.production_quantity,
        "Machine": o.machine_name,
        "Due Date": o.due_date,
        "Priority": o.priority.value,
        "Status": o.status.value,
        "Cost": o.production_cost
    } for o in orders]


async def _get_workforce_report_data(start: date, end: date, db: AsyncSession) -> List[dict]:
    stmt = select(WorkforceAssignment, Worker.name, Machine.name, Product.name).join(
        Worker, WorkforceAssignment.worker_id == Worker.worker_id
    ).join(
        Machine, WorkforceAssignment.machine_id == Machine.machine_id
    ).join(
        Product, WorkforceAssignment.product_id == Product.product_id
    ).where(
        WorkforceAssignment.date >= start,
        WorkforceAssignment.date <= end
    )
    result = await db.execute(stmt)
    data = result.all()
    
    return [{
        "Date": a.date,
        "Worker": w_name,
        "Machine": m_name,
        "Product": p_name,
        "Shift": a.shift,
        "Hours": a.assigned_hours,
        "Overtime": a.overtime_hours,
        "Skill Match": a.skill_match
    } for a, w_name, m_name, p_name in data]


async def _get_machine_utilization_report_data(start: date, end: date, db: AsyncSession) -> List[dict]:
    stmt = select(Machine).where(Machine.availability == 1)
    result = await db.execute(stmt)
    machines = result.scalars().all()
    
    return [{
        "Machine ID": m.machine_id,
        "Name": m.name,
        "Type": m.type,
        "Capacity": m.capacity,
        "Utilization %": m.utilization,
        "Status": m.status.value,
        "Risk Score": m.risk_score
    } for m in machines]


async def _get_maintenance_report_data(start: date, end: date, db: AsyncSession) -> List[dict]:
    stmt = select(Maintenance).where(
        Maintenance.start_date >= start,
        Maintenance.start_date <= end
    )
    result = await db.execute(stmt)
    maintenance = result.scalars().all()
    
    return [{
        "Maintenance ID": m.maintenance_id,
        "Machine": m.machine_id,
        "Type": m.type.value,
        "Status": m.status.value,
        "Start": m.start_date,
        "End": m.end_date,
        "Reason": m.reason,
        "Cost": m.cost
    } for m in maintenance]


async def _get_forecast_report_data(start: date, end: date, db: AsyncSession) -> List[dict]:
    stmt = select(Forecast).where(
        Forecast.forecast_date >= start,
        Forecast.forecast_date <= end
    )
    result = await db.execute(stmt)
    forecasts = result.scalars().all()
    
    return [{
        "Product": f.product_id,
        "Forecast Date": f.forecast_date,
        "Horizon Days": f.forecast_horizon_days,
        "Predicted Demand": f.predicted_demand,
        "Lower Bound": f.lower_bound,
        "Upper Bound": f.upper_bound,
        "Model": f.model_used.value
    } for f in forecasts]


async def _get_optimization_report_data(start: date, end: date, db: AsyncSession) -> List[dict]:
    stmt = select(OptimizationRun).where(
        OptimizationRun.start_date >= start,
        OptimizationRun.start_date <= end
    )
    result = await db.execute(stmt)
    runs = result.scalars().all()
    
    return [{
        "Run ID": r.run_id,
        "Status": r.status.value,
        "Objective Value": r.objective_value,
        "Solve Time (s)": r.solve_time_seconds,
        "Total Cost": r.total_cost,
        "Total Overtime": r.total_overtime,
        "Late Orders": r.late_orders,
        "Machine Util %": r.machine_utilization,
        "Workforce Util %": r.workforce_utilization,
        "Fulfillment Rate %": r.fulfillment_rate
    } for r in runs]


async def _get_cost_report_data(start: date, end: date, db: AsyncSession) -> List[dict]:
    stmt = select(Order).where(
        Order.date >= start,
        Order.date <= end
    )
    result = await db.execute(stmt)
    orders = result.scalars().all()
    
    return [{
        "Order ID": o.order_id,
        "Product": o.product_name,
        "Production Qty": o.production_quantity,
        "Unit Cost": o.production_cost / max(1, o.production_quantity),
        "Total Cost": o.production_cost,
        "Overtime Cost": o.overtime_hours * 500,
        "Machine": o.machine_name
    } for o in orders]


from datetime import datetime