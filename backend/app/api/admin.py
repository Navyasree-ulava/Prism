"""Admin endpoints — Phase 5.

All endpoints read from Postgres and return aggregated stats or individual
request records. No auth on admin endpoints per MVP scope (single API key
protects /v1/* only).

Endpoints
---------
GET /admin/routing-stats       — global aggregate metrics
GET /admin/models-performance  — per-model breakdown
GET /admin/decisions?limit=50  — paginated recent requests list
GET /admin/decisions/{id}      — full record: analyzer + routing + run detail
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /admin/routing-stats
# ---------------------------------------------------------------------------


@router.get("/routing-stats")
async def routing_stats(session: AsyncSession = Depends(get_session)):
    """Global aggregates across all requests.

    Returns:
        total_requests, success_rate, avg_latency_ms, total_cost_usd,
        fallback_rate, error_rate
    """
    raw = await session.execute(
        text("""
            SELECT
                COUNT(*)                                            AS total_requests,
                AVG(latency_ms)                                     AS avg_latency_ms,
                COALESCE(SUM(cost_usd), 0)                          AS total_cost_usd,
                COALESCE(SUM(CASE WHEN fallback_used THEN 1 ELSE 0 END), 0)
                                                                    AS fallback_count,
                COALESCE(SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END), 0)
                                                                    AS success_count,
                COALESCE(SUM(CASE WHEN status = 'error'   THEN 1 ELSE 0 END), 0)
                                                                    AS error_count
            FROM model_runs
        """)
    )
    row = raw.mappings().one()

    total = int(row["total_requests"]) or 0
    success_count = int(row["success_count"]) or 0
    error_count = int(row["error_count"]) or 0
    fallback_count = int(row["fallback_count"]) or 0

    return {
        "total_requests": total,
        "success_rate": round(success_count / total, 4) if total else 0.0,
        "error_rate": round(error_count / total, 4) if total else 0.0,
        "avg_latency_ms": round(float(row["avg_latency_ms"] or 0), 1),
        "total_cost_usd": round(float(row["total_cost_usd"] or 0), 6),
        "fallback_rate": round(fallback_count / total, 4) if total else 0.0,
    }


# ---------------------------------------------------------------------------
# GET /admin/models-performance
# ---------------------------------------------------------------------------


@router.get("/models-performance")
async def models_performance(session: AsyncSession = Depends(get_session)):
    """Per-model breakdown of requests, success rate, latency, and cost."""
    raw = await session.execute(
        text("""
            SELECT
                model_id,
                COUNT(*)                                                     AS total_requests,
                COALESCE(SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END), 0)
                                                                             AS success_count,
                AVG(latency_ms)                                              AS avg_latency_ms,
                COALESCE(SUM(cost_usd), 0)                                   AS total_cost_usd
            FROM model_runs
            GROUP BY model_id
            ORDER BY total_requests DESC
        """)
    )
    rows = raw.mappings().all()

    return [
        {
            "model_id": row["model_id"],
            "total_requests": int(row["total_requests"]),
            "success_rate": round(
                int(row["success_count"]) / int(row["total_requests"]), 4
            ) if row["total_requests"] else 0.0,
            "avg_latency_ms": round(float(row["avg_latency_ms"] or 0), 1),
            "total_cost_usd": round(float(row["total_cost_usd"] or 0), 6),
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# GET /admin/decisions?limit=50
# ---------------------------------------------------------------------------


@router.get("/decisions")
async def list_decisions(
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    """Paginated list of recent request records.

    Returns id, timestamp, selected_model, status, cost_usd for each.
    """
    raw = await session.execute(
        text("""
            SELECT
                r.id            AS request_id,
                r.created_at    AS created_at,
                rd.selected_model,
                mr.status,
                mr.cost_usd,
                mr.latency_ms,
                mr.fallback_used
            FROM requests r
            JOIN routing_decisions rd ON rd.request_id = r.id
            JOIN model_runs        mr ON mr.request_id = r.id
            ORDER BY r.created_at DESC
            LIMIT :limit
        """),
        {"limit": limit},
    )
    rows = raw.mappings().all()

    def _fmt_dt(val) -> str | None:
        """Return ISO string regardless of whether the DB gave us a str or datetime."""
        if val is None:
            return None
        return val.isoformat() if hasattr(val, "isoformat") else str(val)

    return [
        {
            "request_id": str(row["request_id"]),
            "created_at": _fmt_dt(row["created_at"]),
            "selected_model": row["selected_model"],
            "status": row["status"],
            "cost_usd": round(float(row["cost_usd"] or 0), 6),
            "latency_ms": row["latency_ms"],
            "fallback_used": bool(row["fallback_used"]),
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# GET /admin/decisions/{request_id}
# ---------------------------------------------------------------------------


@router.get("/decisions/{request_id}")
async def get_decision(
    request_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Full record for a single request — analyzer output + routing decision + run detail.

    This is the data source for the Request Inspector page.
    """
    try:
        req_uuid = uuid.UUID(request_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID format for request_id")

    # Use raw SQL for all lookups so SQLAlchemy doesn't try to coerce the
    # string id through its UUID type processor (which breaks on SQLite).
    req_str = str(req_uuid)

    req_raw = await session.execute(
        text("SELECT id, user_id, prompt_meta, strategy, created_at FROM requests WHERE id = :id"),
        {"id": req_str},
    )
    req_row = req_raw.mappings().one_or_none()
    if req_row is None:
        raise HTTPException(status_code=404, detail=f"Request '{request_id}' not found")

    # routing_decisions
    rd_raw = await session.execute(
        text("SELECT selected_model, reason, confidence, candidates_json FROM routing_decisions WHERE request_id = :id"),
        {"id": req_str},
    )
    rd_row = rd_raw.mappings().one_or_none()

    # model_runs
    mr_raw = await session.execute(
        text("SELECT model_id, latency_ms, tokens_in, tokens_out, cost_usd, status, fallback_used FROM model_runs WHERE request_id = :id"),
        {"id": req_str},
    )
    mr_row = mr_raw.mappings().one_or_none()

    def _safe_dt(val) -> str | None:
        if val is None:
            return None
        return val.isoformat() if hasattr(val, "isoformat") else str(val)

    import json as _json  # noqa: PLC0415

    def _parse_json(val):
        """Parse candidates_json which may be a string (SQLite) or already parsed (Postgres)."""
        if val is None:
            return []
        if isinstance(val, str):
            try:
                return _json.loads(val)
            except Exception:
                return []
        return val

    return {
        "request_id": req_str,
        "created_at": _safe_dt(req_row["created_at"]),
        "strategy": req_row["strategy"],
        "prompt_meta": req_row["prompt_meta"],
        "routing_decision": {
            "selected_model": rd_row["selected_model"] if rd_row else None,
            "reason": rd_row["reason"] if rd_row else None,
            "confidence": rd_row["confidence"] if rd_row else None,
            "candidates": _parse_json(rd_row["candidates_json"]) if rd_row else [],
        },
        "model_run": {
            "model_id": mr_row["model_id"] if mr_row else None,
            "latency_ms": mr_row["latency_ms"] if mr_row else None,
            "tokens_in": mr_row["tokens_in"] if mr_row else None,
            "tokens_out": mr_row["tokens_out"] if mr_row else None,
            "cost_usd": round(float(mr_row["cost_usd"] or 0), 6) if mr_row else None,
            "status": mr_row["status"] if mr_row else None,
            "fallback_used": bool(mr_row["fallback_used"]) if mr_row else False,
        },
    }
