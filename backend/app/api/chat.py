"""POST /v1/chat/completions — Phase 3 routing engine + streaming."""
from __future__ import annotations

import json
import time
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import verify_api_key
from app.config import settings
from app.db import get_session
from app.providers import get_provider
from app.routing.engine import RoutingResult, route
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    RoutingCandidate,
    RoutingInfo,
)

router = APIRouter()

_EST_OUTPUT_TOKENS = 500


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_routing_info(
    result: RoutingResult,
    latency_ms: int,
    fallback_used: bool = False,
) -> RoutingInfo:
    top = result.ranked[0]
    cost_usd = round(
        result.analysis.estimated_input_tokens / 1000 * top.model.input_price_per_1k
        + _EST_OUTPUT_TOKENS / 1000 * top.model.output_price_per_1k,
        6,
    )
    return RoutingInfo(
        selected_model=top.model.id,
        strategy=result.strategy,
        reason=result.reason,
        confidence=result.analysis.confidence,
        candidates=[
            RoutingCandidate(model=r.model.id, score=r.score)
            for r in result.ranked
        ],
        fallback_used=fallback_used,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/chat/completions")
async def chat_completions(
    body: ChatRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(verify_api_key),
):
    """OpenAI-compatible chat completions with intelligent routing."""
    strategy = request.headers.get(
        "x-routing-strategy", settings.default_routing_strategy
    )

    # 1. Run routing engine.
    messages_dicts = [m.model_dump() for m in body.messages]
    try:
        routing_result = await route(messages_dicts, strategy, session)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    selected = routing_result.selected

    # 2. Resolve provider adapter.
    try:
        provider = get_provider(selected.provider)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # 3. Guard: provider key configured?
    if not await provider.health_check():
        raise HTTPException(
            status_code=503,
            detail={
                "error": "provider_unavailable",
                "detail": (
                    f"{selected.provider.upper()}_API_KEY is not configured. "
                    "Set the key in your .env file and restart the server."
                ),
            },
        )

    # 4. Build provider-level request (override model with engine selection).
    provider_request = body.model_copy(update={"model": selected.id})

    # 5. Dispatch.
    if body.stream:
        return _make_streaming_response(provider_request, provider, routing_result)
    return await _non_streaming(provider_request, provider, routing_result)


# ---------------------------------------------------------------------------
# Non-streaming path
# ---------------------------------------------------------------------------


async def _non_streaming(
    body: ChatRequest,
    provider,
    routing_result: RoutingResult,
) -> ChatResponse:
    t0 = time.monotonic()
    response = await provider.generate(body)
    latency_ms = int((time.monotonic() - t0) * 1000)
    routing_info = _build_routing_info(routing_result, latency_ms)
    return response.model_copy(update={"routing": routing_info})


# ---------------------------------------------------------------------------
# Streaming path — standard OpenAI SSE + terminal routing_metadata event
# ---------------------------------------------------------------------------


def _make_streaming_response(
    body: ChatRequest,
    provider,
    routing_result: RoutingResult,
) -> StreamingResponse:
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    model_id = routing_result.selected.id

    async def event_stream() -> AsyncIterator[str]:
        t0 = time.monotonic()

        async for chunk in provider.stream(body):
            if chunk:
                data = json.dumps({
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "model": model_id,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": chunk},
                        "finish_reason": None,
                    }],
                })
                yield f"data: {data}\n\n"

        latency_ms = int((time.monotonic() - t0) * 1000)

        # Final stop chunk.
        stop_data = json.dumps({
            "id": completion_id,
            "object": "chat.completion.chunk",
            "model": model_id,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        })
        yield f"data: {stop_data}\n\n"

        # Terminal routing metadata event.
        routing_info = _build_routing_info(routing_result, latency_ms)
        yield f"event: routing_metadata\ndata: {routing_info.model_dump_json()}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
