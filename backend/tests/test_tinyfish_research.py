import json

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.v1.endpoints import research
from app.core.config import settings


@pytest.mark.asyncio
async def test_research_requires_an_api_key(monkeypatch):
    monkeypatch.setattr(settings, "TINYFISH_API_KEY", "")

    with pytest.raises(HTTPException) as exc:
        await research.run_research(research.ResearchRequest(query="Research production trends"))

    assert exc.value.status_code == 503
    assert "TINYFISH_API_KEY" in exc.value.detail


def test_research_query_is_required_and_limited():
    with pytest.raises(ValidationError):
        research.ResearchRequest(query=" ")
    with pytest.raises(ValidationError):
        research.ResearchRequest(query="x" * 10_001)


@pytest.mark.asyncio
async def test_research_stream_forwards_events_without_exposing_key(monkeypatch):
    api_key = "private-test-key"
    payload = {
        "event": "final_result",
        "result": "Research summary",
        "citations": ["https://example.com/source"],
    }

    def handle_request(request):
        assert request.headers["X-API-Key"] == api_key
        assert request.url == research.TINYFISH_RESEARCH_URL
        assert json.loads(request.read()) == {"query": "Research production trends", "mode": "deep"}
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text=f'data: {{"event":"created","research_run_id":"run-1"}}\n\ndata: {json.dumps(payload)}\n\ndata: {{"event":"done"}}\n\n',
        )

    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        research.httpx,
        "AsyncClient",
        lambda timeout: real_async_client(transport=httpx.MockTransport(handle_request), timeout=timeout),
    )

    events = [chunk async for chunk in research._stream_research("Research production trends", api_key)]

    assert any('"event": "final_result"' in event for event in events)
    assert all(api_key not in event for event in events)
