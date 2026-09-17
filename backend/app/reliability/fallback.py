"""Fallback logic for the routing engine.

If the top-scored candidate fails after retries, ``call_with_fallback``
picks the next-highest-scored candidate from the already-computed ranked
list — without re-running the routing pipeline.

Rules (from BUILD SPEC § 4.4)
------------------------------
- Use the ranked list produced by the routing engine directly.
- The fallback candidate must still satisfy ``required_capabilities``.
- Mark ``fallback_used = True`` in the result.
- One hop only: if the fallback also fails, propagate the error.
- Record failures/successes in the health tracker.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.reliability.health_tracker import HealthTracker
from app.reliability.retry import with_retry
from app.routing.engine import RoutingResult
from app.schemas.chat import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)


class FallbackError(RuntimeError):
    """Raised when both primary and fallback candidates fail."""


async def call_with_fallback(
    routing_result: RoutingResult,
    request: ChatRequest,
    get_provider_fn: Any,
    health_tracker: HealthTracker,
) -> tuple[ChatResponse, Any, bool]:
    """Attempt primary model; fall back to next ranked candidate on failure.

    Args:
        routing_result:  Result from ``routing.engine.route()``.
        request:         The incoming chat request.
        get_provider_fn: ``providers.get_provider`` function.
        health_tracker:  Shared ``HealthTracker`` instance.

    Returns:
        Tuple of ``(response, model_used, fallback_used)``.

    Raises:
        FallbackError: if both primary and fallback candidates fail.
        ValueError: if no fallback candidate is available.
    """
    ranked = routing_result.ranked
    required = routing_result.analysis.required_capabilities

    # ------------------------------------------------------------------ #
    # Primary attempt                                                      #
    # ------------------------------------------------------------------ #
    primary = ranked[0].model
    primary_provider = get_provider_fn(primary.provider)
    primary_request = request.model_copy(update={"model": primary.id})

    try:
        response = await with_retry(primary_provider.generate, primary_request)
        health_tracker.record_success(primary.id)
        return response, primary, False
    except Exception as primary_exc:
        health_tracker.record_failure(primary.id)
        logger.warning(
            "Primary model '%s' failed after retries: %s. Attempting fallback.",
            primary.id,
            primary_exc,
        )

    # ------------------------------------------------------------------ #
    # Fallback: pick the next eligible candidate from the ranked list     #
    # ------------------------------------------------------------------ #
    fallback_model = None
    for scored in ranked[1:]:
        candidate = scored.model
        # The ranked list is already capability-filtered by the routing engine.
        # Only skip candidates the health tracker currently considers unavailable.
        if not health_tracker.is_healthy(candidate.id):
            continue
        fallback_model = candidate
        break

    if fallback_model is None:
        raise FallbackError(
            f"Primary model '{primary.id}' failed and no eligible fallback candidate "
            "is available in the ranked list."
        )

    fallback_provider = get_provider_fn(fallback_model.provider)
    fallback_request = request.model_copy(update={"model": fallback_model.id})

    try:
        response = await with_retry(fallback_provider.generate, fallback_request)
        health_tracker.record_success(fallback_model.id)
        logger.info(
            "Fallback successful: used '%s' after '%s' failed.",
            fallback_model.id,
            primary.id,
        )
        return response, fallback_model, True
    except Exception as fallback_exc:
        health_tracker.record_failure(fallback_model.id)
        raise FallbackError(
            f"Both primary '{primary.id}' and fallback '{fallback_model.id}' "
            f"failed. Last error: {fallback_exc}"
        ) from fallback_exc
