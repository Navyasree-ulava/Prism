"""Weighted scoring engine for routing candidates.

All four metrics are normalised to [0, 1] before weighting so that
different units (USD, ms, ratio) are comparable.

Normalisation formulas (from build spec §Phase 3 step 5):
  quality_score    → used as-is (already 0–1 from DB seed)
  capability_match → matched / required,  1.0 if full superset / no requirements
  latency_score    → 1 - (model.avg_latency_ms / max_latency_among_candidates)
  cost_score       → 1 - (est_cost / max_est_cost_among_candidates)

Final: Σ weight_i × normalised_i
"""
from __future__ import annotations

from dataclasses import dataclass

from app.models.model_registry import Model
from app.routing.filters import _to_list

# Estimated output tokens used for cost estimation when we don't yet know real usage.
_EST_OUTPUT_TOKENS = 500


@dataclass
class ScoredModel:
    model: Model
    score: float
    breakdown: dict[str, float]  # per-metric normalised scores


def score_candidates(
    candidates: list[Model],
    required_capabilities: list[str],
    estimated_input_tokens: int,
    weights: dict[str, float],
) -> list[ScoredModel]:
    """Score and rank *candidates*; return sorted list (highest score first)."""
    if not candidates:
        return []

    # Estimated cost per model
    est_costs = {
        m.id: (
            estimated_input_tokens / 1000 * m.input_price_per_1k
            + _EST_OUTPUT_TOKENS / 1000 * m.output_price_per_1k
        )
        for m in candidates
    }

    max_cost = max(est_costs.values()) or 1.0
    max_latency = max(m.avg_latency_ms for m in candidates) or 1

    results: list[ScoredModel] = []
    for m in candidates:
        # Capability match ratio
        if required_capabilities:
            model_caps = _to_list(m.capabilities)
            matched = sum(1 for c in required_capabilities if c in model_caps)
            cap_score = matched / len(required_capabilities)
        else:
            cap_score = 1.0

        latency_score = 1.0 - (m.avg_latency_ms / max_latency)
        cost_score = 1.0 - (est_costs[m.id] / max_cost)
        quality = m.quality_score

        final = (
            weights["quality"]    * quality
            + weights["capability"] * cap_score
            + weights["latency"]    * latency_score
            + weights["cost"]       * cost_score
        )

        results.append(
            ScoredModel(
                model=m,
                score=round(final, 4),
                breakdown={
                    "quality":    round(quality, 4),
                    "capability": round(cap_score, 4),
                    "latency":    round(latency_score, 4),
                    "cost":       round(cost_score, 4),
                },
            )
        )

    # Deterministic candidate ranking:
    # 1. Primary: Score descending (higher composite score is better: -x.score)
    # 2. Secondary tie-breaker: Average latency ascending (faster model preferred: x.model.avg_latency_ms)
    # 3. Tertiary tie-breaker: Model ID ascending (lexicographical order guarantees 100% determinism)
    return sorted(results, key=lambda x: (-x.score, x.model.avg_latency_ms, x.model.id))
