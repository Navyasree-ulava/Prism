"""Unit tests for routing/scorer.py — hand-computed expected values."""
from dataclasses import dataclass

import pytest

from app.routing.scorer import ScoredModel, score_candidates
from app.routing.strategies import STRATEGIES


# ---------------------------------------------------------------------------
# Helpers — plain dataclass stub (avoids SQLAlchemy instrumentation at import)
# ---------------------------------------------------------------------------


@dataclass
class _Model:
    id: str
    quality_score: float
    avg_latency_ms: int
    input_price_per_1k: float
    output_price_per_1k: float
    capabilities: list


# Three representative models matching the seeded data
CHEAP_FAST = _Model(
    id="llama3-8b-8192",
    quality_score=0.58,
    avg_latency_ms=350,
    input_price_per_1k=0.00005,
    output_price_per_1k=0.00008,
    capabilities=["general", "qa"],
)
EXPENSIVE_SLOW = _Model(
    id="gpt-4o-mini",
    quality_score=0.72,
    avg_latency_ms=800,
    input_price_per_1k=0.00015,
    output_price_per_1k=0.0006,
    capabilities=["general", "coding", "reasoning", "qa"],
)
QUALITY_MID = _Model(
    id="claude-3-haiku",
    quality_score=0.78,
    avg_latency_ms=950,
    input_price_per_1k=0.00025,
    output_price_per_1k=0.00125,
    capabilities=["general", "summarization", "coding", "reasoning"],
)



# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestScoreCandidates:
    def test_empty_candidates_returns_empty(self):
        assert score_candidates([], [], 100, STRATEGIES["balanced"]) == []

    def test_results_sorted_descending(self):
        results = score_candidates(
            [CHEAP_FAST, EXPENSIVE_SLOW, QUALITY_MID],
            ["general"],
            500,
            STRATEGIES["balanced"],
        )
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_cost_strategy_prefers_cheapest(self):
        """With cost weight=0.50, the cheapest model should win."""
        results = score_candidates(
            [CHEAP_FAST, EXPENSIVE_SLOW, QUALITY_MID],
            [],
            1000,
            STRATEGIES["cost"],
        )
        assert results[0].model.id == "llama3-8b-8192"

    def test_quality_strategy_picks_higher_quality_when_other_metrics_equal(self):
        """Isolate quality: identical latency, cost, caps — only quality_score differs."""
        from dataclasses import replace

        low_q = _Model(
            id="low-q", quality_score=0.50, avg_latency_ms=500,
            input_price_per_1k=0.0001, output_price_per_1k=0.0003,
            capabilities=["general"],
        )
        high_q = _Model(
            id="high-q", quality_score=0.90, avg_latency_ms=500,
            input_price_per_1k=0.0001, output_price_per_1k=0.0003,
            capabilities=["general"],
        )
        results = score_candidates([low_q, high_q], [], 1000, STRATEGIES["quality"])
        assert results[0].model.id == "high-q"

    def test_latency_strategy_prefers_fastest(self):
        results = score_candidates(
            [CHEAP_FAST, EXPENSIVE_SLOW, QUALITY_MID],
            [],
            1000,
            STRATEGIES["latency"],
        )
        assert results[0].model.id == "llama3-8b-8192"

    def test_single_candidate_latency_cost_zero(self):
        """With one candidate, max==self so latency_score and cost_score are 0.0."""
        results = score_candidates([CHEAP_FAST], ["general"], 100, STRATEGIES["balanced"])
        assert len(results) == 1
        assert results[0].breakdown["latency"] == 0.0
        assert results[0].breakdown["cost"] == 0.0

    def test_full_capability_match_scores_one(self):
        results = score_candidates(
            [CHEAP_FAST], ["general", "qa"], 100, STRATEGIES["balanced"]
        )
        assert results[0].breakdown["capability"] == 1.0

    def test_partial_capability_match(self):
        """Model has 1 of 2 required caps → 0.5."""
        results = score_candidates(
            [CHEAP_FAST], ["general", "coding"], 100, STRATEGIES["balanced"]
        )
        assert results[0].breakdown["capability"] == 0.5

    def test_no_required_caps_gives_full_cap_score(self):
        results = score_candidates([CHEAP_FAST], [], 100, STRATEGIES["balanced"])
        assert results[0].breakdown["capability"] == 1.0

    def test_score_in_valid_range(self):
        results = score_candidates(
            [CHEAP_FAST, EXPENSIVE_SLOW, QUALITY_MID],
            ["general"],
            500,
            STRATEGIES["balanced"],
        )
        for r in results:
            assert 0.0 <= r.score <= 1.0

    def test_breakdown_keys_present(self):
        results = score_candidates([CHEAP_FAST], [], 100, STRATEGIES["balanced"])
        assert set(results[0].breakdown.keys()) == {"quality", "capability", "latency", "cost"}

    def test_equal_score_secondary_tie_break_prefers_lower_latency(self):
        """When two candidates have identical final scores, lower latency candidate wins."""
        # Both models have identical quality, price, and caps. Latency differs.
        # But wait: if latency differs, latency_score would differ unless weight["latency"] is 0.
        # Using a custom weights dict with latency weight = 0 isolates the tie-break:
        custom_weights = {"quality": 1.0, "capability": 0.0, "latency": 0.0, "cost": 0.0}
        fast = _Model(
            id="fast-model", quality_score=0.80, avg_latency_ms=200,
            input_price_per_1k=0.001, output_price_per_1k=0.002, capabilities=["general"],
        )
        slow = _Model(
            id="slow-model", quality_score=0.80, avg_latency_ms=800,
            input_price_per_1k=0.001, output_price_per_1k=0.002, capabilities=["general"],
        )
        # Passing [slow, fast] should still rank fast first due to secondary tie-breaker
        results1 = score_candidates([slow, fast], ["general"], 100, custom_weights)
        assert results1[0].score == results1[1].score
        assert results1[0].model.id == "fast-model"
        assert results1[1].model.id == "slow-model"

        # Reversed input order should produce identical ranking
        results2 = score_candidates([fast, slow], ["general"], 100, custom_weights)
        assert [r.model.id for r in results2] == ["fast-model", "slow-model"]

    def test_equal_score_and_latency_tertiary_tie_break_alphabetical_id(self):
        """When score and latency are both identical, alphabetical model ID is deterministic."""
        custom_weights = {"quality": 1.0, "capability": 0.0, "latency": 0.0, "cost": 0.0}
        model_b = _Model(
            id="model-b", quality_score=0.80, avg_latency_ms=500,
            input_price_per_1k=0.001, output_price_per_1k=0.002, capabilities=["general"],
        )
        model_a = _Model(
            id="model-a", quality_score=0.80, avg_latency_ms=500,
            input_price_per_1k=0.001, output_price_per_1k=0.002, capabilities=["general"],
        )
        # Regardless of input order, model-a must come before model-b
        res1 = score_candidates([model_b, model_a], ["general"], 100, custom_weights)
        res2 = score_candidates([model_a, model_b], ["general"], 100, custom_weights)
        assert [r.model.id for r in res1] == ["model-a", "model-b"]
        assert [r.model.id for r in res2] == ["model-a", "model-b"]
