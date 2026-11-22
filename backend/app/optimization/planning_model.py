"""Pure, DB-free production planning model (OR-Tools CP-SAT) plus a greedy
operator-assignment step.

Design (see hclpro_fixes.md for the rationale):
- Time bucket: one day. Machine capacity is ``capacity_per_hour`` (units/hour,
  from ``Machine_Capacity_Per_Hour``) x productive hours per day x the machine's
  fractional availability, minus a fixed downtime on days with a scheduled
  maintenance event.
- Production decisions: integer units ``x[order, machine, day]`` on machines of
  the order's process type, from the order's release date (or horizon start)
  to the horizon end.  Production after the due date is allowed but penalised
  per unit-day ("late units"); demand that cannot be produced inside the
  horizon is carried as backlog with a larger, priority-weighted penalty.
- Inventory on hand can be allocated to orders of the same product.
- Workers are assigned after the solve (decoupled, greedy): every machine-hour
  of production needs ``operators_per_machine`` qualified operators from the
  matching shift.  This keeps the CP-SAT model small (orders x eligible
  machines x days instead of orders x workers x days).  Joint
  workforce/shift modelling is the next step.
"""
from __future__ import annotations

import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Set, Tuple

from ortools.sat.python import cp_model

DEFAULT_PRIORITY_WEIGHTS = {"Critical": 4.0, "High": 3.0, "Medium": 2.0, "Low": 1.0}

# Objective weights (integer cost units).  Backlog must always cost more than
# producing late anywhere inside the horizon; see _backlog_penalty().
HOLDING_COST_PER_UNIT_DAY = 1
LATE_COST_PER_UNIT_DAY = 50
LATE_ORDER_COST = 200
BACKLOG_BASE_COST = 500


@dataclass
class OrderInput:
    order_id: str
    product_id: str
    product_name: str
    category: str  # process type; must match MachineInput.machine_type
    demand: int  # target quantity after scenario adjustments
    due_date: date
    release_date: date
    priority: str
    unit_cost: float
    default_machine_id: Optional[str] = None


@dataclass
class MachineInput:
    machine_id: str
    name: str
    machine_type: str
    capacity_per_hour: int
    availability_factor: float = 1.0
    maintenance_days: Set[date] = field(default_factory=set)


@dataclass
class WorkerInput:
    worker_id: str
    name: str
    shift: str
    skills: Set[str]
    availability_factor: float = 1.0


@dataclass
class PlanningProblem:
    start_date: date
    end_date: date
    orders: List[OrderInput]
    machines: List[MachineInput]
    workers: List[WorkerInput] = field(default_factory=list)
    inventory: Dict[str, int] = field(default_factory=dict)
    priority_weights: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_PRIORITY_WEIGHTS))
    shifts: Tuple[str, ...] = ("Morning", "Evening", "Night")
    shift_hours: int = 8
    maintenance_downtime_hours: float = 8.0
    max_overtime_hours: int = 8
    operators_per_machine: int = 1
    time_limit_seconds: float = 30.0
    num_workers: int = 8

    @property
    def dates(self) -> List[date]:
        return [self.start_date + timedelta(days=i) for i in range((self.end_date - self.start_date).days + 1)]

    @property
    def hours_per_day(self) -> float:
        return float(len(self.shifts) * self.shift_hours)


@dataclass
class ScheduleEntry:
    date: date
    machine_id: str
    quantity: int


@dataclass
class OrderResult:
    order: OrderInput
    schedule: List[ScheduleEntry]
    produced: int
    from_inventory: int
    backlog: int
    late_units: int
    completion_date: Optional[date]
    primary_machine_id: Optional[str]
    production_minutes: int
    cost: float

    @property
    def status(self) -> str:
        if self.backlog > 0:
            return "Backlog"
        if self.late_units > 0:
            return "Late"
        return "Planned"


@dataclass
class Assignment:
    worker_id: str
    machine_id: str
    product_id: str
    order_id: str
    date: date
    shift: str
    hours: float
    overtime_hours: float


@dataclass
class PlanningSolution:
    status: str  # CP-SAT status name
    feasible: bool
    objective_value: Optional[float]
    solve_seconds: float
    num_variables: int
    num_constraints: int
    orders: List[OrderResult]
    machine_day_capacity: Dict[Tuple[str, date], int]
    machine_day_load: Dict[Tuple[str, date], int]
    assignments: List[Assignment] = field(default_factory=list)
    unstaffed_hours: float = 0.0
    regular_hours_available: float = 0.0

    @property
    def total_demand(self) -> int:
        return sum(r.order.demand for r in self.orders)

    @property
    def total_production(self) -> int:
        return sum(r.produced for r in self.orders)

    @property
    def total_from_inventory(self) -> int:
        return sum(r.from_inventory for r in self.orders)

    @property
    def total_backlog(self) -> int:
        return sum(r.backlog for r in self.orders)

    @property
    def late_orders(self) -> int:
        return sum(1 for r in self.orders if r.status != "Planned")

    @property
    def total_cost(self) -> float:
        return round(sum(r.cost for r in self.orders), 2)

    @property
    def total_overtime(self) -> float:
        return round(sum(a.overtime_hours for a in self.assignments), 2)

    @property
    def fulfillment_rate(self) -> float:
        demand = self.total_demand
        if demand <= 0:
            return 0.0
        return round(100.0 * (self.total_production + self.total_from_inventory) / demand, 2)

    @property
    def on_time_fulfillment_rate(self) -> float:
        demand = self.total_demand
        if demand <= 0:
            return 0.0
        not_on_time = sum(r.late_units for r in self.orders)  # late production + backlog
        return round(100.0 * (demand - not_on_time) / demand, 2)

    @property
    def machine_utilization(self) -> float:
        capacity = sum(self.machine_day_capacity.values())
        if capacity <= 0:
            return 0.0
        return round(100.0 * sum(self.machine_day_load.values()) / capacity, 2)

    @property
    def workforce_utilization(self) -> float:
        if self.regular_hours_available <= 0:
            return 0.0
        used = sum(a.hours - a.overtime_hours for a in self.assignments)
        return round(100.0 * used / self.regular_hours_available, 2)


def machine_day_capacity(problem: PlanningProblem, machine: MachineInput, day: date) -> int:
    """Units the machine can produce on ``day``."""
    hours = problem.hours_per_day
    if day in machine.maintenance_days:
        hours = max(0.0, hours - problem.maintenance_downtime_hours)
    availability = min(max(machine.availability_factor, 0.0), 1.0)
    return max(0, int(math.floor(machine.capacity_per_hour * hours * availability)))


def _weight(problem: PlanningProblem, priority: str) -> float:
    return float(problem.priority_weights.get(priority, 1.0))


def _backlog_penalty(problem: PlanningProblem, priority: str) -> int:
    horizon = len(problem.dates)
    # Larger than the worst-case late cost inside the horizon, so the solver
    # always prefers producing late over not producing at all.
    return int(math.ceil(_weight(problem, priority) * (LATE_COST_PER_UNIT_DAY * (horizon + 1) + BACKLOG_BASE_COST)))


def eligible_machines(order: OrderInput, machines: List[MachineInput]) -> List[MachineInput]:
    same_type = [m for m in machines if m.machine_type == order.category]
    if same_type:
        return same_type
    return [m for m in machines if m.machine_id == order.default_machine_id]


def solve_production_plan(problem: PlanningProblem) -> PlanningSolution:
    """Build and solve the CP-SAT model.  Synchronous: run it in a worker thread."""
    dates = problem.dates
    model = cp_model.CpModel()

    capacity: Dict[Tuple[str, date], int] = {
        (m.machine_id, d): machine_day_capacity(problem, m, d) for m in problem.machines for d in dates
    }

    x: Dict[Tuple[str, str, date], cp_model.IntVar] = {}
    x_by_order: Dict[str, List[Tuple[str, date, cp_model.IntVar]]] = defaultdict(list)
    from_stock: Dict[str, cp_model.IntVar] = {}
    backlog: Dict[str, cp_model.IntVar] = {}
    is_late: Dict[str, cp_model.IntVar] = {}
    objective = []

    for o in problem.orders:
        target = max(0, int(o.demand))
        first_day = max(problem.start_date, o.release_date)
        weight = _weight(problem, o.priority)
        unit_cost = max(1, int(round(o.unit_cost)))
        late_terms = []
        for m in eligible_machines(o, problem.machines):
            for d in dates:
                cap = capacity[(m.machine_id, d)]
                if d < first_day or cap <= 0 or target == 0:
                    continue
                var = model.NewIntVar(0, min(target, cap), f"x_{o.order_id}_{m.machine_id}_{d.isoformat()}")
                x[(o.order_id, m.machine_id, d)] = var
                x_by_order[o.order_id].append((m.machine_id, d, var))
                if d <= o.due_date:
                    coeff = unit_cost + HOLDING_COST_PER_UNIT_DAY * (o.due_date - d).days
                else:
                    days_late = (d - o.due_date).days
                    coeff = unit_cost + int(math.ceil(LATE_COST_PER_UNIT_DAY * weight * days_late))
                    late_terms.append(var)
                objective.append(coeff * var)

        from_stock[o.order_id] = model.NewIntVar(0, target, f"stock_{o.order_id}")
        backlog[o.order_id] = model.NewIntVar(0, target, f"backlog_{o.order_id}")
        is_late[o.order_id] = model.NewBoolVar(f"late_{o.order_id}")

        order_vars = [var for _, _, var in x_by_order[o.order_id]]
        # Demand balance: produce + allocate stock + backlog == target.
        model.Add(sum(order_vars) + from_stock[o.order_id] + backlog[o.order_id] == target)
        # An order is late if any unit is produced after the due date or backlogged.
        model.Add(sum(late_terms) + backlog[o.order_id] <= target * is_late[o.order_id])

        objective.append(_backlog_penalty(problem, o.priority) * backlog[o.order_id])
        objective.append(int(math.ceil(LATE_ORDER_COST * weight)) * is_late[o.order_id])

    # Machine capacity per day.
    by_machine_day: Dict[Tuple[str, date], list] = defaultdict(list)
    for (oid, mid, d), var in x.items():
        by_machine_day[(mid, d)].append(var)
    for (mid, d), vars_ in by_machine_day.items():
        model.Add(sum(vars_) <= capacity[(mid, d)])

    # Inventory on hand per product.
    by_product: Dict[str, list] = defaultdict(list)
    for o in problem.orders:
        by_product[o.product_id].append(from_stock[o.order_id])
    for product_id, vars_ in by_product.items():
        model.Add(sum(vars_) <= max(0, int(problem.inventory.get(product_id, 0))))

    model.Minimize(sum(objective))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(problem.time_limit_seconds)
    solver.parameters.num_search_workers = int(problem.num_workers)
    started = time.perf_counter()
    status = solver.Solve(model)
    elapsed = time.perf_counter() - started
    status_name = solver.StatusName(status)
    feasible = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    proto = model.Proto()

    solution = PlanningSolution(
        status=status_name,
        feasible=feasible,
        objective_value=solver.ObjectiveValue() if feasible else None,
        solve_seconds=round(elapsed, 3),
        num_variables=len(proto.variables),
        num_constraints=len(proto.constraints),
        orders=[],
        machine_day_capacity=capacity,
        machine_day_load={},
    )
    if not feasible:
        return solution

    machine_by_id = {m.machine_id: m for m in problem.machines}
    load: Dict[Tuple[str, date], int] = defaultdict(int)
    for o in problem.orders:
        entries: List[ScheduleEntry] = []
        per_machine: Dict[str, int] = defaultdict(int)
        late_units = 0
        minutes = 0.0
        for mid, d, var in x_by_order[o.order_id]:
            qty = int(solver.Value(var))
            if qty <= 0:
                continue
            entries.append(ScheduleEntry(date=d, machine_id=mid, quantity=qty))
            per_machine[mid] += qty
            load[(mid, d)] += qty
            minutes += 60.0 * qty / max(1, machine_by_id[mid].capacity_per_hour)
            if d > o.due_date:
                late_units += qty
        entries.sort(key=lambda e: (e.date, e.machine_id))
        produced = sum(e.quantity for e in entries)
        bl = int(solver.Value(backlog[o.order_id]))
        solution.orders.append(OrderResult(
            order=o,
            schedule=entries,
            produced=produced,
            from_inventory=int(solver.Value(from_stock[o.order_id])),
            backlog=bl,
            late_units=late_units + bl,
            completion_date=entries[-1].date if entries else None,
            primary_machine_id=max(per_machine, key=per_machine.get) if per_machine else o.default_machine_id,
            production_minutes=int(round(minutes)),
            cost=round(produced * o.unit_cost, 2),
        ))
    solution.machine_day_load = dict(load)

    assign_workers(problem, solution)
    return solution


def assign_workers(problem: PlanningProblem, solution: PlanningSolution) -> None:
    """Greedy operator assignment after the production solve (heuristic).

    Each machine-day's run time (units / capacity_per_hour) is laid out on a
    timeline starting at the first shift, so it falls into consecutive shifts
    of ``shift_hours``.  Each segment needs ``operators_per_machine`` operators
    who (a) have a skill for the machine type and (b) work that shift.  The
    least-loaded qualified worker is picked; regular hours per worker-day are
    ``shift_hours x availability_factor`` and overtime is capped at
    ``max_overtime_hours``.  Hours that cannot be staffed are reported as
    ``unstaffed_hours`` instead of being silently dropped.
    """
    machine_by_id = {m.machine_id: m for m in problem.machines}
    regular_cap = {
        w.worker_id: problem.shift_hours * min(max(w.availability_factor, 0.0), 1.0) for w in problem.workers
    }
    solution.regular_hours_available = round(sum(regular_cap.values()) * len(problem.dates), 2)
    workers_by_shift: Dict[str, List[WorkerInput]] = defaultdict(list)
    for w in problem.workers:
        workers_by_shift[w.shift].append(w)
    used: Dict[Tuple[str, date], float] = defaultdict(float)
    unstaffed = 0.0
    eps = 1e-9

    def staff(need: float, shift: str, d: date, machine: MachineInput, order_id: str, product_id: str) -> float:
        while need > eps:
            candidates = [
                w for w in workers_by_shift.get(shift, [])
                if machine.machine_type in w.skills
                and used[(w.worker_id, d)] < regular_cap[w.worker_id] + problem.max_overtime_hours - eps
            ]
            if not candidates:
                return need
            worker = min(candidates, key=lambda w: (used[(w.worker_id, d)], w.worker_id))
            limit = regular_cap[worker.worker_id] + problem.max_overtime_hours
            give = min(need, limit - used[(worker.worker_id, d)])
            regular_left = max(0.0, regular_cap[worker.worker_id] - used[(worker.worker_id, d)])
            overtime = max(0.0, give - regular_left)
            used[(worker.worker_id, d)] += give
            solution.assignments.append(Assignment(
                worker_id=worker.worker_id, machine_id=machine.machine_id, product_id=product_id,
                order_id=order_id, date=d, shift=shift,
                hours=round(give, 2), overtime_hours=round(overtime, 2),
            ))
            need -= give
        return 0.0

    per_machine_day: Dict[Tuple[str, date], List[Tuple[str, str, int]]] = defaultdict(list)
    for result in solution.orders:
        for entry in result.schedule:
            per_machine_day[(entry.machine_id, entry.date)].append(
                (result.order.order_id, result.order.product_id, entry.quantity)
            )

    for (mid, d), parts in sorted(per_machine_day.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        machine = machine_by_id[mid]
        t = 0.0
        for order_id, product_id, qty in parts:
            run_hours = qty / max(1, machine.capacity_per_hour)
            while run_hours > eps:
                shift_index = int(t // problem.shift_hours)
                if shift_index >= len(problem.shifts):
                    unstaffed += run_hours * problem.operators_per_machine
                    break
                segment = min(run_hours, (shift_index + 1) * problem.shift_hours - t)
                for _ in range(problem.operators_per_machine):
                    unstaffed += staff(segment, problem.shifts[shift_index], d, machine, order_id, product_id)
                t += segment
                run_hours -= segment
    solution.unstaffed_hours = round(unstaffed, 2)
