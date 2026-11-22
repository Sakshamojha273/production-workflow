"""Bearer-token (JWT) authentication for the API.

/api/auth/login and /api/auth/demo-login issue an HS256 JWT signed with
settings.SECRET_KEY; every other /api route requires it in an
``Authorization: Bearer <token>`` header (see app/api/__init__.py).
/health, / and the OpenAPI docs stay public.
"""
import logging
from typing import Dict

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import settings

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)


def secret_key_is_default() -> bool:
    key = settings.SECRET_KEY or ""
    return len(key) < 32 or "change-in-production" in key or "your-secret-key" in key


def warn_if_default_secret() -> None:
    if secret_key_is_default():
        logger.warning(
            "SECRET_KEY is a development default (or shorter than 32 chars). "
            "API tokens can be forged: set a long random SECRET_KEY in backend/.env before deploying."
        )


async def require_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> Dict:
    """FastAPI dependency: validate the bearer JWT and return its claims."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise unauthorized
    try:
        claims = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        unauthorized.detail = "Session expired or invalid token, please sign in again"
        raise unauthorized
    if not claims.get("sub"):
        raise unauthorized
    return claims
