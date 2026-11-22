"""Regression tests for the 2026-11-22 bug-fix pass."""
from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from app.services.data_processor import DataProcessor, normalize_maintenance_status


class TestMaintenanceStatusMapping:
    def test_numeric_flags(self):
        values = pd.Series([0.0, 1.0, np.nan, 0, 1, "0.0", "1", "true", "no", ""], dtype=object)
        assert normalize_maintenance_status(values).tolist() == [
            "Operational", "Scheduled", "Operational", "Operational", "Scheduled",
            "Operational", "Scheduled", "Scheduled", "Operational", "Operational",
        ]

    def test_text_labels_kept(self):
        values = pd.Series(["None", "Scheduled", "Emergency", None, "Overhaul"])
        assert normalize_maintenance_status(values).tolist() == [
            "Operational", "Scheduled", "Emergency", "Operational", "Overhaul",
        ]

    def test_only_flagged_rows_become_events(self):
        df = pd.DataFrame({
            "Order_ID": ["A", "B", "C"],
            "Date": ["2026-09-29", "2026-10-02", "2026-10-03"],
            "Machine_ID": ["M1", "M1", "M2"],
            "Maintenance_Status": normalize_maintenance_status(pd.Series([1.0, 0.0, np.nan])),
        })
        rows = DataProcessor._maintenance_rows(df, reference_date=date(2026, 10, 1))
        assert len(rows) == 1
        assert rows[0]["type"].value == "Preventive"
        assert rows[0]["status"].value == "Completed"


class TestInventoryRows:
    def test_unit_cost_safety_stock_and_as_of_level(self):
        df = pd.DataFrame({
            "Order_ID": ["A", "B", "C", "D"],
            "Product_ID": ["P1"] * 4,
            "Date": pd.to_datetime(["2026-09-28", "2026-09-29", "2026-09-30", "2026-10-05"]),
            "Due_Date": pd.to_datetime(["2026-09-30", "2026-10-01", "2026-10-02", "2026-10-07"]),
            "Demand": [100, 200, 300, 400],
            "Production_Quantity": [100, 100, 100, 100],
            "Production_Cost": [1000.0, 1000.0, 2000.0, 4000.0],
            "Inventory_Level": [50, 60, 70, 999],
            "Safety_Stock": [0, 0, 0, 0],
        })
        row = DataProcessor._inventory_rows(df, reference_date=date(2026, 10, 1))["P1"]
        assert row["current_level"] == 70          # latest row on/before the reference date
        assert row["unit_cost"] == 20.0            # 8000 / 400
        assert row["safety_stock"] > 0             # computed when the file has none
        assert row["reorder_point"] > row["safety_stock"]


def test_coverage_days_uses_average_daily_demand():
    from app.api.v1.endpoints.inventory import _coverage_days
    assert _coverage_days(500, 250.0) == 2.0
    assert _coverage_days(500, 0) == 0.0


def test_machine_risk_analyzer_tolerates_unwritable_model_path(monkeypatch):
    from app.core.config import settings
    from app.ml.machine_risk import MachineRiskAnalyzer
    monkeypatch.setattr(settings, "ML_MODEL_PATH", "/proc/definitely-not-writable/models")
    analyzer = MachineRiskAnalyzer(db=None)
    assert analyzer.model_path is None


def test_default_model_path_is_project_relative():
    import os
    from app.core import config
    assert config._BACKEND_DIR.endswith("backend") or os.path.isdir(os.path.join(config._BACKEND_DIR, "app"))


class TestScenarioComparison:
    def _run(self, **kw):
        base = dict(total_cost=100.0, total_overtime=0, late_orders=0, machine_utilization=50.0,
                    workforce_utilization=10.0, fulfillment_rate=80.0, run_id="R")
        base.update(kw)
        return SimpleNamespace(**base)

    def test_zero_baseline_and_unchanged(self):
        from app.api.v1.endpoints.scenario import _compare_runs
        scenario = SimpleNamespace(scenario_id="S", name="s")
        result = _compare_runs(self._run(), self._run(late_orders=87, total_cost=90.0), scenario)
        by_name = {m.metric: m for m in result.metrics}
        assert by_name["Late Orders"].change_pct is None
        assert by_name["Late Orders"].change == 87
        assert by_name["Late Orders"].improvement is False
        assert by_name["Overtime Hours"].improvement is None      # unchanged, not a "Regression"
        assert by_name["Total Cost"].improvement is True
        assert by_name["Total Cost"].change_pct == pytest.approx(-10.0)


def test_scenario_verdict_rule():
    from app.api.v1.endpoints.scenario import scenario_verdict

    assert scenario_verdict(0.0, 0.0)[0] == "No change"
    assert scenario_verdict(2.0, -100.0)[0] == "Improvement"
    assert scenario_verdict(0.0, -100.0)[0] == "Improvement"
    # Cheaper only because fewer orders get filled: not an improvement.
    verdict, reason = scenario_verdict(-5.0, -1000.0, -3.2)
    assert verdict == "Trade-off"
    assert "Fulfilment -5.0 pts" in reason and "cost -3.2%" in reason
    assert scenario_verdict(3.0, 500.0)[0] == "Trade-off"
    assert scenario_verdict(-1.0, 10.0)[0] == "Worse"
    assert scenario_verdict(-1.0, 0.0)[0] == "Worse"


def test_risk_category_thresholds():
    from app.ml.machine_risk import MachineRiskAnalyzer

    assert [MachineRiskAnalyzer.risk_category(x) for x in (0, 0.299, 0.3, 0.599, 0.6, 1)] == [
        "Low", "Low", "Medium", "Medium", "High", "High"]


# --- QA pass 2026-11-22: B2 (failed upload must store a readable report) ---

class _FakeSession:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        pass


@pytest.mark.parametrize("content", [
    b"Order_ID,Date,Foo\nX1,2026-01-01,3\n",   # missing required columns
    b"",                                        # empty file
    bytes(range(128, 256)) * 4,                 # not text
], ids=["missing-columns", "empty", "binary"])
async def test_failed_upload_report_matches_response_schema(content):
    from app.schemas.data import DataQualityResponse, DataUploadResponse
    session = _FakeSession()
    report = await DataProcessor(session).process_csv(content, "bad.csv")
    report.created_at = report.created_at or __import__("datetime").datetime.utcnow()
    assert report.status.value == "Failed" and report.error_message
    assert report.missing_by_column == {} and report.column_types == {} and report.sample_data == []
    DataQualityResponse.model_validate(report, from_attributes=True)
    DataUploadResponse.model_validate(report, from_attributes=True)


def test_quality_response_tolerates_legacy_null_profile():
    from datetime import datetime
    from app.schemas.data import DataQualityResponse
    legacy = SimpleNamespace(
        report_id="r", filename="f.csv", total_rows=0, total_columns=0, missing_values=None,
        duplicate_rows=None, invalid_records=None, outliers=None, quality_score=None,
        missing_by_column=None, column_types=None, status="Failed", error_message="x",
        created_at=datetime(2026, 11, 22, 6, 25), completed_at=None,
    )
    parsed = DataQualityResponse.model_validate(legacy, from_attributes=True)
    assert parsed.missing_by_column == {} and parsed.missing_values == 0 and parsed.quality_score == 0.0


def test_critical_priority_enum_and_weight():
    from app.models.order import OrderPriority
    from app.optimization.planning_model import DEFAULT_PRIORITY_WEIGHTS
    assert OrderPriority("Critical") is OrderPriority.CRITICAL
    assert DEFAULT_PRIORITY_WEIGHTS["Critical"] > DEFAULT_PRIORITY_WEIGHTS["High"]
