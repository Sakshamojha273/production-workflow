from pydantic_settings import BaseSettings
from typing import Optional
from datetime import date
import os


class Settings(BaseSettings):
    APP_NAME: str = "SmartPlan AI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/smartplan"
    DATABASE_URL_SYNC: str = "postgresql://postgres:postgres@localhost:5432/smartplan"
    
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    CORS_ORIGINS: list = ["http://localhost:5173", "http://localhost:3000"]
    
    UPLOAD_MAX_SIZE: int = 10 * 1024 * 1024  # 10MB
    UPLOAD_ALLOWED_TYPES: list = ["text/csv", "application/csv"]
    
    ML_MODEL_PATH: str = "/app/models"
    FORECAST_DEFAULT_HORIZON: int = 7
    FORECAST_MAX_HORIZON: int = 30
    FORECAST_INTERVAL_LEVEL: float = 0.80
    FORECAST_MIN_HISTORY: int = 30

    # Production planning (see app/optimization/planning_model.py)
    PLANNING_SHIFTS: list = ["Morning", "Evening", "Night"]
    PLANNING_SHIFT_HOURS: int = 8
    # Productive hours lost on a machine-day that has a maintenance event.
    PLANNING_MAINTENANCE_DOWNTIME_HOURS: float = 8.0
    PLANNING_OPERATORS_PER_MACHINE: int = 1
    PLANNING_MAX_HORIZON_DAYS: int = 31
    PLANNING_SOLVER_TIME_LIMIT_SECONDS: float = 30.0
    PLANNING_SOLVER_WORKERS: int = 8
    # Orders due on/after this date are imported as open ("Pending") orders.
    # Defaults to the upload date when unset.
    PLANNING_REFERENCE_DATE: Optional[date] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()