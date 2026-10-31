from __future__ import annotations

import logging
import hashlib
from datetime import date, datetime, timedelta
from collections import OrderedDict
from typing import Any, Optional

import numpy as np
import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.ml.forecast_evaluation import evaluate_models, forecast_series
from app.ml.forecast_features import make_daily_series
from app.models.demand_history import DemandHistory
from app.models.forecast import Forecast, ForecastModel
from app.models.product import Product

logger = logging.getLogger(__name__)
_EVALUATION_CACHE: OrderedDict[str, dict[str, Any]] = OrderedDict()
_MAX_EVALUATION_CACHE_ENTRIES = 8


class ForecastService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def load_history(self, product_ids: Optional[list[str]] = None) -> pd.DataFrame:
        stmt = select(
            DemandHistory.product_id,
            DemandHistory.date,
            DemandHistory.demand,
            Product.name,
            Product.category,
        ).join(Product, Product.product_id == DemandHistory.product_id)
        if product_ids:
            stmt = stmt.where(DemandHistory.product_id.in_(product_ids))
        stmt = stmt.order_by(DemandHistory.product_id, DemandHistory.date)
        records = (await self.db.execute(stmt)).all()
        if not records:
            return pd.DataFrame(columns=["product_id", "date", "demand", "product_name", "process_type"])
        return pd.DataFrame(
            [
                {
                    "product_id": row.product_id,
                    "date": row.date,
                    "demand": row.demand,
                    "product_name": row.name,
                    "process_type": row.category,
                }
                for row in records
            ]
        )

    async def prepare_history(
        self, product_ids: Optional[list[str]] = None
    ) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
        raw = await self.load_history(product_ids)
        daily = make_daily_series(raw)
        products = {
            product_id: rows.sort_values("date").reset_index(drop=True)
            for product_id, rows in daily.groupby("product_id", sort=False)
        } if not daily.empty else {}
        return daily, products

    async def evaluate(
        self, product_ids: Optional[list[str]] = None, horizon: int = 7
    ) -> dict[str, Any]:
        daily, products = await self.prepare_history(product_ids)
        if daily.empty:
            return {
                "metrics": {},
                "selected_model": None,
                "backtest_windows": 0,
                "eligible_products": 0,
            }
        hashed_rows = pd.util.hash_pandas_object(
            daily[["product_id", "date", "demand"]], index=False
        ).values.tobytes()
        cache_key = hashlib.sha256(
            hashed_rows + str(horizon).encode("ascii")
        ).hexdigest()
        result = _EVALUATION_CACHE.get(cache_key)
        if result is None:
            result = evaluate_models(products, horizon=horizon)
            _EVALUATION_CACHE[cache_key] = result
            if len(_EVALUATION_CACHE) > _MAX_EVALUATION_CACHE_ENTRIES:
                _EVALUATION_CACHE.popitem(last=False)
        else:
            _EVALUATION_CACHE.move_to_end(cache_key)
        return {key: value for key, value in result.items() if key != "residuals"}

    async def generate(
        self,
        horizon: int,
        product_ids: Optional[list[str]] = None,
    ) -> list[Forecast]:
        daily, products = await self.prepare_history(product_ids)
        if daily.empty:
            raise ValueError("No historical demand is available. Upload demand data first.")

        minimum_history = settings.FORECAST_MIN_HISTORY
        too_short = [key for key, rows in products.items() if len(rows) < minimum_history]
        if too_short:
            raise ValueError(
                f"Insufficient historical data for reliable forecasting: "
                f"{len(too_short)} selected product(s) have fewer than {minimum_history} daily observations."
            )

        await self.evaluate(product_ids, horizon=min(horizon, 7))
        evaluation = _EVALUATION_CACHE.get(
            hashlib.sha256(
                pd.util.hash_pandas_object(
                    daily[["product_id", "date", "demand"]], index=False
                ).values.tobytes()
                + str(min(horizon, 7)).encode("ascii")
            ).hexdigest()
        )
        if evaluation is None:
            raise RuntimeError("Backtest results are unavailable after model evaluation")
        selected_model = evaluation["selected_model"] or "MovingAverage"
        residuals = evaluation["residuals"]
        interval_level = settings.FORECAST_INTERVAL_LEVEL
        interval_quantile = min(1.0, (1.0 + interval_level) / 2.0)
        created_at = datetime.utcnow()
        forecasts: list[Forecast] = []
        for product_id, series in products.items():
            model_name = selected_model
            if model_name == "RandomForest" and len(series) < 35:
                model_name = "MovingAverage"
            predictions = forecast_series(series, horizon, model_name)
            residual_values = residuals.get(product_id, {}).get(model_name, [])
            error_margin = (
                float(np.quantile(residual_values, interval_quantile))
                if residual_values
                else float(series["demand"].tail(28).std(ddof=0) or 0)
            )
            last_date = pd.to_datetime(series["date"].max()).date()
            for offset, prediction in enumerate(predictions, start=1):
                quantity = max(0, int(round(prediction)))
                margin = max(0, int(np.ceil(error_margin)))
                forecasts.append(
                    Forecast(
                        product_id=product_id,
                        forecast_date=last_date + timedelta(days=offset),
                        forecast_horizon_days=offset,
                        predicted_demand=quantity,
                        lower_bound=max(0, quantity - margin),
                        upper_bound=quantity + margin,
                        confidence_level=interval_level,
                        model_used=(
                            ForecastModel.RANDOM_FOREST
                            if model_name == "RandomForest"
                            else ForecastModel.MOVING_AVERAGE
                        ),
                        model_version=f"backtest-v1:{model_name}",
                        mae=evaluation["metrics"].get(model_name, {}).get("mae"),
                        rmse=evaluation["metrics"].get(model_name, {}).get("rmse"),
                        created_at=created_at,
                    )
                )

        forecast_product_ids = list(products)
        await self.db.execute(
            delete(Forecast).where(Forecast.product_id.in_(forecast_product_ids))
        )
        self.db.add_all(forecasts)
        await self.db.commit()
        logger.info(
            "Generated %s daily forecasts for %s products using %s",
            len(forecasts),
            len(products),
            selected_model,
        )
        return forecasts
