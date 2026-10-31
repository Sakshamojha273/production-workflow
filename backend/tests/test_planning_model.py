"""Unit tests for the DB-free CP-SAT planning model."""
from collections import defaultdict
from datetime import date, timedelta

import pytest

from app.optimization.planning_model import (
    MachineInput,
    OrderInput,
    PlanningProblem,
    WorkerInput,
    machine_day_capacity,
    solve_production_plan,
)

START = date(2026, 3, 2)


def _order(order_id, demand, due_offset, product="P1", category="Machining", priority="Medium", release_offset=-3):
    return OrderInput(
        order_id=order_id,
        product_id=product,
        product_name=f"Product {product}",
        category=category,
        demand=demand,
        due_date=START + timedelta(days=due_offset),
        release_date=START + timedelta(days=release_offset),
        priority=priority,
        unit_cost=10.0,
        default_machine_id="M1",
    )


def _machines(capacity_per_hour=10, availability=1.0, maintenance=None):
    return [
        MachineInput("M1", "CNC-01", "Machining", capacity_per_hour, availability, set(maintenance or [])),
        MachineInput("M2", "CNC-02", "Machining", capacity_per_hour, availability),
        MachineInput("A1", "ASM-01", "Assembly", capacity_per_hour, availability),
    ]


def _workers():
    workers = []
    for shift in ("Morning", "Evening", "Night"):
        for i in range(2):
            workers.append(WorkerInput(f"W-{shift}-{i}", f"{shift} {i}", shift, {"Machining", "Assembly"}, 1.0))
    return workers


def _problem(orders, machines=None, days=5, **kwargs):
    return PlanningProblem(
        start_date=START,
        end_date=START + timedelta(days=days - 1),
        orders=orders,
        machines=machines or _machines(),
        workers=kwargs.pop("workers", _workers()),
        time_limit_seconds=10,
        num_workers=4,
        **kwargs,
    )


def _assert_balance_and_capacity(problem, solution):
    for result in solution.orders:
        assert result.produced + result.from_inventory + result.backlog == result.order.demand
        assert result.produced == sum(e.quantity for e in result.schedule)
    load = defaultdict(int)
    for result in solution.orders:
        for entry in result.schedule:
            load[(entry.machine_id, entry.date)] += entry.quantity
            machine = next(m for m in problem.machines if m.machine_id == entry.machine_id)
            assert machine.machine_type == result.order.category
            assert entry.date >= max(problem.start_date, result.order.release_date)
    for key, qty in load.items():
        assert qty <= solution.machine_day_capacity[key]


def test_feasible_plan_meets_demand_within_capacity():
    orders = [
        _order("O1", 300, 1),
        _order("O2", 500, 3, priority="High"),
        _order("O3", 200, 4, product="P2", category="Assembly"),
    ]
    problem = _problem(orders)
    solution = solve_production_plan(problem)

    assert solution.feasible
    assert solution.status in ("OPTIMAL", "FEASIBLE")
    _assert_balance_and_capacity(problem, solution)
    # Enough capacity (240 units/machine-day): everything on time, nothing backlogged.
    assert solution.total_backlog == 0
    assert solution.late_orders == 0
    assert solution.fulfillment_rate == 100.0
    assert all(r.completion_date <= r.order.due_date for r in solution.orders)
    assert solution.num_variables > 0 and solution.num_constraints > 0


def test_capacity_shortage_is_backlogged_not_hidden():
    # 2 Machining machines x 240 units/day x 2 days = 960 < 2000 demanded.
    orders = [_order("O1", 1000, 1, priority="High"), _order("O2", 1000, 1, priority="Low")]
    problem = _problem(orders, days=2)
    solution = solve_production_plan(problem)

    assert solution.feasible
    _assert_balance_and_capacity(problem, solution)
    assert solution.total_production == 960  # every available unit of capacity is used
    assert solution.total_backlog == 2000 - 960
    by_id = {r.order.order_id: r for r in solution.orders}
    # Higher priority order is served first.
    assert by_id["O1"].backlog <= by_id["O2"].backlog
    assert all(r.status in ("Backlog", "Late") for r in solution.orders if r.backlog)


def test_late_is_defined_by_due_date():
    # Due on day 0, only 240+240 units/day of Machining capacity: 900 units cannot all be on time.
    orders = [_order("O1", 900, 0)]
    problem = _problem(orders, days=3)
    solution = solve_production_plan(problem)

    result = solution.orders[0]
    assert result.backlog == 0  # produced within the horizon ...
    on_time = sum(e.quantity for e in result.schedule if e.date <= result.order.due_date)
    assert on_time == 480
    assert result.late_units == 900 - 480  # ... but partly after the due date
    assert result.status == "Late"
    assert solution.late_orders == 1


def test_inventory_on_hand_is_used_before_producing():
    orders = [_order("O1", 100, 2)]
    problem = _problem(orders, inventory={"P1": 60})
    solution = solve_production_plan(problem)

    result = solution.orders[0]
    assert result.from_inventory == 60
    assert result.produced == 40


def test_maintenance_day_and_availability_reduce_capacity():
    maint_day = START
    problem = _problem([_order("O1", 10, 1)], machines=_machines(capacity_per_hour=10, availability=0.5, maintenance=[maint_day]))
    m1 = problem.machines[0]
    assert machine_day_capacity(problem, m1, maint_day) == int(10 * (24 - 8) * 0.5)
    assert machine_day_capacity(problem, m1, maint_day + timedelta(days=1)) == int(10 * 24 * 0.5)


def test_no_production_before_order_release_date():
    order = _order("O1", 100, 3, release_offset=2)
    problem = _problem([order])
    solution = solve_production_plan(problem)
    assert all(e.date >= order.release_date for e in solution.orders[0].schedule)


def test_workers_are_qualified_and_on_their_shift():
    orders = [_order("O1", 400, 2), _order("O2", 300, 2, product="P2", category="Assembly")]
    problem = _problem(orders)
    solution = solve_production_plan(problem)

    workers = {w.worker_id: w for w in problem.workers}
    machine_type = {m.machine_id: m.machine_type for m in problem.machines}
    assert solution.assignments
    for a in solution.assignments:
        assert workers[a.worker_id].shift == a.shift
        assert machine_type[a.machine_id] in workers[a.worker_id].skills
    # Staffed hours match machine run hours (1 operator per machine, capacity 10 units/h).
    run_hours = sum(r.produced for r in solution.orders) / 10
    staffed = sum(a.hours for a in solution.assignments)
    assert staffed + solution.unstaffed_hours == pytest.approx(run_hours, abs=0.05)


def test_unstaffed_hours_are_reported_when_nobody_is_qualified():
    workers = [WorkerInput("W1", "Assembler", "Morning", {"Assembly"}, 1.0)]
    problem = _problem([_order("O1", 50, 2)], workers=workers)
    solution = solve_production_plan(problem)
    assert solution.assignments == []
    assert solution.unstaffed_hours == pytest.approx(5.0, abs=0.01)
