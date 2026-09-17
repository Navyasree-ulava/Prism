"""Routing engine — orchestrates: analyze → filter → score → select.

Returns a RoutingResult with the selected model, full ranked list, and
a human-readable reason string.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.analyzer.heuristic_analyzer import AnalysisResult, analyze
from app.routing.filters import filter_by_capability, filter_by_health
from app.routing.registry import load_active_models
from app.routing.scorer import ScoredModel, score_candidates
from app.routing.strategies import DEFAULT_STRATEGY, STRATEGIES

_FACTOR_LABELS: dict[str, str] = {
    "cost":       "cost efficiency",
    "quality":    "output quality",
    "latency":    "response speed",
    "capability": "capability match",
}


@dataclass
class RoutingResult:
    selected: object          # Model instance
    analysis: AnalysisResult
    ranked: list[ScoredModel]
    strategy: str
    reason: str


def _dominant_factor(weights: dict[str, float]) -> str:
    """Return the metric key with the highest weight."""
    return max(weights, key=lambda k: weights[k])


def _build_reason(strategy: str) -> str:
    weights = STRATEGIES[strategy]
    dominant = _dominant_factor(weights)
    label = _FACTOR_LABELS.get(dominant, dominant)
    return f"Best {label} match given '{strategy}' strategy."


async def route(
    messages: list[dict],
    strategy: str,
    session: AsyncSession,
    health_tracker=None,
) -> RoutingResult:
    """Run the full routing pipeline and return the selected model + ranking.

    Args:
        messages:       OpenAI-format message list (used for prompt analysis).
        strategy:       One of cost | quality | latency | balanced.
        session:        Active DB session (used to load candidate models).
        health_tracker: Optional Phase-4 health tracker; None = all healthy.

    Returns:
        RoutingResult with selected model and full ranked candidate list.

    Raises:
        ValueError: if no eligible candidates remain after all filters.
    """
    if strategy not in STRATEGIES:
        strategy = DEFAULT_STRATEGY

    weights = STRATEGIES[strategy]

    # Extract user-facing prompt for analysis (concatenate all user turns).
    prompt = " ".join(
        m["content"] for m in messages if m.get("role") == "user"
    )

    analysis = analyze(prompt)

    # Load all active models from DB.
    candidates = await load_active_models(session)

    # Apply capability filter; fall back to no filter if nothing matches.
    filtered = filter_by_capability(candidates, analysis.required_capabilities)
    if not filtered:
        filtered = candidates  # graceful degradation

    filtered = filter_by_health(filtered, health_tracker)

    if not filtered:
        raise ValueError(
            "No eligible candidates after filtering. "
            "Check model registry or health tracker state."
        )

    ranked = score_candidates(
        filtered, analysis.required_capabilities, analysis.estimated_input_tokens, weights
    )

    return RoutingResult(
        selected=ranked[0].model,
        analysis=analysis,
        ranked=ranked,
        strategy=strategy,
        reason=_build_reason(strategy),
    )
