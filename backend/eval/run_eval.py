#!/usr/bin/env python3
"""Phase 6 evaluation harness — routing accuracy, cost, latency, fallback, analyzers.

Usage:
    cd backend
    python eval/run_eval.py

Writes JSON + Markdown reports to eval/results/.
"""
from __future__ import annotations

import asyncio
import json
import logging
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Allow running as `python eval/run_eval.py` from backend/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from app.analyzer.heuristic_analyzer import analyze as heuristic_analyze
from app.config import settings
from app.cost import estimate_cost
from app.models.model_registry import Model
from app.reliability.fallback import call_with_fallback
from app.reliability.health_tracker import HealthTracker
from app.routing import engine as routing_engine
from app.routing.strategies import DEFAULT_STRATEGY
from app.schemas.chat import ChatMessage, ChatRequest, ChatResponse, ChatResponseChoice

EVAL_DIR = Path(__file__).parent
DATASET_PATH = EVAL_DIR / "dataset.json"
RESULTS_DIR = EVAL_DIR / "results"

logging.getLogger("app.reliability.fallback").setLevel(logging.ERROR)

SEED_MODELS = [
    Model(id="gpt-4o-mini", provider="openai",
          capabilities=["general", "coding", "reasoning", "qa"],
          context_window=128_000, quality_score=0.72,
          input_price_per_1k=0.000150, output_price_per_1k=0.000600,
          avg_latency_ms=800, enabled=True),
    Model(id="claude-3-haiku-20240307", provider="anthropic",
          capabilities=["general", "summarization", "coding", "reasoning", "long_context"],
          context_window=200_000, quality_score=0.78,
          input_price_per_1k=0.000250, output_price_per_1k=0.001250,
          avg_latency_ms=950, enabled=True),
    Model(id="llama3-8b-8192", provider="groq",
          capabilities=["general", "qa", "summarization"],
          context_window=8_192, quality_score=0.58,
          input_price_per_1k=0.000050, output_price_per_1k=0.000080,
          avg_latency_ms=350, enabled=True),
]

FLAGSHIP_MODEL_ID = "claude-3-haiku-20240307"

# Live LLM-analyzer pacing (Groq free tier rejects bursts with HTTP 429).
_LLM_CALL_INTERVAL_S = 1.5   # sleep between LLM classification calls
_LLM_429_BACKOFF_S = 5.0     # base wait before retrying a 429
_LLM_MAX_ATTEMPTS = 3        # attempts per entry before counting a failure


async def _load_seed_models(_session: Any) -> list[Model]:
    """Return the Phase 6 seed registry without touching Postgres or provider APIs."""
    return list(SEED_MODELS)


class _EvalProvider:
    """Tiny provider fake used to exercise fallback logic without generation APIs."""

    def __init__(self, model_id: str, should_fail: bool = False) -> None:
        self.model_id = model_id
        self.should_fail = should_fail

    async def generate(self, request: ChatRequest) -> ChatResponse:
        if self.should_fail:
            raise RuntimeError(f"simulated provider failure for {self.model_id}")

        return ChatResponse(
            id=f"eval-{self.model_id}",
            model=request.model or self.model_id,
            choices=[
                ChatResponseChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content="eval response"),
                    finish_reason="stop",
                )
            ],
            usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        )


def _random_baseline(dataset: list[dict], model_count: int = 3) -> float:
    """Expected routing accuracy if each acceptable set has ~model_count overlap."""
    hits = 0.0
    for entry in dataset:
        acceptable = entry["acceptable_models"]
        hits += len(acceptable) / model_count
    return round(hits / len(dataset), 4) if dataset else 0.0


async def _simulate_primary_failure(routing_result, messages: list[dict]) -> bool:
    """Return True when the existing fallback helper recovers from primary failure."""
    if len(routing_result.ranked) < 2:
        return False

    primary_provider = routing_result.ranked[0].model.provider
    providers = {
        primary_provider: _EvalProvider(routing_result.ranked[0].model.id, should_fail=True)
    }
    for scored in routing_result.ranked[1:]:
        providers.setdefault(scored.model.provider, _EvalProvider(scored.model.id))

    request = ChatRequest(messages=messages)

    def get_provider(provider_name: str) -> _EvalProvider:
        return providers[provider_name]

    try:
        _response, _model_used, fallback_used = await call_with_fallback(
            routing_result,
            request,
            get_provider,
            HealthTracker(),
        )
    except Exception:
        return False
    return fallback_used


async def _run_routing_eval(dataset: list[dict]) -> dict:
    routing_hits = 0
    routed_cost = 0.0
    flagship_cost = 0.0
    overhead_ms: list[float] = []
    fallback_count = 0
    per_entry: list[dict] = []

    flagship = next(m for m in SEED_MODELS if m.id == FLAGSHIP_MODEL_ID)

    original_loader = routing_engine.load_active_models
    routing_engine.load_active_models = _load_seed_models
    try:
        for entry in dataset:
            messages = [{"role": "user", "content": entry["query"]}]

            t0 = time.perf_counter()
            result = await routing_engine.route(messages, DEFAULT_STRATEGY, session=None)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            overhead_ms.append(elapsed_ms)

            selected = result.selected.id
            hit = selected in entry["acceptable_models"]
            routing_hits += int(hit)

            est_tokens = result.analysis.estimated_input_tokens
            routed_cost += estimate_cost(result.selected, est_tokens)
            flagship_cost += estimate_cost(flagship, est_tokens)

            if await _simulate_primary_failure(result, messages):
                fallback_count += 1

            per_entry.append({
                "query": entry["query"][:80],
                "selected_model": selected,
                "acceptable": entry["acceptable_models"],
                "routing_hit": hit,
                "task_type": result.analysis.task_type,
                "expected_task_type": entry["expected_task_type"],
                "overhead_ms": round(elapsed_ms, 2),
            })
    finally:
        routing_engine.load_active_models = original_loader

    n = len(dataset)
    p95_index = max(0, min(n - 1, int(n * 0.95) - 1))
    return {
        "routing_accuracy": round(routing_hits / n, 4) if n else 0.0,
        "random_baseline": _random_baseline(dataset),
        "total_routed_cost_usd": round(routed_cost, 6),
        "total_flagship_cost_usd": round(flagship_cost, 6),
        "cost_savings_pct": round((1 - routed_cost / flagship_cost) * 100, 2) if flagship_cost else 0.0,
        "avg_routing_overhead_ms": round(statistics.mean(overhead_ms), 2) if overhead_ms else 0.0,
        "p95_routing_overhead_ms": round(sorted(overhead_ms)[p95_index] if n else 0, 2),
        "simulated_fallback_rate": round(fallback_count / n, 4) if n else 0.0,
        "entries": per_entry,
    }


async def _run_analyzer_eval(dataset: list[dict]) -> dict:
    heuristic_hits = 0
    llm_hits = 0
    llm_calls = 0
    llm_failures = 0
    llm_available = bool(settings.groq_api_key or settings.openai_api_key)

    for entry in dataset:
        h = heuristic_analyze(entry["query"])
        if h.task_type == entry["expected_task_type"]:
            heuristic_hits += 1

        if llm_available:
            from app.analyzer.llm_analyzer import analyze as llm_analyze

            # Pace + retry: Groq free tier rate-limits rapid bursts with 429.
            # strict=True so a fallback-to-heuristic can't masquerade as an
            # LLM classification in the report.
            for attempt in range(_LLM_MAX_ATTEMPTS):
                try:
                    await asyncio.sleep(_LLM_CALL_INTERVAL_S if llm_calls else 0)
                    l = await llm_analyze(entry["query"], strict=True)
                    llm_calls += 1
                    if l.task_type == entry["expected_task_type"]:
                        llm_hits += 1
                    break
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code != 429 or attempt == _LLM_MAX_ATTEMPTS - 1:
                        llm_failures += 1
                        break
                    await asyncio.sleep(_LLM_429_BACKOFF_S * (attempt + 1))
                except Exception:
                    llm_failures += 1
                    break

    n = len(dataset)
    result = {
        "heuristic_task_type_accuracy": round(heuristic_hits / n, 4) if n else 0.0,
        "llm_task_type_accuracy": None,
        "llm_analyzer_skipped": not llm_available,
        "llm_classified": llm_calls,
        "llm_failed": llm_failures,
    }
    if llm_calls:
        result["llm_task_type_accuracy"] = round(llm_hits / llm_calls, 4)
    return result


def _format_llm_row(a: dict) -> str:
    """Render the LLM analyzer row, including live sample counts when available."""
    if a.get("llm_analyzer_skipped"):
        return "skipped (no API key)"
    accuracy = a.get("llm_task_type_accuracy")
    if accuracy is None:
        return "no successful LLM classifications"
    classified = a.get("llm_classified")
    failed = a.get("llm_failed")
    if classified is None:
        return f"{accuracy:.1%}"
    detail = f"{accuracy:.1%} ({classified} classified"
    if failed:
        detail += f", {failed} failed"
    return detail + ")"


def _write_reports(report: dict) -> tuple[Path, Path]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = RESULTS_DIR / f"report_{ts}.json"
    md_path = RESULTS_DIR / f"report_{ts}.md"

    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    r = report["routing"]
    a = report["analyzers"]
    md = f"""# Prism Eval Report — {report["timestamp"]}

## Routing Metrics

| Metric | Value |
|--------|-------|
| Routing accuracy | {r["routing_accuracy"]:.1%} |
| Random baseline | {r["random_baseline"]:.1%} |
| Accuracy above baseline | {(r["routing_accuracy"] - r["random_baseline"]):.1%} |
| Total routed cost | ${r["total_routed_cost_usd"]:.6f} |
| Total flagship cost | ${r["total_flagship_cost_usd"]:.6f} |
| Cost savings | {r["cost_savings_pct"]}% |
| Avg routing overhead | {r["avg_routing_overhead_ms"]} ms |
| P95 routing overhead | {r["p95_routing_overhead_ms"]} ms |
| Simulated fallback rate | {r["simulated_fallback_rate"]:.1%} |

## Analyzer Comparison

| Analyzer | Task-type accuracy |
|----------|-------------------|
| Heuristic | {a["heuristic_task_type_accuracy"]:.1%} |
| LLM | {_format_llm_row(a)} |

## Config

- Strategy: `{report["strategy"]}`
- Analyzer mode: `{report["analyzer_mode"]}`
- Dataset size: {report["dataset_size"]}
"""
    md_path.write_text(md, encoding="utf-8")
    return json_path, md_path


async def main() -> None:
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))

    routing = await _run_routing_eval(dataset)
    analyzers = await _run_analyzer_eval(dataset)

    report = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "dataset_size": len(dataset),
        "strategy": DEFAULT_STRATEGY,
        "analyzer_mode": settings.analyzer_mode,
        "routing": routing,
        "analyzers": analyzers,
    }

    json_path, md_path = _write_reports(report)

    print(f"Eval complete — {len(dataset)} entries")
    print(f"  Routing accuracy:  {routing['routing_accuracy']:.1%}  (baseline {routing['random_baseline']:.1%})")
    print(f"  Cost savings:      {routing['cost_savings_pct']}%")
    print(f"  Avg overhead:      {routing['avg_routing_overhead_ms']} ms")
    print(f"  Heuristic accuracy:{analyzers['heuristic_task_type_accuracy']:.1%}")
    print(f"  LLM accuracy:      {_format_llm_row(analyzers)}")
    print(f"  Reports: {json_path.name}, {md_path.name}")


if __name__ == "__main__":
    asyncio.run(main())
