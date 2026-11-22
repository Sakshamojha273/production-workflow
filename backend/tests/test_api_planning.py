"""API integration tests for planning, scenario, maintenance and analytics endpoints.

They need PostgreSQL (the models use PostgreSQL types and the importer uses
INSERT ... ON CONFLICT).  Set TEST_DATABASE_URL to a *dedicated* database whose
name contains "test", e.g.

    TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/smartplan_test

The schema in that database is dropped and recreated for every test.
"""
import io
import os
import random
from collections import defaultdict
from datetime import date, timedelta

import pandas as pd
import pytest

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL or "test" not in TEST_DATABASE_URL.rsplit("/", 1)[-1],
    reason="TEST_DATABASE_URL (a database whose name contains 'test') is not set",
)

if TEST_DATABASE_URL:
    import httpx
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    import app.models  # noqa: F401
    from app.core.config import settings
    from app.core.database import Base, get_db
    from app.core.schema_upgrades import UPGRADE_STATEMENTS
    from app.main import app
    from app.api.v1.endpoints.auth import create_access_token, DEMO_USER
    from app.services.data_processor import DataProcessor

TODAY = date.today()
# Keep every fixture date in the past relative to "today" so the machine-risk
# window (which never looks past today) has data.
REFERENCE = TODAY - timedelta(days=12)


def _fixture_csv() -> bytes:
    """Small dataset in the same raw schema as data/raw/Production_Planning_AI_10K_Dataset.csv."""
    rng = random.Random(7)
    machines = [("M001", "CNC-01", "Machining", 12), ("M002", "CNC-02", "Machining", 12), ("M003", "ASM-01", "Assembly", 10)]
    products = [("P001", "Shaft", "Machining"), ("P002", "Bracket", "Machining"), ("P003", "Housing", "Assembly")]
    workers = []
    for i, shift in enumerate(["Morning", "Evening", "Night"] * 2):
        dept = "Machining" if i % 2 == 0 else "Assembly"
        workers.append((f"W{i + 1:03d}", f"Worker_{i + 1:03d}", dept, shift))
    rows = []
    for i in range(40):
        product = products[i % len(products)]
        same_type = [m for m in machines if m[2] == product[2]]
        machine = same_type[i % len(same_type)]
        worker = next(w for w in workers if w[2] == product[2])
        order_date = REFERENCE - timedelta(days=10) + timedelta(days=i % 14)
        due = order_date + timedelta(days=rng.randint(2, 6))
        demand = rng.randint(60, 160)
        maint = "None"
        if i % 9 == 0:
            maint = "Scheduled"
        elif i % 13 == 0:
            maint = "Emergency"
        rows.append({
            "Order_ID": f"O{i + 1:05d}", "Date": order_date.isoformat(), "Product_ID": product[0],
            "Product_Name": product[1], "Process_Type": product[2], "Demand_Qty": demand,
            "Planned_Production_Qty": demand - rng.randint(0, 20), "Due_Date": due.isoformat(),
            "Priority": rng.choice(["High", "Medium", "Low"]), "Machine_ID": machine[0],
            "Machine_Name": machine[1], "Machine_Capacity_Per_Hour": machine[3],
            "Machine_Availability": round(rng.uniform(0.7, 0.99), 3), "Maintenance_Status": maint,
            "Worker_ID": worker[0], "Worker_Name": worker[1], "Worker_Department": worker[2],
            "Worker_Availability": round(rng.uniform(0.8, 0.99), 3), "Shift": worker[3],
            "Inventory_Level": rng.randint(0, 40), "Production_Time_Min": rng.randint(10, 45),
            "Unit_Production_Capacity": 30, "Overtime_Hours": round(rng.uniform(0, 2), 2),
            "Late_Units": rng.choice([0, 0, 3]), "Production_Cost": round(demand * 25.0, 2),
            "Machine_Vibration": round(rng.uniform(0.5, 4), 2), "Machine_Temperature_C": round(rng.uniform(40, 85), 2),
            "Machine_Risk_Score": round(rng.uniform(0, 1), 3), "Next_Day_Demand": demand,
        })
    return pd.DataFrame(rows).to_csv(index=False).encode()


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setattr(settings, "PLANNING_REFERENCE_DATE", REFERENCE)
    monkeypatch.setattr(settings, "PLANNING_SOLVER_TIME_LIMIT_SECONDS", 10.0)
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        for statement in UPGRADE_STATEMENTS:
            await conn.execute(text(statement))
    sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with sessions() as session:
        report = await DataProcessor(session).process_csv(_fixture_csv(), "fixture.csv")
        assert report.error_message is None, report.error_message

    async def override_get_db():
        async with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=app)
    token = create_access_token({"sub": DEMO_USER["email"], "user_id": DEMO_USER["id"]})
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(transport=transport, base_url="http://test", headers=headers) as http:
        http.sessions = sessions
        yield http
    app.dependency_overrides.clear()
    await engine.dispose()


def _window():
    return {"start_date": REFERENCE.isoformat(), "end_date": (REFERENCE + timedelta(days=13)).isoformat()}


async def _generate(client):
    response = await client.post("/api/planning/generate", json=_window())
    assert response.status_code == 200, response.text
    return response.json()


async def test_upload_imports_open_orders_fractional_availability_and_maintenance(client):
    orders = (await client.get("/api/orders", params={"page_size": 100})).json()["orders"]
    assert any(o["status"] == "Pending" for o in orders)
    assert all(o["status"] != "Pending" or o["due_date"] >= REFERENCE.isoformat() for o in orders)
    assert any(0 < o["machine_availability"] < 1 for o in orders)

    machines = (await client.get("/api/machines")).json()["machines"]
    assert all(0 < m["availability_factor"] < 1 for m in machines)

    maintenance = await client.get("/api/maintenance")
    assert maintenance.status_code == 200
    events = maintenance.json()
    assert events and {e["type"] for e in events} <= {"Preventive", "Emergency"}

    reports = (await client.get("/api/data/quality")).json()
    assert reports[0]["missing_values"] == 0  # "None" maintenance status is a value


async def test_generate_plan_returns_real_items_within_capacity(client):
    plan = await _generate(client)

    assert plan["status"] == "Generated"
    assert plan["optimization_run_id"]
    assert plan["items"], "plan must contain one item per open order"
    assert plan["notes"]["solver_status"] in ("OPTIMAL", "FEASIBLE")

    total_demand = 0
    load = defaultdict(int)
    for item in plan["items"]:
        assert item["planned_production"] + item["from_inventory"] + item["backlog"] == item["demand"]
        assert item["planned_production"] == sum(e["quantity"] for e in item["schedule"])
        assert item["status"] in ("Planned", "Late", "Backlog")
        total_demand += item["demand"]
        for entry in item["schedule"]:
            load[(entry["machine_id"], entry["date"])] += entry["quantity"]
    assert plan["total_demand"] == total_demand
    assert plan["total_production"] == sum(i["planned_production"] for i in plan["items"])

    machines = {m["machine_id"]: m for m in (await client.get("/api/machines")).json()["machines"]}
    hours_per_day = len(settings.PLANNING_SHIFTS) * settings.PLANNING_SHIFT_HOURS
    for (machine_id, _day), qty in load.items():
        machine = machines[machine_id]
        assert qty <= machine["capacity"] * hours_per_day * machine["availability_factor"] + 1e-6


async def test_plan_read_endpoints(client):
    plan = await _generate(client)

    listing = await client.get("/api/planning")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["plans"][0]["items"] == []

    latest = await client.get("/api/planning/latest")
    assert latest.status_code == 200
    assert latest.json()["plan_id"] == plan["plan_id"]
    assert len(latest.json()["items"]) == len(plan["items"])

    single = await client.get(f"/api/planning/{plan['plan_id']}")
    assert single.status_code == 200
    assert single.json()["items"] == plan["items"]


async def test_generate_plan_rejects_bad_windows(client):
    response = await client.post("/api/planning/generate", json={"start_date": "2026-03-10", "end_date": "2026-03-01"})
    assert response.status_code == 422
    far = REFERENCE + timedelta(days=400)
    response = await client.post(
        "/api/planning/generate",
        json={"start_date": far.isoformat(), "end_date": (far + timedelta(days=3)).isoformat()},
    )
    assert response.status_code == 422
    assert "No open orders" in response.json()["detail"]


async def test_machine_risk_and_analytics_summary(client):
    risk = await client.get("/api/maintenance/machine-risk")
    assert risk.status_code == 200, risk.text
    assert {r["machine_id"] for r in risk.json()} == {"M001", "M002", "M003"}

    summary = await client.get("/api/analytics/summary")
    assert summary.status_code == 200, summary.text
    assert "inventory_coverage" in summary.json()


async def test_scenario_flow_end_to_end(client):
    plan = await _generate(client)

    created = await client.post("/api/scenario", json={
        "name": "Lose a CNC", "demand_change_pct": 10, "machine_availability_change_pct": -20,
        "worker_availability_change_pct": 0, "overtime_limit_change_pct": 0,
        "production_target_change_pct": 0, "inventory_change_pct": 0, "machine_failure_ids": ["M002"],
    })
    assert created.status_code == 200, created.text
    scenario = created.json()
    assert scenario["status"] == "Draft"
    assert scenario["machine_failure_ids"] == ["M002"]

    # Exactly what the frontend sends: JSON body with the plan's optimization_run_id (a UUID).
    run = await client.post(
        f"/api/scenario/{scenario['scenario_id']}/run", json={"baseline_run_id": plan["optimization_run_id"]}
    )
    assert run.status_code == 200, run.text
    comparison = run.json()
    assert comparison["scenario_id"] == scenario["scenario_id"]
    metrics = {m["metric"]: m for m in comparison["metrics"]}
    assert metrics["Fulfillment Rate %"]["baseline"] > 0

    stored = (await client.get(f"/api/scenario/{scenario['scenario_id']}")).json()
    assert stored["status"] == "Completed"
    assert stored["comparison_results"]["metrics"]
    listing = await client.get("/api/scenario")
    assert listing.status_code == 200
    # The scenario's own plan does not replace the baseline as "latest".
    assert (await client.get("/api/planning/latest")).json()["plan_id"] == plan["plan_id"]
    assert (await client.get("/api/planning")).json()["total"] == 1


async def test_scenario_is_not_marked_completed_when_optimisation_fails(client, monkeypatch):
    plan = await _generate(client)
    scenario = (await client.post("/api/scenario", json={"name": "fails"})).json()

    from app.optimization import production_optimizer
    from app.optimization.planning_model import PlanningSolution

    def infeasible(problem):
        return PlanningSolution(
            status="INFEASIBLE", feasible=False, objective_value=None, solve_seconds=0.0,
            num_variables=0, num_constraints=0, orders=[], machine_day_capacity={}, machine_day_load={},
        )

    monkeypatch.setattr(production_optimizer, "solve_production_plan", infeasible)
    run = await client.post(
        f"/api/scenario/{scenario['scenario_id']}/run", json={"baseline_run_id": plan["optimization_run_id"]}
    )
    assert run.status_code == 422
    assert (await client.get(f"/api/scenario/{scenario['scenario_id']}")).json()["status"] == "Failed"


async def test_scenario_requires_completed_baseline(client):
    failed = await client.post("/api/planning/generate", json={
        "start_date": (REFERENCE + timedelta(days=400)).isoformat(),
        "end_date": (REFERENCE + timedelta(days=401)).isoformat(),
    })
    assert failed.status_code == 422
    scenario = (await client.post("/api/scenario", json={"name": "no baseline"})).json()
    async with client.sessions() as session:
        run_id = (await session.execute(text("select run_id from optimization_runs limit 1"))).scalar()
    run = await client.post(f"/api/scenario/{scenario['scenario_id']}/run", json={"baseline_run_id": run_id})
    assert run.status_code == 409
    # Backwards compatible query-parameter form is still accepted.
    run = await client.post(f"/api/scenario/{scenario['scenario_id']}/run", params={"baseline_run_id": run_id})
    assert run.status_code == 409


async def test_api_requires_bearer_token(client):
    anon = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    async with anon:
        assert (await anon.get("/api/orders")).status_code == 401
        assert (await anon.get("/api/dashboard")).status_code == 401
        assert (await anon.get("/api/orders", headers={"Authorization": "Bearer not-a-jwt"})).status_code == 401
        assert (await anon.get("/health")).status_code == 200
        assert (await anon.post("/api/auth/login", json={"email": "admin@smartplan.ai", "password": "wrong"})).status_code == 401
        login = await anon.post("/api/auth/demo-login")
        assert login.status_code == 200
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        assert (await anon.get("/api/orders", headers=headers)).status_code == 200
        me = await anon.get("/api/auth/me", headers=headers)
        assert me.status_code == 200 and me.json()["email"] == "admin@smartplan.ai"
        assert (await anon.get("/api/auth/me")).status_code == 401


async def test_machine_sensor_fields_filled_by_upload(client):
    machines = (await client.get("/api/machines")).json()["machines"]
    assert machines
    for m in machines:
        assert m["vibration"] > 0 and m["temperature_c"] > 0, m


async def test_risk_distribution_matches_machine_risk(client):
    risks = (await client.get("/api/maintenance/machine-risk")).json()
    dist = (await client.get("/api/maintenance/risk-distribution")).json()
    expected = {"Low": 0, "Medium": 0, "High": 0}
    for r in risks:
        expected[r["risk_category"]] += 1
    assert dist == expected


async def test_current_demand_uses_reference_date(client):
    kpis = (await client.get("/api/analytics/kpis")).json()
    current = kpis["current_demand"] if "current_demand" in kpis else next(
        k for k in kpis.get("kpis", []) if k.get("title") == "Current Demand")
    assert "PLANNING_REFERENCE_DATE" in current["description"]
    assert str(REFERENCE) in current["description"] or "before" in current["description"]


async def test_csv_reports_and_settings(client):
    await _generate(client)
    catalogue = (await client.get("/api/reports")).json()
    ids = {r["id"] for r in catalogue["reports"]}
    assert {"plan-summary", "plan-items", "orders", "inventory", "workforce-assignments"} <= ids
    for rid in ids:
        response = await client.get(f"/api/reports/{rid}")
        assert response.status_code == 200, (rid, response.text)
        assert response.headers["content-type"].startswith("text/csv")
        assert "attachment" in response.headers["content-disposition"]
        lines = response.text.strip().splitlines()
        assert len(lines) >= 2, rid  # header + at least one data row
    orders = await client.get("/api/reports/orders")
    assert int(orders.headers["x-row-count"]) == 40
    assert (await client.get("/api/reports/nope")).status_code == 404
    settings_view = (await client.get("/api/settings")).json()
    flat = {i["key"]: i["value"] for g in settings_view["groups"] for i in g["items"]}
    assert flat["PLANNING_REFERENCE_DATE"] == REFERENCE.isoformat()
    assert "SECRET_KEY" in flat and settings.SECRET_KEY not in str(settings_view)
    assert "postgres:" not in flat["DATABASE"] or "@" not in flat["DATABASE"]


# --- Regression tests for the QA pass of 2026-11-22 (B1, B2, B3, B8) ---

async def test_orders_search_by_id_and_product_name(client):
    by_id = await client.get("/api/orders", params={"search": "O00001"})
    assert by_id.status_code == 200, by_id.text
    assert [o["order_id"] for o in by_id.json()["orders"]] == ["O00001"]
    by_name = await client.get("/api/orders", params={"search": "hous", "page_size": 100})
    assert by_name.status_code == 200, by_name.text
    body = by_name.json()
    assert body["total"] > 0 and {o["product_name"] for o in body["orders"]} == {"Housing"}
    assert (await client.get("/api/orders", params={"search": "no-such-order"})).json()["total"] == 0


async def test_rejected_upload_returns_reason_and_keeps_history_readable(client):
    bad = await client.post(
        "/api/data/upload", files={"file": ("bad.csv", b"Order_ID,Date,Foo\nX1,2026-01-01,3\n", "text/csv")}
    )
    assert bad.status_code == 422
    assert "missing required columns" in bad.json()["detail"]

    reports = await client.get("/api/data/quality")
    assert reports.status_code == 200, reports.text
    failed = next(r for r in reports.json() if r["filename"] == "bad.csv")
    assert failed["status"] == "Failed" and failed["missing_by_column"] == {}
    assert "missing required columns" in failed["error_message"]
    detail = await client.get(f"/api/data/quality/{failed['report_id']}")
    assert detail.status_code == 200, detail.text

    # Rows written by the old code path have NULL profile columns; they must still be readable.
    from app.models.data_quality_report import DataQualityReport, DataQualityStatus as ModelStatus
    async with client.sessions() as session:
        session.add(DataQualityReport(
            report_id="legacy01", filename="legacy.csv", total_rows=0, total_columns=0,
            quality_score=0.0, status=ModelStatus.FAILED, error_message="old failure",
            missing_by_column=None, column_types=None, sample_data=None,
        ))
        await session.commit()
    assert (await client.get("/api/data/quality")).status_code == 200
    assert (await client.get("/api/data/quality/legacy01")).status_code == 200


async def test_upload_rejects_non_csv_extension(client):
    response = await client.post("/api/data/upload", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert response.status_code == 400
    assert ".csv" in response.json()["detail"]


async def test_critical_priority_is_imported_and_filterable(client):
    df = pd.read_csv(io.BytesIO(_fixture_csv()))
    df.loc[0, "Priority"] = "Critical"
    response = await client.post(
        "/api/data/upload", files={"file": ("crit.csv", df.to_csv(index=False).encode(), "text/csv")}
    )
    assert response.status_code == 200, response.text
    critical = (await client.get("/api/orders", params={"priority": "Critical"})).json()
    assert critical["total"] == 1 and critical["orders"][0]["order_id"] == df.loc[0, "Order_ID"]
    charts = await client.get("/api/analytics/charts")
    assert charts.status_code == 200, charts.text
