"""Capability and health filters for routing candidates.

Both functions are pure (no I/O) and operate on the in-memory candidate list
produced by routing/registry.py.
"""
from __future__ import annotations

import ast
import json

from app.models.model_registry import Model


def _to_list(caps: list[str] | str | None) -> list[str]:
    """Normalise capabilities to a Python list.

    PostgreSQL ARRAY → already a list.
    SQLite (tests) → stored as a JSON/Python-repr string; parse it.
    """
    if caps is None:
        return []
    if isinstance(caps, list):
        return caps
    # Try JSON first (double-quoted), then Python repr (single-quoted).
    try:
        return json.loads(caps)
    except (json.JSONDecodeError, TypeError):
        pass
    try:
        result = ast.literal_eval(caps)
        return result if isinstance(result, list) else []
    except (ValueError, SyntaxError):
        return []


def filter_by_capability(
    candidates: list[Model],
    required: list[str],
) -> list[Model]:
    """Keep only models whose capability set is a superset of *required*."""
    if not required:
        return candidates
    return [
        m for m in candidates
        if all(cap in _to_list(m.capabilities) for cap in required)
    ]


def filter_by_health(
    candidates: list[Model],
    health_tracker=None,
) -> list[Model]:
    """Exclude models that the health tracker considers unavailable.

    If *health_tracker* is None (Phase 2/3 stub), every candidate passes.
    Phase 4 wires in the real HealthTracker.
    """
    if health_tracker is None:
        return candidates
    return [m for m in candidates if health_tracker.is_healthy(m.id)]
