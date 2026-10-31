"""Compatibility facade for code using the original demand forecaster."""

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.forecast_service import ForecastService


class DemandForecaster:
    def __init__(self, db: AsyncSession):
        self.service = ForecastService(db)

    async def generate_forecast(
        self,
        product_ids: Optional[list[str]] = None,
        horizon_days: int = 7,
        model_type: Any = None,
    ):
        return await self.service.generate(horizon_days, product_ids)

    async def get_forecast_accuracy(self, product_id: str, days: int = 30) -> dict:
        result = await self.service.evaluate([product_id])
        metrics = result.get("metrics", {})
        selected = result.get("selected_model")
        selected_metrics = metrics.get(selected, {}) if selected else {}
        return {
            "mape": selected_metrics.get("mape"),
            "mae": selected_metrics.get("mae"),
            "rmse": selected_metrics.get("rmse"),
            "wape": selected_metrics.get("wape"),
            "num_comparisons": selected_metrics.get("backtest_observations", 0),
            "selected_model": selected,
        }
