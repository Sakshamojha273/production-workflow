from __future__ import annotations

import pandas as pd


FEATURE_COLUMNS = (
    "day_of_week",
    "day_of_month",
    "week_of_year",
    "month",
    "quarter",
    "lag_1",
    "lag_7",
    "lag_14",
    "lag_28",
    "rolling_mean_7",
    "rolling_mean_14",
    "rolling_mean_28",
    "rolling_std_7",
    "rolling_std_14",
    "rolling_std_28",
)


def aggregate_daily_demand(data: pd.DataFrame) -> pd.DataFrame:
    """Aggregate order-level demand without using future-derived fields."""
    required = {"date", "product_id", "demand"}
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"Demand data is missing columns: {', '.join(sorted(missing))}")

    cleaned = data.copy()
    cleaned["date"] = pd.to_datetime(cleaned["date"], errors="coerce").dt.normalize()
    cleaned["demand"] = pd.to_numeric(cleaned["demand"], errors="coerce")
    cleaned = cleaned.dropna(subset=["date", "product_id", "demand"])
    if cleaned["demand"].lt(0).any():
        raise ValueError("Demand quantities must not be negative")

    group_columns = ["date", "product_id"]
    aggregations: dict[str, tuple[str, str]] = {"demand": ("demand", "sum")}
    for column in ("product_name", "process_type"):
        if column in cleaned.columns:
            aggregations[column] = (column, "first")

    daily = cleaned.groupby(group_columns, as_index=False).agg(**aggregations)
    return daily.sort_values(["product_id", "date"]).reset_index(drop=True)


def make_daily_series(data: pd.DataFrame) -> pd.DataFrame:
    """Create a daily series per product, treating unrecorded order days as zero."""
    daily = aggregate_daily_demand(data)
    if daily.empty:
        return daily

    series = []
    for product_id, product_data in daily.groupby("product_id", sort=False):
        indexed = product_data.set_index("date").sort_index()
        dates = pd.date_range(indexed.index.min(), indexed.index.max(), freq="D")
        expanded = indexed.reindex(dates)
        expanded.index.name = "date"
        expanded["product_id"] = product_id
        expanded["demand"] = expanded["demand"].fillna(0.0)
        for column in ("product_name", "process_type"):
            if column in expanded.columns:
                expanded[column] = expanded[column].ffill().bfill()
        series.append(expanded.reset_index())
    return pd.concat(series, ignore_index=True).sort_values(
        ["product_id", "date"]
    ).reset_index(drop=True)


def build_features(series: pd.DataFrame) -> pd.DataFrame:
    """Build one-step-ahead features using only demand known before each date."""
    if not {"date", "demand"}.issubset(series.columns):
        raise ValueError("A demand series must contain date and demand columns")

    result = series[["date", "demand"]].sort_values("date").copy().reset_index(drop=True)
    result["date"] = pd.to_datetime(result["date"])
    demand_before_date = result["demand"].shift(1)

    result["day_of_week"] = result["date"].dt.dayofweek
    result["day_of_month"] = result["date"].dt.day
    result["week_of_year"] = result["date"].dt.isocalendar().week.astype(int)
    result["month"] = result["date"].dt.month
    result["quarter"] = result["date"].dt.quarter
    for lag in (1, 7, 14, 28):
        result[f"lag_{lag}"] = result["demand"].shift(lag)
    for window in (7, 14, 28):
        result[f"rolling_mean_{window}"] = demand_before_date.rolling(window).mean()
        result[f"rolling_std_{window}"] = demand_before_date.rolling(window).std(ddof=0)
    return result


def features_for_next_day(history: list[float], forecast_date: pd.Timestamp) -> list[float]:
    """Build the same lag and calendar features for a recursively predicted day."""
    if len(history) < 28:
        raise ValueError("At least 28 daily observations are required for forecast features")

    row = {
        "day_of_week": forecast_date.dayofweek,
        "day_of_month": forecast_date.day,
        "week_of_year": int(forecast_date.isocalendar().week),
        "month": forecast_date.month,
        "quarter": forecast_date.quarter,
    }
    for lag in (1, 7, 14, 28):
        row[f"lag_{lag}"] = history[-lag]
    for window in (7, 14, 28):
        window_values = history[-window:]
        row[f"rolling_mean_{window}"] = sum(window_values) / window
        mean = row[f"rolling_mean_{window}"]
        row[f"rolling_std_{window}"] = (
            sum((value - mean) ** 2 for value in window_values) / window
        ) ** 0.5
    return [float(row[column]) for column in FEATURE_COLUMNS]
