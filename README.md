# Prism — LLM Routing Gateway

An OpenAI-compatible LLM gateway that analyzes each incoming chat request, scores candidate models from multiple providers on capability / cost / quality / latency, and routes to the best one — with the routing decision fully explainable in the response. Includes retry + fallback, usage/cost logging to Postgres, an evaluation harness, and a React dashboard.

Built as a college capstone project (not a production SaaS).

## Quick Start

```bash
# 1. Copy the env template (see Environment Variables below)
cp .env.example .env

# 2. Fill in your API keys (optional — the stack runs without them;
#    provider calls and the live LLM-analyzer comparison need at least one)
#    Edit .env: OPENAI_API_KEY, ANTHROPIC_API_KEY, GROQ_API_KEY

# 3. Bring up the full stack (Postgres + backend + frontend)
docker compose up --build
```

On start the backend container runs Alembic migrations, seeds the model registry, then launches uvicorn.

| Service | URL |
|---|---|
| Backend API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |
| Frontend dashboard | http://localhost:5173 |
| PostgreSQL | localhost:5432 |

## Environment Variables

`.env.example` (copy to `.env`) — read by the backend via `pydantic-settings`:

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | yes | `postgresql+asyncpg://prism:prism@postgres:5432/prism` | Async SQLAlchemy URL. `docker-compose.yml` overrides this for the `backend` service to point at the `postgres` container. |
| `API_KEY` | yes | `dev-local-key-change-me` | Single bearer token required on `/v1/chat/completions`. Change it for anything non-local. |
| `OPENAI_API_KEY` | no | *(empty)* | Enables the OpenAI provider (`gpt-4o-mini`). |
| `ANTHROPIC_API_KEY` | no | *(empty)* | Enables the Anthropic provider (`claude-3-haiku`). |
| `GROQ_API_KEY` | no | *(empty)* | Enables the Groq provider (`llama3-8b-8192`, free tier) and the live LLM analyzer. |
| `DEFAULT_ROUTING_STRATEGY` | no | `balanced` | Strategy used when the request has no `X-Routing-Strategy` header. One of `cost`, `quality`, `latency`, `balanced`. |
| `ANALYZER_MODE` | no | `heuristic` | `heuristic` (keyword rules, free) or `llm` (one cheap LLM classification call, falls back to heuristic on failure). |
| `LOG_LEVEL` | no | `info` | Python log level. |

## API

### `GET /health`

```json
{"status": "ok"}
```

### `GET /v1/models`

Lists enabled models from the registry (seeded: `gpt-4o-mini`, `claude-3-haiku-20240307`, `llama3-8b-8192`).

### `POST /v1/chat/completions`

OpenAI-compatible chat completion with intelligent routing.

**Headers**

| Header | Required | Values |
|---|---|---|
| `Authorization` | yes | `Bearer <API_KEY>` (from `.env`) |
| `X-Routing-Strategy` | no | `cost` \| `quality` \| `latency` \| `balanced` (default from `DEFAULT_ROUTING_STRATEGY`) |

**Request**

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer dev-local-key-change-me" \
  -H "X-Routing-Strategy: balanced" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Write a Python function to reverse a linked list"}]}'
```

**Response** — standard OpenAI shape plus a `routing` object explaining the decision:

```json
{
  "id": "chatcmpl-...",
  "model": "claude-3-haiku-20240307",
  "choices": [{"message": {"role": "assistant", "content": "..."}, "finish_reason": "stop"}],
  "usage": {"prompt_tokens": 120, "completion_tokens": 340, "total_tokens": 460},
  "routing": {
    "selected_model": "claude-3-haiku-20240307",
    "strategy": "balanced",
    "reason": "Best capability match with acceptable latency and cost.",
    "confidence": 0.91,
    "candidates": [
      {"model": "claude-3-haiku-20240307", "score": 0.91},
      {"model": "gpt-4o-mini", "score": 0.84}
    ],
    "fallback_used": false,
    "cost_usd": 0.0042,
    "latency_ms": 1380
  }
}
```

**Streaming** — send `"stream": true` to receive standard OpenAI SSE `data: {...}` chunks. After the final content chunk the gateway emits one extra terminal event carrying the same `routing` object, then `data: [DONE]`:

```
data: {"id":"chatcmpl-...","object":"chat.completion.chunk","choices":[{"delta":{"content":"..."}}]}

event: routing_metadata
data: {"selected_model":"...","strategy":"balanced","reason":"...","candidates":[...]}

data: [DONE]
```

**How a request is routed** — analyzer (task type / complexity / required capabilities) → capability + health filters → weighted scoring (quality, capability match, latency, cost) → top pick. If the top pick fails after retries, one fallback hop is taken from the already-ranked list and `fallback_used` becomes `true`.

### Admin endpoints (dashboard data source)

| Endpoint | Returns |
|---|---|
| `GET /admin/routing-stats` | Total requests, success rate, error rate, avg latency, total cost, fallback rate |
| `GET /admin/models-performance` | Per-model requests, success %, avg latency, total cost |
| `GET /admin/decisions?limit=50` | Recent requests: id, timestamp, selected model, status, cost |
| `GET /admin/decisions/{request_id}` | Full record: analyzer output (`prompt_meta`) + routing decision + model run |

## Dashboard

The React frontend (Phase 7) reads the admin endpoints:

| Page | Route |
|---|---|
| Overview | `/overview` |
| Model Performance | `/models` |
| Routing Distribution | `/routing` |
| Request Inspector | `/requests` |

## Testing

```bash
cd backend
pip install -e ".[dev]"
pytest
```

~120 tests: unit (analyzer, filters, scorer, cost formula, retry, health tracker, eval harness, scope guards) and integration (chat, streaming, fallback, logging, admin endpoints) using mocked providers — no paid API calls and no Postgres required.

## Evaluation Harness

```bash
# From the repo root (so the backend can read .env for a live LLM-analyzer comparison):
python backend/eval/run_eval.py
```

Runs the 60-entry labeled dataset in `backend/eval/dataset.json` through the routing engine (no generation, no Postgres) and writes a JSON + Markdown report to `backend/eval/results/`. Metrics: routing accuracy vs. random baseline, routed vs. flagship cost, analyzer+scoring latency overhead, simulated fallback rate, and heuristic vs. LLM analyzer classification accuracy. See `backend/eval/README.md`. **Final results with interpretation: [`backend/eval/RESULTS.md`](backend/eval/RESULTS.md)** (90.0% routing accuracy vs 82.2% random baseline, 58.7% cost savings, heuristic analyzer 96.7% vs LLM 76.7%).

Without provider API keys the LLM-analyzer column is marked `skipped` and only the heuristic run is reported.

## Project Structure

```
prism/
├── docker-compose.yml        # 3 services: backend, frontend, postgres
├── .env.example
├── backend/
│   ├── alembic.ini, migrations/
│   ├── seed.py               # idempotent model-registry seed (run on container start)
│   ├── app/
│   │   ├── analyzer/         # heuristic_analyzer.py, llm_analyzer.py
│   │   ├── routing/          # registry, filters, scorer, strategies, engine
│   │   ├── providers/        # OpenAI, Anthropic, Groq adapters
│   │   ├── reliability/      # retry, fallback, in-memory health tracker
│   │   ├── services/         # request logger (requests/routing_decisions/model_runs)
│   │   ├── api/              # chat, models, admin, health routes
│   │   └── schemas/          # Pydantic request/response models
│   ├── eval/                 # dataset.json, run_eval.py, results/
│   └── tests/                # unit/ + integration/
└── frontend/                 # React 18 + TS + Vite + Tailwind + Recharts
```

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2.x async |
| Database | PostgreSQL 16 |
| Migrations | Alembic |
| Frontend | React 18 + TypeScript + Vite + Tailwind |
| Providers | OpenAI API, Anthropic API, Groq API |
| Testing | Pytest, pytest-asyncio, HTTPX |

## Scope

MVP capstone scope only — deliberately **not** included (future work): rate limiting, Redis or any second data store, multi-state circuit breaker (only the simple failure-counter health tracker), OAuth/RBAC/multi-tenant keys, Prometheus/Grafana/OpenTelemetry, Kubernetes/Terraform/multi-region deployment, adaptive/ML-learned routing weights, load-testing infrastructure.
