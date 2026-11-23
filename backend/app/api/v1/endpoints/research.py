import json
from typing import AsyncIterator

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings

router = APIRouter()

TINYFISH_RESEARCH_URL = "https://agent.tinyfish.ai/v1/automation/run-research"


class ResearchRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(min_length=1, max_length=10_000)


def _event(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=True)}\n\n"


async def _stream_research(query: str, api_key: str) -> AsyncIterator[str]:
    timeout = httpx.Timeout(connect=20, read=2700, write=20, pool=20)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                TINYFISH_RESEARCH_URL,
                headers={"X-API-Key": api_key},
                json={"query": query, "mode": "deep"},
            ) as response:
                if response.status_code >= 400:
                    yield _event({
                        "event": "error",
                        "message": f"TinyFish rejected the request (HTTP {response.status_code}). Check your API key, account access, and credits.",
                    })
                    return

                received_report = False
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    try:
                        event = json.loads(line[5:].strip())
                    except json.JSONDecodeError:
                        yield _event({"event": "error", "message": "TinyFish returned an invalid research event."})
                        return

                    if not isinstance(event, dict):
                        yield _event({"event": "error", "message": "TinyFish returned an invalid research event."})
                        return

                    if event.get("event") == "final_result":
                        received_report = True
                    elif event.get("event") == "error":
                        yield _event({
                            "event": "error",
                            "message": str(event.get("message") or "TinyFish research failed."),
                        })
                        return

                    yield _event(event)
                    if event.get("event") == "done":
                        if not received_report:
                            yield _event({"event": "error", "message": "TinyFish ended the run without a research report."})
                        return

                if not received_report:
                    yield _event({"event": "error", "message": "TinyFish ended the run without a research report."})
    except httpx.TimeoutException:
        yield _event({"event": "error", "message": "The TinyFish research request timed out. Please try again."})
    except httpx.RequestError:
        yield _event({"event": "error", "message": "Could not connect to TinyFish. Check the backend network and try again."})


@router.post("")
async def run_research(request: ResearchRequest):
    api_key = (settings.TINYFISH_API_KEY or "").strip()
    if not api_key or api_key == "your_tinyfish_api_key_here":
        raise HTTPException(
            status_code=503,
            detail="TinyFish is not configured. Set TINYFISH_API_KEY in backend/.env and restart the backend.",
        )

    return StreamingResponse(
        _stream_research(request.query, api_key),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
