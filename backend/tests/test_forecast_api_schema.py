import pytest
from pydantic import ValidationError

from app.schemas.forecast import ForecastRequest


@pytest.mark.parametrize("horizon", [7, 14, 30])
def test_forecast_api_accepts_supported_horizons(horizon):
    assert ForecastRequest(horizon_days=horizon).horizon_days == horizon


@pytest.mark.parametrize("horizon", [0, 1, 6, 8, 29, 31, 90])
def test_forecast_api_rejects_unsupported_horizons(horizon):
    with pytest.raises(ValidationError):
        ForecastRequest(horizon_days=horizon)


def test_forecast_api_supports_a_single_product_filter():
    request = ForecastRequest(horizon_days=14, product_id="P1")

    assert request.product_ids == ["P1"]


def test_forecast_api_rejects_conflicting_product_filters():
    with pytest.raises(ValidationError):
        ForecastRequest(product_id="P1", product_ids=["P2"])
