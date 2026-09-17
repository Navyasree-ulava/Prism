"""API key authentication dependency."""
from fastapi import Header, HTTPException, status

from app.config import settings


async def verify_api_key(
    authorization: str | None = Header(default=None),
) -> None:
    """FastAPI dependency — enforces Bearer token auth against settings.api_key."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header. Use: Bearer <API_KEY>",
        )
    token = authorization.split(" ", 1)[1].strip()
    if token != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )
