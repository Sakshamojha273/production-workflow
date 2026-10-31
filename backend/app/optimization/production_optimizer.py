"""Production planning service: loads data, runs the CP-SAT model off the event
loop, and persists the plan, per-order plan items and workforce assignments.

The optimisation model itself lives in ``app.optimization.planning_model`` and
is DB-free so it can be unit-tested directly.
"""
import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.inventory import Inventory
from app.models.machine import Machine
from app.models.maintenance import Maintenance, MaintenanceStatus
from app.models.optimization_run import OptimizationRun, OptimizationStatus
from app.models.order import Order, OrderStatus
from app.models.product import Product
from app.models.production_plan import PlanStatus, ProductionPlan
from app.models.production_plan_item import ProductionPlanItem
from app.models.worker import Worker, WorkerAvailability, WorkerSkill
from app.models.workforce_assignment import AssignmentStatus, WorkforceAssignment
from app.optimization.demand_adjustment import apply_demand_change
from app.optimization.planning_model import (
    DEFAULT_PRIORITY_WEIGHTS,
    MachineInput,
    OrderInput,
    PlanningProblem,
    PlanningSolution,
    WorkerInput,
    solve_production_plan,
)

OPEN_ORDER_STATUSES = (OrderStatus.PENDING, OrderStatus.IN_PROGRESS, OrderStatus.DELAYED)


@dataclass
class ScenarioAdjustments:
    """What-if levers applied to the planning inputs (percentages)."""

    demand_change_pct: float = 0.0
    machine_availability_change_pct: float = 0.0
    worker_availability_change_pct: float = 0.0
    overtime_limit_change_pct: float = 0.0
    production_target_change_pct: float = 0.0
    inventory_change_pct: float = 0.0
    machine_failure_ids: List[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "demand_change_pct": self.demand_change_pct,
            "machine_availability_change_pct": self.machine_availability_change_pct,
            "worker_availability_change_pct": self.worker_availability_change_pct,
            "overtime_limit_change_pct": self.overtime_limit_change_pct,
            "production_target_change_pct": self.production_target_change_pct,
            "inventory_change_pct": self.inventory_change_pct,
            "machine_failure_ids": list(self.machine_failure_ids),
        }


def _pct(value: float, pct: float) -> float:
    return value * (1 + (pct or 0) / 100.0)


def _clamp01(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


def _enum_value(value) -> str:
    return getattr(value, "value", value)


class ProductionOptimizer:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_plan(
        self,
        start_date: date,
        end_date: date,
        product_ids: Optional[List[str]] = None,
        machine_ids: Optional[List[str]] = None,
        max_overtime_hours: int = 8,
        priority_weights: Optional[Dict[str, float]] = None,
        demand_change_pct: float = 0,
        adjustments: Optional[ScenarioAdjustments] = None,
        scenario_id: Optional[uuid.UUID] = None,
    ) -> Tuple[Optional[ProductionPlan], OptimizationRun]:
        """Generate an optimised production plan with CP-SAT."""
        adjustments = adjustments or ScenarioAdjustments(demand_change_pct=demand_change_pct)
        effective_overtime = max(0, int(round(_pct(max_overtime_hours, adjustments.overtime_limit_change_pct))))

        opt_run = OptimizationRun(
            run_id=f"OPT-{uuid.uuid4().hex[:8].upper()}",
            scenario_id=scenario_id,
            start_date=datetime.combine(start_date, datetime.min.time()),
            end_date=datetime.combine(end_date, datetime.min.time()),
            status=OptimizationStatus.RUNNING,
            parameters=json.dumps({
                "product_ids": product_ids,
                "machine_ids": machine_ids,
                "max_overtime_hours": max_overtime_hours,
                "priority_weights": priority_weights,
                "adjustments": adjustments.as_dict(),
            }),
        )
        self.db.add(opt_run)
        await self.db.commit()

        try:
            horizon_days = (end_date - start_date).days + 1
            if horizon_days < 1:
                return await self._fail(opt_run, "end_date must be on or after start_date")
            if horizon_days > settings.PLANNING_MAX_HORIZON_DAYS:
                return await self._fail(
                    opt_run, f"Planning horizon is limited to {settings.PLANNING_MAX_HORIZON_DAYS} days"
                )

            problem = await self._build_problem(
                start_date, end_date, product_ids, machine_ids, effective_overtime, priority_weights, adjustments
            )
            if not problem.orders:
                return await self._fail(opt_run, "No open orders are due in the selected planning window")
            if not problem.machines:
                return await self._fail(opt_run, "No available machines match the selection")

            # CP-SAT is CPU-bound and synchronous: keep it off the event loop.
            solution = await asyncio.to_thread(solve_production_plan, problem)

            opt_run.solve_time_seconds = solution.solve_seconds
            opt_run.num_variables = solution.num_variables
            opt_run.num_constraints = solution.num_constraints
            if not solution.feasible:
                return await self._fail(opt_run, f"Solver returned {solution.status}")

            plan = await self._persist(solution, problem, opt_run)

            opt_run.status = OptimizationStatus.COMPLETED
            opt_run.objective_value = solution.objective_value
            opt_run.total_cost = plan.total_cost
            opt_run.total_overtime = plan.total_overtime
            opt_run.late_orders = plan.late_orders
            opt_run.machine_utilization = plan.machine_utilization
            opt_run.workforce_utilization = plan.workforce_utilization
            opt_run.fulfillment_rate = plan.fulfillment_rate
            opt_run.completed_at = datetime.utcnow()
            await self.db.commit()
            return plan, opt_run
        except Exception as exc:  # keep the run record truthful
            await self.db.rollback()
            return await self._fail(opt_run, f"{type(exc).__name__}: {exc}")

    async def _fail(self, opt_run: OptimizationRun, message: str) -> Tuple[None, OptimizationRun]:
        opt_run.status = OptimizationStatus.FAILED
        opt_run.error_message = message
        opt_run.completed_at = datetime.utcnow()
        self.db.add(opt_run)
        await self.db.commit()
        await self.db.refresh(opt_run)
        return None, opt_run

    async def _build_problem(
        self,
        start_date: date,
        end_date: date,
        product_ids: Optional[List[str]],
        machine_ids: Optional[List[str]],
        max_overtime_hours: int,
        priority_weights: Optional[Dict[str, float]],
        adj: ScenarioAdjustments,
    ) -> PlanningProblem:
        # Open orders due inside the window.
        stmt = select(Order, Product.name, Product.category).join(
            Product, Order.product_id == Product.product_id
        ).where(
            Order.due_date >= start_date,
            Order.due_date <= end_date,
            Order.status.in_(OPEN_ORDER_STATUSES),
        )
        if product_ids:
            stmt = stmt.where(Order.product_id.in_(product_ids))
        stmt = stmt.order_by(Order.due_date, Order.order_id)
        order_rows = (await self.db.execute(stmt)).all()

        mstmt = select(Machine).where(Machine.availability == 1)
        if machine_ids:
            mstmt = mstmt.where(Machine.machine_id.in_(machine_ids))
        machines = list((await self.db.execute(mstmt)).scalars().all())

        maint_stmt = select(Maintenance.machine_id, Maintenance.start_date, Maintenance.end_date).where(
            Maintenance.start_date <= end_date,
            Maintenance.end_date >= start_date,
            Maintenance.status.in_([MaintenanceStatus.SCHEDULED, MaintenanceStatus.IN_PROGRESS]),
        )
        maintenance_days: Dict[str, set] = {}
        for machine_id, m_start, m_end in (await self.db.execute(maint_stmt)).all():
            day = max(m_start, start_date)
            while day <= min(m_end, end_date):
                maintenance_days.setdefault(machine_id, set()).add(day)
                day += timedelta(days=1)

        workers = list((await self.db.execute(
            select(Worker).where(Worker.availability == WorkerAvailability.AVAILABLE)
        )).scalars().all())
        skills: Dict[str, set] = {}
        for worker_id, machine_type in (await self.db.execute(
            select(WorkerSkill.worker_id, WorkerSkill.machine_type)
        )).all():
            skills.setdefault(worker_id, set()).add(machine_type)

        inventory = {
            inv.product_id: max(0, int(round(_pct(inv.current_level or 0, adj.inventory_change_pct))))
            for inv in (await self.db.execute(select(Inventory))).scalars().all()
        }

        failed = set(adj.machine_failure_ids or [])
        machine_inputs = [
            MachineInput(
                machine_id=m.machine_id,
                name=m.name,
                machine_type=m.type,
                capacity_per_hour=int(m.capacity or 0),
                availability_factor=0.0 if m.machine_id in failed else _clamp01(
                    _pct(m.availability_factor if m.availability_factor is not None else 1.0,
                         adj.machine_availability_change_pct)
                ),
                maintenance_days=maintenance_days.get(m.machine_id, set()),
            )
            for m in machines
        ]
        worker_inputs = [
            WorkerInput(
                worker_id=w.worker_id,
                name=w.name,
                shift=w.shift,
                skills=skills.get(w.worker_id) or {w.department},
                availability_factor=_clamp01(
                    _pct(w.availability_factor if w.availability_factor is not None else 1.0,
                         adj.worker_availability_change_pct)
                ),
            )
            for w in workers
        ]
        order_inputs = []
        for order, product_name, category in order_rows:
            target = apply_demand_change(order.demand, adj.demand_change_pct)
            target = apply_demand_change(target, adj.production_target_change_pct)
            unit_cost = (order.production_cost or 0.0) / max(1, order.production_quantity or order.demand or 1)
            order_inputs.append(OrderInput(
                order_id=order.order_id,
                product_id=order.product_id,
                product_name=product_name or order.product_id,
                category=category,
                demand=target,
                due_date=order.due_date,
                release_date=order.date or start_date,
                priority=_enum_value(order.priority) or "Medium",
                unit_cost=unit_cost,
                default_machine_id=order.machine_id,
            ))

        return PlanningProblem(
            start_date=start_date,
            end_date=end_date,
            orders=order_inputs,
            machines=machine_inputs,
            workers=worker_inputs,
            inventory=inventory,
            priority_weights=priority_weights or dict(DEFAULT_PRIORITY_WEIGHTS),
            shifts=tuple(settings.PLANNING_SHIFTS),
            shift_hours=settings.PLANNING_SHIFT_HOURS,
            maintenance_downtime_hours=settings.PLANNING_MAINTENANCE_DOWNTIME_HOURS,
            max_overtime_hours=max_overtime_hours,
            operators_per_machine=settings.PLANNING_OPERATORS_PER_MACHINE,
            time_limit_seconds=settings.PLANNING_SOLVER_TIME_LIMIT_SECONDS,
            num_workers=settings.PLANNING_SOLVER_WORKERS,
        )

    async def _persist(
        self, solution: PlanningSolution, problem: PlanningProblem, opt_run: OptimizationRun
    ) -> ProductionPlan:
        machine_names = {m.machine_id: m.name for m in problem.machines}
        worker_names = {w.worker_id: w.name for w in problem.workers}

        plan = ProductionPlan(
            plan_id=f"PLAN-{uuid.uuid4().hex[:8].upper()}",
            optimization_run_id=opt_run.id,
            start_date=problem.start_date,
            end_date=problem.end_date,
            total_demand=solution.total_demand,
            total_production=solution.total_production,
            total_cost=solution.total_cost,
            total_overtime=int(round(solution.total_overtime)),
            late_orders=solution.late_orders,
            machine_utilization=solution.machine_utilization,
            workforce_utilization=solution.workforce_utilization,
            fulfillment_rate=solution.fulfillment_rate,
            status=PlanStatus.GENERATED,
            notes=json.dumps({
                "solver_status": solution.status,
                "solve_seconds": solution.solve_seconds,
                "orders": len(solution.orders),
                "from_inventory": solution.total_from_inventory,
                "backlog_units": solution.total_backlog,
                "on_time_fulfillment_rate": solution.on_time_fulfillment_rate,
                "unstaffed_hours": solution.unstaffed_hours,
                "worker_assignment": "greedy post-solve heuristic",
            }),
        )
        self.db.add(plan)
        await self.db.flush()  # assigns plan.id

        # Main operator per order: the worker with most hours on it.
        hours_by_order_worker: Dict[Tuple[str, str], float] = {}
        shift_by_order_worker: Dict[Tuple[str, str], str] = {}
        for a in solution.assignments:
            key = (a.order_id, a.worker_id)
            hours_by_order_worker[key] = hours_by_order_worker.get(key, 0.0) + a.hours
            shift_by_order_worker.setdefault(key, a.shift)

        for result in solution.orders:
            candidates = [(h, wid) for (oid, wid), h in hours_by_order_worker.items() if oid == result.order.order_id]
            main_worker = max(candidates)[1] if candidates else None
            self.db.add(ProductionPlanItem(
                production_plan_id=plan.id,
                order_id=result.order.order_id,
                product_id=result.order.product_id,
                product_name=result.order.product_name,
                machine_id=result.primary_machine_id,
                machine_name=machine_names.get(result.primary_machine_id, ""),
                demand=result.order.demand,
                planned_production=result.produced,
                from_inventory=result.from_inventory,
                backlog=result.backlog,
                late_units=result.late_units,
                due_date=result.order.due_date,
                completion_date=result.completion_date,
                priority=result.order.priority,
                production_time_minutes=result.production_minutes,
                cost=result.cost,
                status=result.status,
                worker_id=main_worker,
                worker_name=worker_names.get(main_worker) if main_worker else None,
                shift=shift_by_order_worker.get((result.order.order_id, main_worker)) if main_worker else None,
                schedule=json.dumps([
                    {"date": e.date.isoformat(), "machine_id": e.machine_id, "quantity": e.quantity}
                    for e in result.schedule
                ]),
            ))

        for a in solution.assignments:
            self.db.add(WorkforceAssignment(
                production_plan_id=plan.id,
                worker_id=a.worker_id,
                machine_id=a.machine_id,
                product_id=a.product_id,
                date=a.date,
                shift=a.shift,
                assigned_hours=a.hours,
                overtime_hours=a.overtime_hours,
                skill_match=1.0,
                status=AssignmentStatus.ASSIGNED,
            ))
        await self.db.flush()
        return plan

    async def run_scenario(
        self,
        baseline_run_id: uuid.UUID,
        demand_change_pct: float = 0,
        machine_availability_change_pct: float = 0,
        worker_availability_change_pct: float = 0,
        overtime_limit_change_pct: float = 0,
        production_target_change_pct: float = 0,
        inventory_change_pct: float = 0,
        machine_failure_ids: Optional[List[str]] = None,
        scenario_id: Optional[uuid.UUID] = None,
    ) -> OptimizationRun:
        """Re-optimise the baseline window with the scenario levers applied to the inputs."""
        baseline_run = (await self.db.execute(
            select(OptimizationRun).where(OptimizationRun.id == baseline_run_id)
        )).scalar_one_or_none()
        if not baseline_run:
            raise ValueError("Baseline run not found")

        params = json.loads(baseline_run.parameters) if baseline_run.parameters else {}
        base_adj = params.get("adjustments") or {}
        adjustments = ScenarioAdjustments(
            # Scenario levers are applied relative to the baseline's own levers.
            demand_change_pct=demand_change_pct + float(base_adj.get("demand_change_pct", params.get("demand_change_pct", 0)) or 0),
            machine_availability_change_pct=machine_availability_change_pct,
            worker_availability_change_pct=worker_availability_change_pct,
            overtime_limit_change_pct=overtime_limit_change_pct,
            production_target_change_pct=production_target_change_pct,
            inventory_change_pct=inventory_change_pct,
            machine_failure_ids=list(machine_failure_ids or []),
        )
        _, new_run = await self.generate_plan(
            start_date=baseline_run.start_date.date(),
            end_date=baseline_run.end_date.date(),
            product_ids=params.get("product_ids"),
            machine_ids=params.get("machine_ids"),
            max_overtime_hours=int(params.get("max_overtime_hours", 8)),
            priority_weights=params.get("priority_weights"),
            adjustments=adjustments,
            scenario_id=scenario_id,
        )
        return new_run
