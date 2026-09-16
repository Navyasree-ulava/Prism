"""POST /v1/chat/completions — OpenAI-compatible passthrough endpoint."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.model_registry import Model
from app.providers import get_provider
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/chat/completions", response_model=ChatResponse)
async def chat_completions(
    body: ChatRequest,
    session: AsyncSession = Depends(get_session),
) -> ChatResponse:
    # 1. Look up the model to find its provider.
    result = await session.execute(select(Model).where(Model.id == body.model))
    db_model = result.scalar_one_or_none()

    if db_model is None:
        raise HTTPException(
            status_code=404,
            detail=f"Model '{body.model}' not found in the registry.",
        )

    # 2. Resolve the provider adapter.
    try:
        provider = get_provider(db_model.provider)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # 3. Guard: verify the provider is properly configured.
    if not await provider.health_check():
        raise HTTPException(
            status_code=503,
            detail={
                "error": "provider_unavailable",
                "detail": (
                    f"{db_model.provider.upper()}_API_KEY is not configured. "
                    "Set the key in your .env file and restart the server."
                ),
            },
        )

    # 4. Delegate to the provider (non-streaming only in Phase 2).
    return await provider.generate(body)
