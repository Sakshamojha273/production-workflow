"""Read-only view of the running backend configuration for the Settings page.

Values come from app.core.config.settings (backend/.env). Secrets are never
returned: only whether SECRET_KEY is still a development default, and the
database host/name without credentials.
"""
from sqlalchemy.engine import make_url
from fastapi import APIRouter

from app.core.config import settings, reference_date
from app.core.security import secret_key_is_default

router = APIRouter()


@router.get("")
async def get_settings():
    try:
        url = make_url(settings.DATABASE_URL)
        database = f"{url.get_backend_name()}://{url.host or 'localhost'}:{url.port or 5432}/{url.database}"
    except Exception:  # pragma: no cover - malformed URL
        database = "unparseable DATABASE_URL"
    return {
        "editable": False,
        "source": "backend/.env (restart the backend after editing)",
        "groups": [
            {"name": "Application", "items": [
                {"key": "APP_NAME", "value": settings.APP_NAME},
                {"key": "APP_VERSION", "value": settings.APP_VERSION},
                {"key": "DEBUG", "value": settings.DEBUG},
                {"key": "DATABASE", "value": database},
                {"key": "CORS_ORIGINS", "value": ", ".join(map(str, settings.CORS_ORIGINS))},
            ]},
            {"name": "Planning", "items": [
                {"key": "PLANNING_REFERENCE_DATE", "value": settings.PLANNING_REFERENCE_DATE.isoformat() if settings.PLANNING_REFERENCE_DATE else None,
                 "note": f"App 'today' = {reference_date().isoformat()}"},
                {"key": "PLANNING_SHIFTS", "value": ", ".join(settings.PLANNING_SHIFTS)},
                {"key": "PLANNING_SHIFT_HOURS", "value": settings.PLANNING_SHIFT_HOURS},
                {"key": "PLANNING_MAINTENANCE_DOWNTIME_HOURS", "value": settings.PLANNING_MAINTENANCE_DOWNTIME_HOURS},
                {"key": "PLANNING_OPERATORS_PER_MACHINE", "value": settings.PLANNING_OPERATORS_PER_MACHINE},
                {"key": "PLANNING_MAX_HORIZON_DAYS", "value": settings.PLANNING_MAX_HORIZON_DAYS},
                {"key": "PLANNING_SOLVER_TIME_LIMIT_SECONDS", "value": settings.PLANNING_SOLVER_TIME_LIMIT_SECONDS},
                {"key": "PLANNING_SOLVER_WORKERS", "value": settings.PLANNING_SOLVER_WORKERS},
            ]},
            {"name": "Forecasting", "items": [
                {"key": "FORECAST_DEFAULT_HORIZON", "value": settings.FORECAST_DEFAULT_HORIZON},
                {"key": "FORECAST_MAX_HORIZON", "value": settings.FORECAST_MAX_HORIZON},
                {"key": "FORECAST_INTERVAL_LEVEL", "value": settings.FORECAST_INTERVAL_LEVEL},
                {"key": "FORECAST_MIN_HISTORY", "value": settings.FORECAST_MIN_HISTORY},
            ]},
            {"name": "Data upload", "items": [
                {"key": "UPLOAD_MAX_SIZE", "value": f"{settings.UPLOAD_MAX_SIZE // (1024 * 1024)} MB"},
                {"key": "UPLOAD_ALLOWED_TYPES", "value": ", ".join(settings.UPLOAD_ALLOWED_TYPES)},
            ]},
            {"name": "Security", "items": [
                {"key": "ACCESS_TOKEN_EXPIRE_MINUTES", "value": settings.ACCESS_TOKEN_EXPIRE_MINUTES},
                {"key": "ALGORITHM", "value": settings.ALGORITHM},
                {"key": "SECRET_KEY", "value": "development default - change before deploying" if secret_key_is_default() else "set (hidden)"},
            ]},
        ],
    }
