from sqlalchemy import Column, String, Integer, Float, DateTime, Date, ForeignKey, Text, Enum, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid
from datetime import datetime
import enum


class ForecastModel(str, enum.Enum):
    MOVING_AVERAGE = "MovingAverage"
    RANDOM_FOREST = "RandomForest"
    XGBOOST = "XGBoost"
    PROPHET = "Prophet"
    LSTM = "LSTM"


class Forecast(Base):
    __tablename__ = "forecasts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(String(50), ForeignKey("products.product_id"), nullable=False)
    forecast_date = Column(Date, nullable=False)
    forecast_horizon_days = Column(Integer, nullable=False)
    predicted_demand = Column(Integer, nullable=False)
    lower_bound = Column(Integer, nullable=True)
    upper_bound = Column(Integer, nullable=True)
    confidence_level = Column(Float, default=0.95)
    model_used = Column(Enum(ForecastModel), default=ForecastModel.MOVING_AVERAGE)
    model_version = Column(String(50), nullable=True)
    mae = Column(Float, nullable=True)
    rmse = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    product = relationship("Product", backref="forecasts")
    
    __table_args__ = (
        Index("ix_forecasts_product_date", "product_id", "forecast_date"),
    )