"""Phase 8 scope guards — enforce the build spec's Explicit Non-Goals list.

The spec says: "Do not add, even if it seems like best practice: rate limiting,
Redis, multi-state circuit-breaker FSM, OAuth/RBAC, Prometheus/Grafana/OpenTelemetry,
Kubernetes, Terraform, multi-region, adaptive/ML-based routing, load-testing infra."

These tests fail if any of those leak into the project later.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
FRONTEND_ROOT = REPO_ROOT / "frontend"

# Forbidden dependency names (substring match against declared dependencies).
FORBIDDEN_DEPS = [
    "redis",
    "aioredis",
    "slowapi",
    "limits",           # rate-limiting library
    "ratelimit",
    "prometheus",
    "opentelemetry",
    "grafana",
    "kubernetes",
    "terraform",
    "authlib",
    "python-jose",
    "pyjwt",
]

# Forbidden imports anywhere in backend source (app/ + eval/, not tests).
FORBIDDEN_IMPORTS = [
    r"\bimport redis\b",
    r"\bfrom redis\b",
    r"\bslowapi\b",
    r"\bprometheus_client\b",
    r"\bopentelemetry\b",
]


def _pyproject() -> str:
    return (BACKEND_ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_no_forbidden_python_dependencies():
    text = _pyproject().lower()
    found = [dep for dep in FORBIDDEN_DEPS if dep in text]
    assert not found, f"Forbidden dependencies declared in pyproject.toml: {found}"


def test_no_forbidden_frontend_dependencies():
    pkg = (FRONTEND_ROOT / "package.json").read_text(encoding="utf-8").lower()
    found = [dep for dep in ("redis", "prometheus", "grafana") if f'"{dep}' in pkg]
    assert not found, f"Forbidden dependencies declared in package.json: {found}"


def test_no_forbidden_imports_in_backend_source():
    offenders: list[str] = []
    for py in list((BACKEND_ROOT / "app").rglob("*.py")) + list((BACKEND_ROOT / "eval").rglob("*.py")):
        source = py.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_IMPORTS:
            if re.search(pattern, source):
                offenders.append(f"{py.relative_to(REPO_ROOT)}: {pattern}")
    assert not offenders, f"Forbidden imports found: {offenders}"


def test_compose_has_exactly_the_three_spec_services():
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    # Top-level service names are the 2-space-indented keys under `services:`.
    services_block = compose.split("services:", 1)[1].split("\nvolumes:", 1)[0]
    services = re.findall(r"\n  ([a-z][a-z0-9_-]*):", services_block)
    assert sorted(services) == ["backend", "frontend", "postgres"], (
        f"docker-compose.yml must define exactly backend/frontend/postgres, got {services}"
    )


def test_health_tracker_is_not_a_multi_state_fsm():
    """Phase 4 allows a simple failure counter, not a HEALTHY/DEGRADED/OPEN FSM."""
    source = (BACKEND_ROOT / "app" / "reliability" / "health_tracker.py").read_text(encoding="utf-8").lower()
    for state in ("healthy/degraded/open", "circuit_open", "half_open", "state machine"):
        assert state not in source, f"Health tracker appears to implement a circuit-breaker FSM: '{state}'"


def test_routing_weights_are_static_not_learned():
    """No adaptive/ML routing — strategies must be the four fixed weight presets."""
    from app.routing.strategies import STRATEGIES

    assert set(STRATEGIES) == {"cost", "quality", "latency", "balanced"}
    for name, weights in STRATEGIES.items():
        assert set(weights) == {"quality", "capability", "latency", "cost"}, name
        assert abs(sum(weights.values()) - 1.0) < 1e-9, f"{name} weights must sum to 1.0"
        for factor, value in weights.items():
            assert isinstance(value, (int, float)), f"{name}.{factor} must be a static number"


def test_no_rate_limiting_middleware_on_app():
    from app.main import app

    paths = [r.path for r in app.routes]
    middleware_names = [m.cls.__name__.lower() for m in app.user_middleware]
    assert not any("limit" in name for name in middleware_names), (
        f"Rate-limiting middleware detected: {middleware_names}"
    )
    assert "/rate" not in " ".join(paths), "Rate-limit endpoint found — out of MVP scope"


@pytest.mark.parametrize("env_key", [
    "DATABASE_URL",
    "API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GROQ_API_KEY",
    "DEFAULT_ROUTING_STRATEGY",
    "ANALYZER_MODE",
    "LOG_LEVEL",
])
def test_env_example_keys_are_readable_by_settings(env_key):
    """Every .env.example key must map to a Settings field (spec 0.2 ↔ config.py)."""
    from app.config import Settings

    env_example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    declared = {
        line.split("=", 1)[0].strip()
        for line in env_example.splitlines()
        if line.strip() and not line.strip().startswith("#") and "=" in line
    }
    assert env_key in declared, f"{env_key} missing from .env.example"

    fields = set(Settings.model_fields)
    assert env_key.lower() in fields, (
        f".env.example defines {env_key} but app.config.Settings has no matching field"
    )
