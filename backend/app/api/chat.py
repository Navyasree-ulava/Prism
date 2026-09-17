"""POST /v1/chat/completions — Phase 4: retry + fallback wired in."""
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
from app.reliability.fallback import FallbackError, call_with_fallback
from app.reliability.health_tracker import HealthTracker
from app.reliability.retry import with_retry
from app.routing.engine import RoutingResult, route
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    RoutingCandidate,
    RoutingInfo,
)

router = APIRouter()

# Module-level singleton — lives for the process lifetime (in-memory, no Redis).
_health_tracker = HealthTracker()

_EST_OUTPUT_TOKENS = 500


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_routing_info(
    result: RoutingResult,
    actual_model: object,
    latency_ms: int,
    fallback_used: bool = False,
) -> RoutingInfo:
    """Build the RoutingInfo response object.

    Uses *actual_model* (which may differ from ranked[0] when fallback occurs)
    to compute cost and set selected_model.
    """
    cost_usd = round(
        result.analysis.estimated_input_tokens / 1000 * actual_model.input_price_per_1k
        + _EST_OUTPUT_TOKENS / 1000 * actual_model.output_price_per_1k,
        6,
    )
    return RoutingInfo(
        selected_model=actual_model.id,
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
    """OpenAI-compatible chat completions with intelligent routing + reliability."""
    strategy = request.headers.get(
        "x-routing-strategy", settings.default_routing_strategy
    )

    # 1. Run routing engine (health_tracker wired in for Phase 4 filtering).
    messages_dicts = [m.model_dump() for m in body.messages]
    try:
        routing_result = await route(
            messages_dicts, strategy, session, health_tracker=_health_tracker
        )
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # 2. Dispatch: non-streaming uses fallback pipeline; streaming has its own path.
    if body.stream:
        return _make_streaming_response(body, routing_result)
    return await _non_streaming(body, routing_result)


# ---------------------------------------------------------------------------
# Non-streaming path  (retry + fallback)
# ---------------------------------------------------------------------------


async def _non_streaming(
    body: ChatRequest,
    routing_result: RoutingResult,
) -> ChatResponse:
    t0 = time.monotonic()
    try:
        response, actual_model, fallback_used = await call_with_fallback(
            routing_result=routing_result,
            request=body,
            get_provider_fn=get_provider,
            health_tracker=_health_tracker,
        )
    except FallbackError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    latency_ms = int((time.monotonic() - t0) * 1000)
    routing_info = _build_routing_info(routing_result, actual_model, latency_ms, fallback_used)
    return response.model_copy(update={"routing": routing_info})


# ---------------------------------------------------------------------------
# Streaming path — standard OpenAI SSE + terminal routing_metadata event
# Note: streaming retries at the chunk level are complex; we do a single
# attempt for streaming and fall back to non-streaming on failure.
# ---------------------------------------------------------------------------


def _make_streaming_response(
    body: ChatRequest,
    routing_result: RoutingResult,
) -> StreamingResponse:
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    primary_model = routing_result.selected

    async def event_stream() -> AsyncIterator[str]:
        t0 = time.monotonic()
        actual_model = primary_model
        fallback_used = False

        # Resolve provider; attempt stream with retry on primary.
        provider = get_provider(primary_model.provider)
        stream_request = body.model_copy(update={"model": primary_model.id})

        try:
            async for chunk in provider.stream(stream_request):
                if chunk:
                    data = json.dumps({
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "model": primary_model.id,
                        "choices": [{
                            "index": 0,
                            "delta": {"content": chunk},
                            "finish_reason": None,
                        }],
                    })
                    yield f"data: {data}\n\n"
            _health_tracker.record_success(primary_model.id)

        except Exception as exc:
            # Primary stream failed — attempt fallback via non-streaming generate().
            _health_tracker.record_failure(primary_model.id)

            # Find next healthy candidate.
            fallback_model = None
            for scored in routing_result.ranked[1:]:
                if _health_tracker.is_healthy(scored.model.id):
                    fallback_model = scored.model
                    break

            if fallback_model is None:
                error_event = json.dumps({"error": "all_providers_failed", "detail": str(exc)})
                yield f"event: error\ndata: {error_event}\n\n"
                yield "data: [DONE]\n\n"
                return

            # Emit a brief fallback notice chunk then generate from fallback.
            fallback_provider = get_provider(fallback_model.provider)
            fallback_request = body.model_copy(update={"model": fallback_model.id, "stream": False})
            try:
                fb_response = await with_retry(fallback_provider.generate, fallback_request)
                _health_tracker.record_success(fallback_model.id)
                actual_model = fallback_model
                fallback_used = True
                content = fb_response.choices[0].message.content if fb_response.choices else ""
                data = json.dumps({
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "model": fallback_model.id,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": content},
                        "finish_reason": None,
                    }],
                })
                yield f"data: {data}\n\n"
            except Exception as fb_exc:
                _health_tracker.record_failure(fallback_model.id)
                error_event = json.dumps({"error": "all_providers_failed", "detail": str(fb_exc)})
                yield f"event: error\ndata: {error_event}\n\n"
                yield "data: [DONE]\n\n"
                return

        latency_ms = int((time.monotonic() - t0) * 1000)

        # Final stop chunk.
        stop_data = json.dumps({
            "id": completion_id,
            "object": "chat.completion.chunk",
            "model": actual_model.id,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        })
        yield f"data: {stop_data}\n\n"

        # Terminal routing metadata event.
        routing_info = _build_routing_info(routing_result, actual_model, latency_ms, fallback_used)
        yield f"event: routing_metadata\ndata: {routing_info.model_dump_json()}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
