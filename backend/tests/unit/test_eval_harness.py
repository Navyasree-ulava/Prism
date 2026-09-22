import json
from collections import Counter

import pytest

from eval import run_eval


def test_dataset_has_required_size_and_task_coverage():
    dataset = json.loads(run_eval.DATASET_PATH.read_text(encoding="utf-8"))

    assert 50 <= len(dataset) <= 100

    counts = Counter(entry["expected_task_type"] for entry in dataset)
    assert counts["coding"] >= 10
    assert counts["summarization"] >= 10
    assert counts["qa"] >= 10
    assert counts["general"] >= 10
    assert all(entry["acceptable_models"] for entry in dataset)


@pytest.mark.asyncio
async def test_routing_eval_beats_random_baseline_and_exercises_fallback():
    dataset = json.loads(run_eval.DATASET_PATH.read_text(encoding="utf-8"))

    report = await run_eval._run_routing_eval(dataset)

    assert report["routing_accuracy"] > report["random_baseline"]
    assert report["total_routed_cost_usd"] < report["total_flagship_cost_usd"]
    assert report["avg_routing_overhead_ms"] >= 0
    assert report["simulated_fallback_rate"] > 0


def test_write_reports_creates_json_and_markdown(tmp_path, monkeypatch):
    monkeypatch.setattr(run_eval, "RESULTS_DIR", tmp_path)
    report = {
        "timestamp": "2026-09-18T00:00:00+00:00",
        "dataset_size": 60,
        "strategy": "balanced",
        "analyzer_mode": "heuristic",
        "routing": {
            "routing_accuracy": 0.9,
            "random_baseline": 0.5,
            "total_routed_cost_usd": 0.001,
            "total_flagship_cost_usd": 0.002,
            "cost_savings_pct": 50.0,
            "avg_routing_overhead_ms": 1.2,
            "p95_routing_overhead_ms": 2.3,
            "simulated_fallback_rate": 1.0,
        },
        "analyzers": {
            "heuristic_task_type_accuracy": 0.95,
            "llm_task_type_accuracy": None,
            "llm_analyzer_skipped": True,
        },
    }

    json_path, md_path = run_eval._write_reports(report)

    assert json_path.exists()
    assert md_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8"))["dataset_size"] == 60
    assert "Routing accuracy" in md_path.read_text(encoding="utf-8")


def test_format_llm_row_reports_live_sample_counts():
    """Live runs must show classified/failed counts, never a bare fallback-blurred number."""
    assert run_eval._format_llm_row({"llm_analyzer_skipped": True}) == "skipped (no API key)"
    assert (
        run_eval._format_llm_row({"llm_analyzer_skipped": False, "llm_task_type_accuracy": None})
        == "no successful LLM classifications"
    )
    assert (
        run_eval._format_llm_row({
            "llm_analyzer_skipped": False,
            "llm_task_type_accuracy": 0.9,
            "llm_classified": 60,
            "llm_failed": 0,
        })
        == "90.0% (60 classified)"
    )
    assert (
        run_eval._format_llm_row({
            "llm_analyzer_skipped": False,
            "llm_task_type_accuracy": 0.5,
            "llm_classified": 4,
            "llm_failed": 2,
        })
        == "50.0% (4 classified, 2 failed)"
    )
    # Reports written before Phase 8 lack the count keys — still render.
    assert (
        run_eval._format_llm_row({"llm_analyzer_skipped": False, "llm_task_type_accuracy": 0.933})
        == "93.3%"
    )


@pytest.mark.asyncio
async def test_analyzer_eval_marks_llm_failed_when_strict_call_raises(monkeypatch):
    """A failing LLM call must be counted as failed, not silently scored as heuristic."""
    from unittest.mock import AsyncMock

    import app.analyzer.llm_analyzer as llm_mod

    monkeypatch.setattr(run_eval.settings, "groq_api_key", "test-key")
    monkeypatch.setattr(run_eval.settings, "openai_api_key", "")
    monkeypatch.setattr(run_eval, "_LLM_CALL_INTERVAL_S", 0)
    monkeypatch.setattr(
        llm_mod, "analyze",
        AsyncMock(side_effect=RuntimeError("simulated LLM outage")),
    )

    dataset = [
        {"query": "What is the capital of France?", "expected_task_type": "qa"},
        {"query": "Write a function to reverse a string", "expected_task_type": "coding"},
    ]
    result = await run_eval._run_analyzer_eval(dataset)

    assert result["llm_analyzer_skipped"] is False
    assert result["llm_classified"] == 0
    assert result["llm_failed"] == 2
    assert result["llm_task_type_accuracy"] is None, "failed calls must not produce an accuracy"
    assert 0.0 <= result["heuristic_task_type_accuracy"] <= 1.0


@pytest.mark.asyncio
async def test_analyzer_eval_counts_only_successful_llm_classifications(monkeypatch):
    from unittest.mock import AsyncMock

    import app.analyzer.llm_analyzer as llm_mod
    from app.analyzer.heuristic_analyzer import AnalysisResult

    correct = AnalysisResult(
        task_type="qa", complexity="low", required_capabilities=["qa"],
        context_requirement="low", estimated_input_tokens=10, confidence=0.9,
    )
    wrong = AnalysisResult(
        task_type="general", complexity="low", required_capabilities=["general"],
        context_requirement="low", estimated_input_tokens=10, confidence=0.9,
    )

    monkeypatch.setattr(run_eval.settings, "groq_api_key", "test-key")
    monkeypatch.setattr(run_eval.settings, "openai_api_key", "")
    monkeypatch.setattr(run_eval, "_LLM_CALL_INTERVAL_S", 0)
    monkeypatch.setattr(llm_mod, "analyze", AsyncMock(side_effect=[correct, wrong]))

    dataset = [
        {"query": "What is the capital of France?", "expected_task_type": "qa"},
        {"query": "Tell me a joke", "expected_task_type": "general"},
    ]
    result = await run_eval._run_analyzer_eval(dataset)

    assert result["llm_classified"] == 2
    assert result["llm_failed"] == 0
    assert result["llm_task_type_accuracy"] == 1.0
