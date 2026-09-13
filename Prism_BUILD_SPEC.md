# Prism — Build Specification for AI-Assisted Development

## 0. Project Summary & Ground Rules

Build **IntelliRoute**: an OpenAI-compatible LLM gateway that analyzes each incoming chat request, scores candidate models from multiple providers on capability/cost/quality/latency, and routes to the best one — with the routing decision fully explainable in the response. Includes retry+fallback, usage/cost logging to Postgres, and a React dashboard.

This is a solo/small-team **college capstone project**, not a production SaaS.

**Do not add**, even if it seems like "best practice": rate limiting, Redis, multi-state circuit-breaker FSM, OAuth/RBAC, Prometheus/Grafana/OpenTelemetry, Kubernetes, Terraform, multi-region deployment, adaptive/ML-based routing, load-testing infra. These are Future Work, not MVP scope. Simpler, correct, and well-tested beats "enterprise-grade" here.

**The two deliverables that matter most:** the routing engine (Phase 3) and the evaluation harness (Phase 6). Everything else exists to support those two.

**Tech stack (fixed):**

| Layer | Choice |
|---|---|
| Backend | Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.x async |
| Database | PostgreSQL only (no Redis) |
| Migrations | Alembic |
| Frontend | React 18 + TypeScript + Vite, Tailwind, Recharts |
| Providers | OpenAI API, Anthropic API, Groq API (free tier) |
| Testing | Pytest, pytest-asyncio, HTTPX ASGI test client |
| Containerization | Docker + docker-compose, 3 services: backend, frontend, postgres |
| Env | `.env` + `pydantic-settings` |

---

## PHASE 0 — Repo Scaffold, Docker, Environment

**Goal: `docker compose up --build` brings up an empty-but-running stack.**

### 0.1 Repository structure

```
intelliroute/
├── docker-compose.yml
├── .env.example
├── README.md
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml  (or requirements.txt)
│   ├── alembic.ini
│   ├── migrations/
│   ├── app/
│   │   ├── main.py                  # FastAPI app entrypoint
│   │   ├── config.py                # pydantic-settings, reads .env
│   │   ├── db.py                    # async engine/session setup
│   │   ├── models/                  # SQLAlchemy ORM models
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── model_registry.py
│   │   │   ├── request_log.py
│   │   │   ├── routing_decision.py
│   │   │   └── model_run.py
│   │   ├── schemas/                 # Pydantic request/response schemas
│   │   │   ├── chat.py              # OpenAI-compatible chat schemas
│   │   │   ├── routing.py
│   │   │   └── admin.py
│   │   ├── analyzer/
│   │   │   ├── heuristic_analyzer.py
│   │   │   └── llm_analyzer.py
│   │   ├── routing/
│   │   │   ├── registry.py          # loads model configs
│   │   │   ├── filters.py           # capability + health filtering
│   │   │   ├── scorer.py            # weighted scoring engine
│   │   │   ├── strategies.py        # cost/quality/latency/balanced weight presets
│   │   │   └── engine.py            # orchestrates analyzer→filter→score→select
│   │   ├── providers/
│   │   │   ├── base.py              # LLMProvider abstract interface
│   │   │   ├── openai_provider.py
│   │   │   ├── anthropic_provider.py
│   │   │   └── groq_provider.py
│   │   ├── reliability/
│   │   │   ├── retry.py
│   │   │   ├── fallback.py
│   │   │   └── health_tracker.py    # in-memory failure-counter, NOT a full FSM
│   │   ├── api/
│   │   │   ├── chat.py              # POST /v1/chat/completions
│   │   │   ├── models.py            # GET /v1/models
│   │   │   ├── admin.py             # /admin/* endpoints
│   │   │   └── health.py            # GET /health
│   │   ├── auth.py                  # single API key check
│   │   └── logging_utils.py
│   ├── eval/
│   │   ├── dataset.json
│   │   ├── run_eval.py
│   │   └── results/
│   └── tests/
│       ├── unit/
│       └── integration/
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── src/
    │   ├── main.tsx
    │   ├── App.tsx
    │   ├── api/client.ts
    │   ├── pages/
    │   │   ├── Overview.tsx
    │   │   ├── ModelPerformance.tsx
    │   │   ├── RoutingDistribution.tsx
    │   │   └── RequestInspector.tsx
    │   └── components/
    └── ...
```

### 0.2 `.env.example`
```env
DATABASE_URL=postgresql+asyncpg://intelliroute:intelliroute@postgres:5432/intelliroute
API_KEY=dev-local-key-change-me
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GROQ_API_KEY=
DEFAULT_ROUTING_STRATEGY=balanced
ANALYZER_MODE=heuristic   # heuristic | llm
LOG_LEVEL=info
```

### 0.3 Docker
`docker-compose.yml` — exactly 3 services: `backend`, `frontend`, `postgres`. Backend's entrypoint runs Alembic migrations + seed script on container start, then launches uvicorn. Frontend just runs the Vite dev server (or a built static server later). One command brings up everything:
```
docker compose up --build
```

### ✅ Checkpoint 0
`docker compose up --build` runs without error; `postgres` is reachable; `backend` container starts uvicorn (even with no routes registered yet is fine at this exact instant, but by the end of this phase `GET /health` should return `{"status":"ok"}`). Do not proceed to Phase 1 until this works.

---

## PHASE 1 — Data Layer

**Goal: schema exists in Postgres, seed data loads, and a basic model-list read path works.**

### 1.1 Database schema (SQLAlchemy models)

```
users
  id            uuid pk
  name          text
  api_key_hash  text
  created_at    timestamptz

models              -- the "model registry" table
  id                    text pk        -- e.g. "gpt-4o-mini"
  provider              text           -- "openai" | "anthropic" | "groq"
  capabilities          text[]         -- e.g. {reasoning, coding, long_context}
  context_window        int
  quality_score         float          -- 0.0–1.0, manually configured
  input_price_per_1k    float
  output_price_per_1k   float
  avg_latency_ms        int            -- seeded, updated by rolling average
  enabled               boolean default true

requests
  id             uuid pk
  user_id        uuid fk -> users.id
  prompt_meta    jsonb        -- task_type, complexity, capabilities, confidence (analyzer output)
  strategy       text         -- cost | quality | latency | balanced
  created_at     timestamptz

routing_decisions
  id               uuid pk
  request_id       uuid fk -> requests.id
  selected_model   text fk -> models.id
  reason           text
  candidates_json  jsonb    -- [{model_id, score}, ...]
  confidence       float

model_runs
  id             uuid pk
  request_id     uuid fk -> requests.id
  model_id       text fk -> models.id
  latency_ms     int
  tokens_in      int
  tokens_out     int
  cost_usd       float
  status         text     -- success | error | timeout
  fallback_used  boolean default false
  created_at     timestamptz
```

Build this as an Alembic migration before writing any route logic.

### 1.2 Seed data
Seed the `models` table with at least 3 real models:
- One OpenAI model (a cheap/fast tier)
- One Anthropic model
- One Groq-hosted model (free tier — good for testing without burning paid credits)

Write as a data migration or a `seed.py` run once on container start. Use real current pricing per provider at seed time.

### 1.3 Tests (write now, not later)
- `tests/unit/test_cost.py` — cost formula: `cost_usd = (tokens_in/1000 * input_price_per_1k) + (tokens_out/1000 * output_price_per_1k)`. Verify against hand-computed values.
- `tests/integration/test_models_endpoint.py` — `GET /v1/models` returns the seeded rows (build this minimal endpoint now, in `api/models.py`, to have something to test against).

### ✅ Checkpoint 1
Migrations apply cleanly on a fresh container; seed data is present; `GET /v1/models` returns 3 models; both tests above pass.

---

## PHASE 2 — Provider Abstraction & Hardcoded Passthrough

**Goal: prove end-to-end connectivity to real providers before any routing logic exists.**

### 2.1 Provider interface (`providers/base.py`)
```python
class LLMProvider(ABC):
    async def generate(self, messages: list[dict]) -> ProviderResponse: ...
    async def stream(self, messages: list[dict]) -> AsyncIterator[str]: ...
    async def health_check(self) -> bool: ...
```
`ProviderResponse` = normalized `{content, tokens_in, tokens_out, latency_ms}`.

### 2.2 Adapters
Implement `openai_provider.py` and `anthropic_provider.py` against that interface. (Groq adapter comes in Phase 4 — don't add it yet, keep this phase small.)

### 2.3 Hardcoded chat endpoint
Build `POST /v1/chat/completions` in `api/chat.py`, hardcoded to call one provider directly — **no routing engine yet**. This proves the OpenAI-compatible request/response shape and provider connectivity work before any routing complexity is layered on.

Request/response shape to implement (full contract, used from here through Phase 3):
```json
// Request
{ "messages": [{"role": "user", "content": "..."}], "stream": false }

// Response (base shape — the "routing" object is added in Phase 3, not here)
{
  "id": "chatcmpl-...",
  "model": "claude-sonnet",
  "choices": [{"message": {"role": "assistant", "content": "..."}, "finish_reason": "stop"}],
  "usage": {"prompt_tokens": 120, "completion_tokens": 340, "total_tokens": 460}
}
```

### 2.4 Tests
- `tests/integration/test_chat_endpoint.py` — full request through FastAPI TestClient with **mocked** provider adapters (never hit real paid APIs in tests).

### ✅ Checkpoint 2
A real curl/Postman request to `/v1/chat/completions` returns a real completion from at least one provider. Mocked integration test passes.

---

## PHASE 3 — The Routing Engine (core deliverable — take your time here)

**Goal: replace the hardcoded model call with real analyzer → filter → score → select, fully explainable, with streaming support.**

Build in this exact order, writing a unit test after each numbered step before moving to the next:

1. **`analyzer/heuristic_analyzer.py`** — pure function, no LLM call:
   - `task_type`: keyword/regex rules (code fence or "function"/"bug"/"error" → coding; "summarize"/"tl;dr" → summarization; short factual question pattern → qa; else → general).
   - `complexity`: prompt length + multi-step language ("first... then... finally", numbered steps) → low/medium/high.
   - `required_capabilities`: derived from task_type mapping.
   - `estimated_input_tokens`: rough word-count × 1.3.
   - Output schema exactly:
   ```json
   {"task_type": "coding", "complexity": "high", "required_capabilities": ["coding","reasoning"], "context_requirement": "medium", "estimated_input_tokens": 5000, "confidence": 0.7}
   ```
   → `tests/unit/test_heuristic_analyzer.py`: known prompts → expected classification.

2. **`routing/registry.py`** — loads `models` table into memory (re-query per request is fine, don't over-engineer caching at this scale).

3. **`routing/filters.py`**:
   - `filter_by_capability(candidates, required_capabilities)` — keep only models whose `capabilities` superset the required list.
   - `filter_by_health(candidates, health_tracker)` — stub `health_tracker` for now (real implementation is Phase 4); everything is "healthy" until then.
   → `tests/unit/test_filters.py`: empty candidates, no match, partial match edge cases.

4. **`routing/strategies.py`** — four named weight presets:
   ```python
   STRATEGIES = {
     "cost":     {"quality":0.15,"capability":0.25,"latency":0.10,"cost":0.50},
     "quality":  {"quality":0.50,"capability":0.30,"latency":0.10,"cost":0.10},
     "latency":  {"quality":0.15,"capability":0.20,"latency":0.50,"cost":0.15},
     "balanced": {"quality":0.30,"capability":0.30,"latency":0.20,"cost":0.20},
   }
   ```

5. **`routing/scorer.py`** — normalize each metric to 0–1 before weighting:
   - `quality_score` → used as-is.
   - `capability_match` → (# matched / # required), 1.0 if superset.
   - `latency_score` → `1 - (avg_latency_ms / max_latency_among_candidates)`.
   - `cost_score` → `1 - (estimated_cost / max_estimated_cost_among_candidates)`.
   - `final_score = Σ weight_i × normalized_metric_i`.
   → `tests/unit/test_scorer.py`: hand-computed expected values for known inputs.

6. **`routing/engine.py`** — orchestrates: analyzer → filter → score all candidates → sort → return top pick + full candidate ranking + reason string (`"Best {dominant_factor} match given '{strategy}' strategy."`).

7. **Wire the engine into `api/chat.py`**, replacing the Phase 2 hardcoded call. Add the `routing` object to the response:
   ```json
   "routing": {
     "selected_model": "claude-sonnet",
     "strategy": "balanced",
     "reason": "Best capability match with acceptable latency and cost.",
     "confidence": 0.91,
     "candidates": [
       {"model": "claude-sonnet", "score": 0.91},
       {"model": "gpt-4o-mini", "score": 0.84}
     ],
     "fallback_used": false,
     "cost_usd": 0.0042,
     "latency_ms": 1380
   }
   ```
   Accept strategy via header: `X-Routing-Strategy: cost | quality | latency | balanced` (default `balanced`), and require `Authorization: Bearer <API_KEY>`.

8. **Streaming.** Implement `stream: true` as standard OpenAI SSE `data: {...}\n\n` chunks; after the final content chunk, send one extra terminal SSE event named `routing_metadata` containing the `routing` object. Do this now, not as an afterthought — it's part of this phase, not a separate later task.

**Do not** implement adaptive/ML-based routing (learned weights, bandits) — that's Future Work. A static, well-tested scoring function is correct scope here.

### ✅ Checkpoint 3
A request with no strategy header routes via `balanced` weights and the response includes a correct `routing` object with plausible scores. Switching `X-Routing-Strategy` changes the selected model on a prompt where it should (verify by hand with 2–3 test prompts). Streaming returns the `routing_metadata` event. All unit tests from steps 1, 3, 5 pass.

---

## PHASE 4 — Reliability Layer + Third Provider

**Goal: the gateway survives a provider failure without crashing the request, and 3 providers are live.**

### 4.1 Groq adapter
Implement `groq_provider.py` against the same `LLMProvider` interface from Phase 2. Wire into the registry.

### 4.2 Health tracker (`reliability/health_tracker.py`)
In-memory dict, no Redis, no FSM library:
```python
# {model_id: {"consecutive_failures": int, "unhealthy_until": datetime | None}}
```
- On failure: increment counter; at ≥3 failures, set `unhealthy_until = now + 60s`.
- On success: reset counter to 0.
- `is_healthy(model_id)`: `False` while `now < unhealthy_until`; allows one probe request through after expiry.
Wire this into the `filter_by_health` stub from Phase 3 step 3.

### 4.3 Retry (`reliability/retry.py`)
Retry only on `{timeout, 429, 502, 503, 504}`, max 2 attempts, exponential backoff (base 0.5s). Do not retry on invalid-request or auth errors.

### 4.4 Fallback (`reliability/fallback.py`)
If the top-scored candidate fails after retries, take the next-highest-scored candidate from the already-computed ranked list (don't re-run the whole pipeline) that still satisfies `required_capabilities`. Mark `fallback_used=true`. One fallback hop only — no chaining.

### 4.5 Tests
- `tests/unit/test_retry.py` — retry only fires on the specified status codes.
- `tests/integration/test_fallback.py` — mock primary provider to raise, assert fallback model gets called and `fallback_used=true` is set.

### ✅ Checkpoint 4
With a provider adapter mocked to fail, a request still returns a successful completion from the fallback model, and `fallback_used=true` appears in the `routing` object. Health tracker correctly marks a repeatedly-failing model unhealthy and excludes it from candidates for ~60s.

---

## PHASE 5 — Persistence & Admin API

**Goal: every request is logged, and the admin endpoints the dashboard needs are live.**

### 5.1 Logging
On every request, write rows to `requests`, `routing_decisions`, and `model_runs` (schema from Phase 1.1) — including cost (Phase 1.3 formula), latency, token counts, fallback flag, and status.

### 5.2 Admin endpoints
- `GET /admin/routing-stats` — total requests, success rate, avg latency, total cost, fallback rate (aggregate from `model_runs` + `routing_decisions`).
- `GET /admin/models-performance` — per-model requests, success %, avg latency, total cost.
- `GET /admin/decisions?limit=50` — paginated recent requests (id, timestamp, selected_model, status, cost).
- `GET /admin/decisions/{request_id}` — full record: analyzer output (`prompt_meta`) + routing decision + model run, for the Request Inspector.

### ✅ Checkpoint 5
After running ~10 varied requests through Phase 3/4, all four admin endpoints return correct, non-empty, consistent aggregates that you can hand-verify against the raw DB rows.

---

## PHASE 6 — Evaluation Harness (second core deliverable)

**Goal: quantitative proof the router works — this becomes your report's Results section.**

### 6.1 `eval/dataset.json`
50–100 hand-labeled entries, covering coding, summarization, creative writing, simple Q&A, and long-context analysis roughly evenly:
```json
[
  {
    "query": "Write a Python function to reverse a linked list",
    "expected_task_type": "coding",
    "expected_complexity": "medium",
    "acceptable_models": ["claude-sonnet", "gpt-4o-mini"]
  }
]
```

### 6.2 `eval/run_eval.py`
1. Load `dataset.json`.
2. For each entry, call the routing engine directly (bypass actual generation to avoid burning API credits on repeated runs — full end-to-end runs only occasionally).
3. Compute and save to `eval/results/`:
   - **Routing accuracy** = % where `selected_model ∈ acceptable_models`.
   - **Cost comparison** — total cost if every request went to the single most expensive/flagship model, vs. actual routed cost.
   - **Latency overhead** — analyzer+scoring time, measured separately from provider call time.
   - **Fallback rate** — run one pass with a provider mocked to fail, to demonstrate it deliberately.
   - **Heuristic vs. LLM analyzer** — run the dataset through both `ANALYZER_MODE` settings, compare classification accuracy against labels. (Build `analyzer/llm_analyzer.py` now if you haven't — it's a single cheap LLM call returning the same JSON schema as the heuristic analyzer.)

### ✅ Checkpoint 6
`run_eval.py` produces a report with all five metrics above, saved to `eval/results/`. Routing accuracy is meaningfully above random-selection baseline (compute that baseline too, for comparison).

---

## PHASE 7 — Frontend Dashboard

**Goal: the demo surface. Build in this order — Request Inspector is the best demo screen, so don't leave it for last if time runs short.**

1. **Overview** — cards from `GET /admin/routing-stats`.
2. **Model Performance** — table from `GET /admin/models-performance`.
3. **Routing Distribution** — bar/pie chart of selection frequency.
4. **Request Inspector** — list (`GET /admin/decisions`) → click row → detail (`GET /admin/decisions/{id}`) showing analyzer output → candidate scores table → selected model → fallback badge.

Keep styling simple with Tailwind — no design system, animations, or dark mode unless time permits at the end.

### ✅ Checkpoint 7
All 4 pages render real data from a running backend; Request Inspector correctly shows the full decision trail for a request you can identify in the DB.

---

## PHASE 8 — Polish & Wrap-Up

1. Full test suite green (`pytest` — everything from Phases 1–4).
2. `README.md` with setup instructions matching `.env.example`.
3. Final full eval run (Phase 6), results written up for the report.
4. Sanity-check the non-goals list below wasn't violated anywhere.

---

## Explicit Non-Goals (do not implement, even mid-build if it seems like "obviously good practice")

- Rate limiting / throttling of any kind.
- Redis or any second data store.
- Multi-state circuit breaker (HEALTHY/DEGRADED/OPEN FSM) — Phase 4's simplified health tracker only.
- OAuth, RBAC, multi-tenant API keys, usage quotas.
- Prometheus, Grafana, OpenTelemetry.
- Kubernetes, Terraform, multi-region/cloud deployment.
- Adaptive/ML-based/learned routing weights.
- Load testing infrastructure.

These are the correct "future work" list if asked to extend the project later — not now.

---

## Full Checklist (mirrors the phases above 1:1 — use this to track progress)

- [ ] **Phase 0** — Repo scaffold, docker-compose, Postgres running, `/health` returns ok
- [ ] **Phase 1** — DB schema + migration, seed data, `/v1/models`, cost-formula test passing
- [ ] **Phase 2** — Provider interface + OpenAI/Anthropic adapters, hardcoded `/v1/chat/completions` working end-to-end
- [ ] **Phase 3** — Heuristic analyzer, filters, strategies, scorer, engine wired in, `routing` object in response, streaming with `routing_metadata` event
- [ ] **Phase 4** — Groq adapter, health tracker, retry, fallback, failure-injection tests passing
- [ ] **Phase 5** — Request/decision/run logging, all 4 admin endpoints returning correct aggregates
- [ ] **Phase 6** — Eval dataset, `run_eval.py`, LLM-based analyzer, first results report generated
- [ ] **Phase 7** — Frontend: Overview → Model Performance → Routing Distribution → Request Inspector
- [ ] **Phase 8** — Full test suite green, README, final eval run, non-goals double-checked


**Instructions to follow:** Do not attempt to implement the entire application in one pass. Follow the Build Order Summary. Implement one milestone at a time, run the relevant tests, fix failures, and only then proceed to the next milestone. Do not introduce technologies, features, abstractions, or dependencies not specified in this document unless required to make the specified functionality work.
