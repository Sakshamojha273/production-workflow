import pytest

from app.optimization.demand_adjustment import apply_demand_change


@pytest.mark.parametrize(
    ("demand", "change_pct", "expected"),
    [(100, -10, 90), (100, 0, 100), (100, 20, 120), (100, -200, 0)],
)
def test_scenario_demand_adjustment_is_nonnegative(demand, change_pct, expected):
    assert apply_demand_change(demand, change_pct) == expected
