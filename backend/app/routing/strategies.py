"""Static strategy weight presets for the scoring engine.

Four named strategies, each a dict of {metric: weight} that sum to 1.0.
Exact values from build spec §Phase 3 step 4.
"""

STRATEGIES: dict[str, dict[str, float]] = {
    "cost":     {"quality": 0.15, "capability": 0.25, "latency": 0.10, "cost": 0.50},
    "quality":  {"quality": 0.50, "capability": 0.30, "latency": 0.10, "cost": 0.10},
    "latency":  {"quality": 0.15, "capability": 0.20, "latency": 0.50, "cost": 0.15},
    "balanced": {"quality": 0.30, "capability": 0.30, "latency": 0.20, "cost": 0.20},
}

DEFAULT_STRATEGY = "balanced"
