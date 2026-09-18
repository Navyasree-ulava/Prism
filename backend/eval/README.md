# Phase 6 — Evaluation Harness

## Goal

Quantitative proof the router works — feeds directly into the capstone report Results section.

## Quick Start

```bash
cd backend
python eval/run_eval.py
```

Output lands in `eval/results/report_<timestamp>.json` and `.md`.

## What Gets Measured

| Metric | Description |
|--------|-------------|
| **Routing accuracy** | % of queries where `selected_model ∈ acceptable_models` |
| **Random baseline** | Expected accuracy if model chosen uniformly at random |
| **Cost comparison** | Routed cost vs. cost if every query used the most expensive model |
| **Latency overhead** | Time spent in analyzer + scoring (no provider call) |
| **Fallback rate** | % of requests that would use fallback with a mocked primary failure |
| **Analyzer comparison** | Heuristic vs LLM task_type classification accuracy vs labels |

## Files

| File | Purpose |
|------|---------|
| `dataset.json` | 60 hand-labeled queries across 5 task categories |
| `run_eval.py` | Runs all metrics and writes reports |
| `results/` | Timestamped JSON + Markdown reports |

## Configuration

- Uses in-memory SQLite with the same 3 seeded models — no Postgres or API keys required for the default run.
- Set `ANALYZER_MODE=llm` and provide `GROQ_API_KEY` or `OPENAI_API_KEY` to include live LLM analyzer comparison (otherwise LLM column uses heuristic fallback and is marked `skipped`).

## Implementation Checklist (Phase 6)

- [x] `dataset.json` — 60 labeled entries
- [x] `run_eval.py` — all 5 metrics + random baseline
- [x] `analyzer/llm_analyzer.py` — cheap LLM classifier with heuristic fallback
- [x] `ANALYZER_MODE` wired in routing engine
- [ ] First full eval run with real API keys (optional, for report)
- [ ] Tune `acceptable_models` labels after reviewing routing decisions

## Next Steps (Phase 7)

Wire the frontend dashboard pages to the Phase 5 admin endpoints:
1. Overview → `GET /admin/routing-stats`
2. Model Performance → `GET /admin/models-performance`
3. Routing Distribution → chart from decisions list
4. Request Inspector → `GET /admin/decisions` + detail view
