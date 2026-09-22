# Phase 6 — Evaluation Harness

## Goal

Quantitative proof the router works — feeds directly into the capstone report Results section.

## Quick Start

```bash
cd backend
python eval/run_eval.py
```

Output lands in `eval/results/report_<timestamp>.json` and `.md`.
Final run write-up with interpretation: [`RESULTS.md`](RESULTS.md).

## What Gets Measured

| Metric | Description |
|--------|-------------|
| **Routing accuracy** | % of queries where `selected_model ∈ acceptable_models` |
| **Random baseline** | Expected accuracy if model chosen uniformly at random |
| **Cost comparison** | Routed cost vs. cost if every query used the most expensive model |
| **Latency overhead** | Time spent in analyzer + scoring (no provider call) |
| **Fallback rate** | % of requests that would use fallback with a mocked primary failure |
| **Analyzer comparison** | Heuristic vs LLM task_type classification accuracy vs labels |

### Honest LLM-analyzer reporting (Phase 8)

When `GROQ_API_KEY`/`OPENAI_API_KEY` is set, the LLM column is measured with
`strict=True` — a failed LLM call is **counted as failed**, never silently scored
as a heuristic result. The report shows `llm_classified` / `llm_failed` counts
next to the accuracy (e.g. `94.9% (59 classified, 1 failed)`). Calls are paced
(~1.5s apart with 429 backoff) to respect Groq's free-tier rate limit.

## Files

| File | Purpose |
|------|---------|
| `dataset.json` | 60 hand-labeled queries across 5 task categories |
| `run_eval.py` | Runs all metrics and writes reports |
| `results/` | Timestamped JSON + Markdown reports |

## Configuration

- Uses in-memory SQLite with the same 3 seeded models — no Postgres or API keys required for the default run.
- Set `ANALYZER_MODE=llm` and provide `GROQ_API_KEY` or `OPENAI_API_KEY` to include live LLM analyzer comparison (otherwise LLM column uses heuristic fallback and is marked `skipped`).

## Implementation Checklist (Phase 6 + Phase 8 wrap-up)

- [x] `dataset.json` — 60 labeled entries
- [x] `run_eval.py` — all 5 metrics + random baseline
- [x] `analyzer/llm_analyzer.py` — cheap LLM classifier with heuristic fallback
- [x] `ANALYZER_MODE` wired in routing engine
- [x] Full eval run with real API keys (Phase 8.3) — results in `results/`
- [x] Honest LLM reporting: `strict=True` + `llm_classified`/`llm_failed` counts
- [ ] Tune `acceptable_models` labels after reviewing routing decisions

## Project Status

All phases (0–8) are complete. See the root `README.md` for setup, API
reference, and the final results summary.
