import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.v1.endpoints import search
from app.core.config import settings


def test_search_query_is_required_and_limited():
    with pytest.raises(ValidationError):
        search.SearchRequest(query=" ")
    with pytest.raises(ValidationError):
        search.SearchRequest(query="x" * 2_001)


@pytest.mark.asyncio
async def test_search_requires_an_api_key(monkeypatch):
    monkeypatch.setattr(settings, "TINYFISH_API_KEY", "")

    with pytest.raises(HTTPException) as exc:
        await search.search_web(search.SearchRequest(query="weather"))

    assert exc.value.status_code == 503
    assert "TINYFISH_API_KEY" in exc.value.detail


@pytest.mark.asyncio
async def test_search_calls_tinyfish_without_exposing_the_api_key(monkeypatch):
    api_key = "private-test-key"
    payload = {
        "query": "weather",
        "results": [{"position": 1, "title": "Forecast", "url": "https://example.com"}],
        "total_results": 1,
        "page": 0,
    }

    def handle_request(request):
        assert str(request.url).startswith(f"{search.TINYFISH_SEARCH_URL}?")
        assert request.url.params["query"] == "weather"
        assert request.headers["X-API-Key"] == api_key
        return httpx.Response(200, json=payload)

    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        search.httpx,
        "AsyncClient",
        lambda timeout: real_async_client(transport=httpx.MockTransport(handle_request), timeout=timeout),
    )
    monkeypatch.setattr(settings, "TINYFISH_API_KEY", api_key)

    result = await search.search_web(search.SearchRequest(query="weather"))

    assert result == payload
    assert api_key not in str(result)


@pytest.mark.asyncio
async def test_tinyfish_auth_failure_is_not_reported_as_app_auth(monkeypatch):
    def handle_request(_request):
        return httpx.Response(401, json={"error": "invalid key"})

    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        search.httpx,
        "AsyncClient",
        lambda timeout: real_async_client(transport=httpx.MockTransport(handle_request), timeout=timeout),
    )
    monkeypatch.setattr(settings, "TINYFISH_API_KEY", "private-test-key")

    with pytest.raises(HTTPException) as exc:
        await search.search_web(search.SearchRequest(query="weather"))

    assert exc.value.status_code == 502
    assert "API key" in exc.value.detail
