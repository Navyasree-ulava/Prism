"""Request logging service — writes rows to requests, routing_decisions, model_runs.

Called from api/chat.py after every successful (or failed) provider dispatch.
All writes are fire-and-forget relative to the HTTP response; errors are logged
but never bubble up to the user.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model_run import ModelRun
from app.models.request_log import Request
from app.models.routing_decision import RoutingDecision
from app.routing.engine import RoutingResult
from app.schemas.chat import ChatResponse

logger = logging.getLogger(__name__)


async def log_request(
    session: AsyncSession,
    routing_result: RoutingResult,
    response: ChatResponse | None,
    actual_model: Any,        # Model ORM instance (may differ from ranked[0] on fallback)
    latency_ms: int,
    fallback_used: bool,
    strategy: str,
    cost_usd: float,
    status: str = "success",  # "success" | "error" | "timeout"
) -> None:
    """Persist one full request cycle to the database.

    Writes three rows atomically:
      - requests          — prompt metadata + strategy
      - routing_decisions — selected model, candidates, confidence
      - model_runs        — token counts, latency, cost, status, fallback flag

    Errors are caught and logged — never raised to the caller.
    """
    try:
        request_id = uuid.uuid4()
        usage = (response.usage if response else {}) or {}

        # ── requests ──────────────────────────────────────────────────────── #
        analysis = routing_result.analysis
        prompt_meta = {
            "task_type": analysis.task_type,
            "complexity": analysis.complexity,
            "required_capabilities": analysis.required_capabilities,
            "context_requirement": analysis.context_requirement,
            "estimated_input_tokens": analysis.estimated_input_tokens,
            "confidence": analysis.confidence,
        }

        request_row = Request(
            id=request_id,
            user_id=None,       # No multi-tenant auth in MVP scope
            prompt_meta=prompt_meta,
            strategy=strategy,
        )
        session.add(request_row)
        # Flush the parent row first so FK-dependent child rows can reference it.
        # Without this, SQLAlchemy's unit-of-work may emit model_runs/routing_decisions
        # INSERTs before requests, causing a ForeignKeyViolationError on PostgreSQL.
        await session.flush([request_row])

        # ── routing_decisions ──────────────────────────────────────────────── #
        candidates_json = [
            {"model_id": r.model.id, "score": round(r.score, 4)}
            for r in routing_result.ranked
        ]
        decision_row = RoutingDecision(
            id=uuid.uuid4(),
            request_id=request_id,
            selected_model=actual_model.id,
            reason=routing_result.reason,
            candidates_json=candidates_json,
            confidence=round(analysis.confidence, 4),
        )
        session.add(decision_row)

        # ── model_runs ─────────────────────────────────────────────────────── #
        tokens_in = usage.get("prompt_tokens") or analysis.estimated_input_tokens
        tokens_out = usage.get("completion_tokens", 0)

        run_row = ModelRun(
            id=uuid.uuid4(),
            request_id=request_id,
            model_id=actual_model.id,
            latency_ms=latency_ms,
            tokens_in=int(tokens_in),
            tokens_out=int(tokens_out),
            cost_usd=round(cost_usd, 6),
            status=status,
            fallback_used=fallback_used,
        )
        session.add(run_row)

        await session.commit()
        logger.debug(
            "Logged request %s → model=%s cost=$%.6f latency=%dms fallback=%s",
            request_id, actual_model.id, cost_usd, latency_ms, fallback_used,
        )

    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to log request to DB: %s", exc, exc_info=True)
        await session.rollback()
