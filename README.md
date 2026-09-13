# Prism — LLM Routing Gateway

An OpenAI-compatible LLM gateway that analyzes incoming chat requests, scores candidate models from multiple providers on capability/cost/quality/latency, and routes to the best one with a fully explainable decision.

## Quick Start

```bash
# 1. Copy env template
cp .env.example .env

# 2. Fill in your API keys (not required for Milestone 1)
#    Edit .env and add OPENAI_API_KEY, ANTHROPIC_API_KEY, GROQ_API_KEY

# 3. Bring up the full stack
docker compose up --build
```

## Endpoints

| Endpoint | Description |
|---|---|
| `GET /health` | Health check → `{"status": "ok"}` |
| `GET /v1/models` | List registered models |

## Development

Backend runs at `http://localhost:8000`  
Frontend runs at `http://localhost:5173`  
PostgreSQL runs at `localhost:5432`

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2.x async |
| Database | PostgreSQL 16 |
| Migrations | Alembic |
| Frontend | React 18 + TypeScript + Vite + Tailwind |
| Testing | Pytest, pytest-asyncio, HTTPX |
