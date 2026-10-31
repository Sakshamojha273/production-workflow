import logging
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.ml.forecast_service import ForecastService
from app.models.forecast import Forecast
from app.models.product import Product
from app.schemas.forecast import ForecastListResponse, ForecastRequest, ForecastResponse

router = APIRouter()
logger = logging.getLogger(__name__)


async def _responses(forecasts: list[Forecast], db: AsyncSession) -> ForecastListResponse:
    product_ids = {forecast.product_id for forecast in forecasts}
    products = {}
    if product_ids:
        result = await db.execute(
            select(Product.product_id, Product.name).where(
                Product.product_id.in_(product_ids)
            )
        )
        products = {row.product_id: row.name for row in result.all()}
    responses = []
    for forecast in forecasts:
        model_name = (
            forecast.model_version.split(":", 1)[1]
            if forecast.model_version and ":" in forecast.model_version
            else forecast.model_used.value
        )
        responses.append(
            ForecastResponse(
                product_id=forecast.product_id,
                product_name=products.get(forecast.product_id, forecast.product_id),
                forecast_date=forecast.forecast_date,
                forecast_horizon_days=forecast.forecast_horizon_days,
                predicted_demand=forecast.predicted_demand,
                lower_bound=forecast.lower_bound,
                upper_bound=forecast.upper_bound,
                confidence_level=forecast.confidence_level,
                model_used=forecast.model_used,
                model_name=model_name,
                mae=forecast.mae,
                rmse=forecast.rmse,
                created_at=forecast.created_at,
            )
        )
    return ForecastListResponse(forecasts=responses, total=len(responses))


@router.get("", response_model=ForecastListResponse)
async def get_forecasts(
    product_id: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    horizon: Optional[int] = Query(default=None, ge=1, le=30),
    horizon_days: Optional[int] = Query(default=None, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
):
    """Read persisted forecasts, optionally filtered by product, date, and horizon."""
    stmt = select(Forecast)
    if product_id:
        stmt = stmt.where(Forecast.product_id == product_id)
    if start_date:
        stmt = stmt.where(Forecast.forecast_date >= start_date)
    if end_date:
        stmt = stmt.where(Forecast.forecast_date <= end_date)
    selected_horizon = horizon if horizon is not None else horizon_days
    if selected_horizon:
        stmt = stmt.where(Forecast.forecast_horizon_days <= selected_horizon)
    stmt = stmt.order_by(Forecast.forecast_date, Forecast.product_id)
    forecasts = list((await db.execute(stmt)).scalars().all())
    return await _responses(forecasts, db)


@router.post("/generate", response_model=ForecastListResponse)
async def generate_forecast(
    request: ForecastRequest,
    db: AsyncSession = Depends(get_db),
):
    """Backtest candidate models, select the best performer, and persist forecasts."""
    if request.horizon_days > settings.FORECAST_MAX_HORIZON:
        raise HTTPException(
            status_code=422,
            detail=f"Forecast horizon cannot exceed {settings.FORECAST_MAX_HORIZON} days.",
        )
    service = ForecastService(db)
    try:
        forecasts = await service.generate(
            request.horizon_days,
            request.product_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Forecast generation failed")
        raise HTTPException(
            status_code=500,
            detail="Forecast generation failed. Check the server logs for details.",
        ) from exc
    return await _responses(forecasts, db)


@router.get("/history")
async def get_demand_history(
    product_id: Optional[str] = None,
    days: int = Query(default=90, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Return daily observed demand used by the forecasting system."""
    service = ForecastService(db)
    daily, _ = await service.prepare_history(
        [product_id] if product_id else None
    )
    if daily.empty:
        return {"history": [], "total": 0}
    latest_date = daily["date"].max()
    start_date = latest_date - timedelta(days=days - 1)
    daily = daily[daily["date"] >= start_date]
    daily = daily[["date", "product_id", "product_name", "demand"]]
    history = [
        {
            "date": row.date.date().isoformat(),
            "product_id": row.product_id,
            "product_name": row.product_name,
            "demand": float(row.demand),
        }
        for row in daily.itertuples(index=False)
    ]
    return {"history": history, "total": len(history)}


@router.get("/metrics")
async def get_forecast_metrics(
    product_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    service = ForecastService(db)
    result = await service.evaluate([product_id] if product_id else None)
    return {
        "selected_model": result["selected_model"],
        "metrics": result["metrics"],
        "backtest_windows": result["backtest_windows"],
        "eligible_products": result["eligible_products"],
        "method": "Expanding-window chronological backtesting; no random split.",
    }


@router.get("/models")
async def get_forecast_models(
    product_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Compare baseline and ML models on chronological historical backtests."""
    return await get_forecast_metrics(product_id, db)


@router.get("/latest", response_model=ForecastListResponse)
async def get_latest_forecast(
    horizon_days: int = Query(default=7, ge=1, le=30),
    product_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Forecast).where(
        Forecast.forecast_horizon_days <= horizon_days
    )
    if product_id:
        stmt = stmt.where(Forecast.product_id == product_id)
    stmt = stmt.order_by(Forecast.forecast_date, Forecast.product_id)
    forecasts = list((await db.execute(stmt)).scalars().all())
    return await _responses(forecasts, db)


@router.get("/accuracy/{product_id}")
async def get_forecast_accuracy(
    product_id: str,
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    service = ForecastService(db)
    result = await service.evaluate([product_id])
    selected = result["selected_model"]
    return {
        "selected_model": selected,
        "metrics": result["metrics"].get(selected, {}) if selected else {},
        "backtest_windows": result["backtest_windows"],
        "eligible_products": result["eligible_products"],
        "method": "Expanding-window chronological backtesting.",
    }
