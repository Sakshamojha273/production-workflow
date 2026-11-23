import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings

router = APIRouter()

TINYFISH_SEARCH_URL = "https://api.search.tinyfish.ai"


class SearchRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(min_length=1, max_length=2_000)


@router.post("")
async def search_web(request: SearchRequest):
    api_key = (settings.TINYFISH_API_KEY or "").strip()
    if not api_key or api_key == "your_tinyfish_api_key_here":
        raise HTTPException(
            status_code=503,
            detail="TinyFish is not configured. Set TINYFISH_API_KEY in backend/.env and restart the backend.",
        )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                TINYFISH_SEARCH_URL,
                params={"query": request.query},
                headers={"X-API-Key": api_key},
            )
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="TinyFish Search timed out. Please try again.") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="Could not connect to TinyFish Search.") from exc

    if response.is_error:
        messages = {
            400: "TinyFish rejected the search query.",
            401: "TinyFish rejected the API key. Check TINYFISH_API_KEY in backend/.env.",
            402: "TinyFish Search allowance or account credits are exhausted.",
            403: "TinyFish Search is not enabled for this account.",
            404: "TinyFish Search is unavailable at the configured endpoint.",
            429: "TinyFish Search rate limit reached. Please wait before trying again.",
        }
        detail = messages.get(response.status_code, f"TinyFish Search failed (HTTP {response.status_code}).")
        raise HTTPException(status_code=502, detail=detail)

    try:
        result = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="TinyFish Search returned an invalid response.") from exc

    if not isinstance(result, dict) or not isinstance(result.get("results"), list):
        raise HTTPException(status_code=502, detail="TinyFish Search returned an unexpected response.")

    return result
