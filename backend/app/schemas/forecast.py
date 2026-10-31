from pydantic import BaseModel, Field, model_validator
from typing import Optional, List
from datetime import date, datetime
from enum import Enum
from app.core.config import settings


class ForecastModel(str, Enum):
    MOVING_AVERAGE = "MovingAverage"
    RANDOM_FOREST = "RandomForest"
    XGBOOST = "XGBoost"
    PROPHET = "Prophet"
    LSTM = "LSTM"


class ForecastRequest(BaseModel):
    product_ids: Optional[List[str]] = None
    product_id: Optional[str] = None
    horizon_days: int = Field(default=settings.FORECAST_DEFAULT_HORIZON, ge=7, le=30)
    model: Optional[ForecastModel] = None

    @model_validator(mode="after")
    def validate_horizon(self):
        if self.horizon_days not in (7, 14, 30):
            raise ValueError("horizon_days must be 7, 14, or 30")
        if self.product_id:
            if self.product_ids and self.product_id not in self.product_ids:
                raise ValueError("product_id conflicts with product_ids")
            self.product_ids = [self.product_id]
        return self


class ForecastResponse(BaseModel):
    product_id: str
    product_name: str
    forecast_date: date
    forecast_horizon_days: int
    predicted_demand: int
    lower_bound: Optional[int] = None
    upper_bound: Optional[int] = None
    confidence_level: float
    model_used: ForecastModel
    model_name: Optional[str] = None
    mae: Optional[float] = None
    rmse: Optional[float] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class ForecastListResponse(BaseModel):
    forecasts: List[ForecastResponse]
    total: int