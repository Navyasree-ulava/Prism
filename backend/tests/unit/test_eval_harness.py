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
