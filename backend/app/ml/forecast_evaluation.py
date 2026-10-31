from __future__ import annotations

from datetime import timedelta
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from app.ml.forecast_features import (
    FEATURE_COLUMNS,
    build_features,
    features_for_next_day,
)


BASELINE_MODELS = ("Naive", "MovingAverage", "SeasonalNaive", "RandomForest")


def calculate_metrics(actual: list[float], predicted: list[float]) -> dict[str, float | None]:
    actual_values = np.asarray(actual, dtype=float)
    predicted_values = np.maximum(0, np.asarray(predicted, dtype=float))
    if not len(actual_values):
        return {"mae": None, "rmse": None, "mape": None, "wape": None, "bias": None}

    errors = predicted_values - actual_values
    nonzero_actuals = actual_values != 0
    return {
        "mae": float(np.mean(np.abs(errors))),
        "rmse": float(np.sqrt(np.mean(errors**2))),
        "mape": (
            float(np.mean(np.abs(errors[nonzero_actuals] / actual_values[nonzero_actuals])) * 100)
            if nonzero_actuals.any()
            else None
        ),
        "wape": (
            float(np.sum(np.abs(errors)) / np.sum(np.abs(actual_values)) * 100)
            if np.sum(np.abs(actual_values)) > 0
            else None
        ),
        "bias": float(np.mean(errors)),
    }


def _baseline_forecast(model_name: str, history: list[float], horizon: int) -> list[float]:
    if model_name == "Naive":
        return [history[-1]] * horizon
    if model_name == "MovingAverage":
        return [float(np.mean(history[-7:]))] * horizon
    if model_name == "SeasonalNaive":
        if len(history) < 7:
            return [float(np.mean(history))] * horizon
        return [history[-7 + (step % 7)] for step in range(horizon)]
    raise ValueError(f"Unsupported baseline model: {model_name}")


def forecast_series(
    series: pd.DataFrame,
    horizon: int,
    model_name: str,
) -> list[float]:
    history = series.sort_values("date")["demand"].astype(float).tolist()
    if not history:
        raise ValueError("Cannot forecast a product without historical demand")
    if model_name != "RandomForest":
        return [max(0.0, value) for value in _baseline_forecast(model_name, history, horizon)]
    if len(history) < 35:
        raise ValueError("RandomForest requires at least 35 daily observations")

    training = build_features(series).dropna(subset=list(FEATURE_COLUMNS))
    if len(training) < 7:
        raise ValueError("Insufficient feature history to train the forecast model")
    model = RandomForestRegressor(
        n_estimators=60,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(training[list(FEATURE_COLUMNS)], training["demand"])

    last_date = pd.to_datetime(series["date"].max())
    predictions = []
    for step in range(1, horizon + 1):
        features = features_for_next_day(history, last_date + timedelta(days=step))
        prediction = max(
            0.0,
            float(model.predict(pd.DataFrame([features], columns=FEATURE_COLUMNS))[0]),
        )
        predictions.append(prediction)
        history.append(prediction)
    return predictions


def evaluate_models(
    product_series: dict[str, pd.DataFrame],
    horizon: int = 7,
) -> dict[str, Any]:
    """Compare baselines with an expanding-window backtest; folds are chronological."""
    errors: dict[str, dict[str, list[float]]] = {
        model: {"actual": [], "predicted": [], "residuals": []}
        for model in BASELINE_MODELS
    }
    product_residuals: dict[str, dict[str, list[float]]] = {
        product_id: {model: [] for model in BASELINE_MODELS}
        for product_id in product_series
    }
    eligible_products = 0
    backtest_windows = 0

    for product_id, frame in product_series.items():
        frame = frame.sort_values("date").reset_index(drop=True)
        values = frame["demand"].astype(float).tolist()
        if len(values) < 2 * horizon + 30:
            continue
        eligible_products += 1
        origins = sorted(set((
            len(values) - 3 * horizon,
            len(values) - 2 * horizon,
            len(values) - horizon,
        )))
        for origin in origins:
            if origin < 30 or origin + horizon > len(values):
                continue
            backtest_windows += 1
            train = frame.iloc[:origin]
            actual = values[origin:origin + horizon]
            for model_name in BASELINE_MODELS:
                if model_name == "RandomForest" and origin < 35:
                    continue
                predictions = forecast_series(train, horizon, model_name)
                residuals = [
                    float(observed - predicted)
                    for observed, predicted in zip(actual, predictions)
                ]
                errors[model_name]["actual"].extend(actual)
                errors[model_name]["predicted"].extend(predictions)
                errors[model_name]["residuals"].extend(residuals)
                product_residuals[product_id][model_name].extend(
                    abs(value) for value in residuals
                )

    metrics = {
        model_name: calculate_metrics(values["actual"], values["predicted"])
        for model_name, values in errors.items()
        if values["actual"]
    }
    if not metrics:
        return {
            "metrics": {},
            "selected_model": None,
            "residuals": product_residuals,
            "backtest_windows": backtest_windows,
            "eligible_products": eligible_products,
        }
    selected_model = min(
        metrics,
        key=lambda name: (
            metrics[name]["wape"] if metrics[name]["wape"] is not None else float("inf"),
            metrics[name]["mae"] if metrics[name]["mae"] is not None else float("inf"),
        ),
    )
    return {
        "metrics": metrics,
        "selected_model": selected_model,
        "residuals": product_residuals,
        "backtest_windows": backtest_windows,
        "eligible_products": eligible_products,
    }
