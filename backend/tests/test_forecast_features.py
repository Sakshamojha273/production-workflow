import pandas as pd
import pytest

from app.ml import forecast_evaluation
from app.ml.forecast_evaluation import calculate_metrics, forecast_series
from app.ml.forecast_features import aggregate_daily_demand, build_features, make_daily_series


def test_order_demand_is_aggregated_by_product_and_date():
    orders = pd.DataFrame({
        "date": ["2026-01-01", "2026-01-01", "2026-01-02"],
        "product_id": ["P1", "P1", "P1"],
        "demand": [10, 25, 8],
        "product_name": ["Part", "Part", "Part"],
    })

    daily = aggregate_daily_demand(orders)

    assert daily[["date", "product_id", "demand"]].to_dict("records") == [
        {"date": pd.Timestamp("2026-01-01"), "product_id": "P1", "demand": 35},
        {"date": pd.Timestamp("2026-01-02"), "product_id": "P1", "demand": 8},
    ]


def test_daily_series_marks_no_order_days_as_zero_within_observed_period():
    orders = pd.DataFrame({
        "date": ["2026-01-01", "2026-01-03"],
        "product_id": ["P1", "P1"],
        "demand": [10, 8],
    })

    daily = make_daily_series(orders)

    assert daily["demand"].tolist() == [10, 0, 8]
    assert len(daily) == 3


def test_lag_and_rolling_features_only_use_past_demand():
    dates = pd.date_range("2026-01-01", periods=35, freq="D")
    series = pd.DataFrame({"date": dates, "demand": range(1, 36)})

    features = build_features(series)
    row = features.iloc[28]

    assert row["lag_1"] == 28
    assert row["lag_7"] == 22
    assert row["lag_14"] == 15
    assert row["lag_28"] == 1
    assert row["rolling_mean_7"] == pytest.approx(25)
    assert row["rolling_mean_14"] == pytest.approx(21.5)
    assert row["rolling_mean_28"] == pytest.approx(14.5)

    changed_current_value = series.copy()
    changed_current_value.loc[28, "demand"] = 99999
    changed_features = build_features(changed_current_value)
    assert changed_features.loc[28, "lag_1"] == row["lag_1"]
    assert changed_features.loc[28, "rolling_mean_7"] == row["rolling_mean_7"]


def test_next_day_demand_is_not_used_as_a_forecasting_feature():
    series = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=35, freq="D"),
        "demand": range(35),
        "Next_Day_Demand": [100000] * 35,
    })

    features = build_features(series)

    assert "Next_Day_Demand" not in features.columns


def test_baseline_forecasts_use_observed_history():
    series = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=14, freq="D"),
        "demand": list(range(1, 15)),
    })

    assert forecast_series(series, 2, "Naive") == [14, 14]
    assert forecast_series(series, 2, "MovingAverage") == [11.0, 11.0]
    assert forecast_series(series, 2, "SeasonalNaive") == [8, 9]


def test_metrics_include_error_and_bias():
    metrics = calculate_metrics([10, 20, 30], [12, 18, 30])

    assert metrics["mae"] == pytest.approx(4 / 3)
    assert metrics["rmse"] == pytest.approx((8 / 3) ** 0.5)
    assert metrics["mape"] == pytest.approx((20 + 10 + 0) / 3)
    assert metrics["wape"] == pytest.approx(4 / 60 * 100)
    assert metrics["bias"] == pytest.approx(0)


def test_backtesting_uses_expanding_chronological_training_windows(monkeypatch):
    dates = pd.date_range("2026-01-01", periods=60, freq="D")
    series = pd.DataFrame({"date": dates, "demand": range(60)})
    training_end_dates = []

    def predict_from_training_window(training, horizon, model_name):
        training_end_dates.append(training["date"].max())
        return [float(training["demand"].iloc[-1])] * horizon

    monkeypatch.setattr(forecast_evaluation, "forecast_series", predict_from_training_window)

    result = forecast_evaluation.evaluate_models({"P1": series}, horizon=7)

    assert result["backtest_windows"] == 3
    assert set(training_end_dates) == {dates[38], dates[45], dates[52]}
    assert result["selected_model"] in result["metrics"]
