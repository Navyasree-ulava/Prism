"""Integration tests for Phase 5 admin endpoints.

Strategy
--------
- In-process SQLite database with pre-seeded rows across all four tables.
- No real HTTP calls; uses HTTPX ASGI transport.
- Tests verify correct aggregates AND correct 404/422 error shapes.

Endpoints under test
--------------------
GET /admin/routing-stats
GET /admin/models-performance
GET /admin/decisions?limit=N
GET /admin/decisions/{request_id}
"""
from __future__ import annotations

import uuid
from typing import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import get_session
from app.main import app

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        # Create schema (SQLite-compatible subset)
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT,
                api_key_hash TEXT,
                created_at TEXT
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS models (
                id TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                capabilities TEXT NOT NULL DEFAULT '[]',
                context_window INTEGER NOT NULL,
                quality_score REAL NOT NULL,
                input_price_per_1k REAL NOT NULL,
                output_price_per_1k REAL NOT NULL,
                avg_latency_ms INTEGER NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS requests (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                prompt_meta TEXT,
                strategy TEXT NOT NULL DEFAULT 'balanced',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS routing_decisions (
                id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL,
                selected_model TEXT NOT NULL,
                reason TEXT,
                candidates_json TEXT,
                confidence REAL
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS model_runs (
                id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL,
                model_id TEXT NOT NULL,
                latency_ms INTEGER,
                tokens_in INTEGER,
                tokens_out INTEGER,
                cost_usd REAL,
                status TEXT NOT NULL DEFAULT 'success',
                fallback_used INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """))

        # Seed models
        await conn.execute(text("""
            INSERT INTO models VALUES
              ('gpt-4o-mini', 'openai', '["general"]', 128000, 0.72, 0.00015, 0.0006, 800, 1),
              ('llama3-8b-8192', 'groq', '["general"]', 8192, 0.58, 0.00005, 0.00008, 350, 1)
        """))

        # Two request rows
        req1 = str(uuid.uuid4())
        req2 = str(uuid.uuid4())

        await conn.execute(text("""
            INSERT INTO requests (id, strategy) VALUES (:r1, 'balanced'), (:r2, 'cost')
        """), {"r1": req1, "r2": req2})

        await conn.execute(text("""
            INSERT INTO routing_decisions (id, request_id, selected_model, reason, candidates_json, confidence)
            VALUES
              (:d1, :r1, 'gpt-4o-mini',    'Best quality match.', :cj1, 0.91),
              (:d2, :r2, 'llama3-8b-8192', 'Best cost match.',    :cj2, 0.80)
        """), {
            "d1": str(uuid.uuid4()), "r1": req1,
            "d2": str(uuid.uuid4()), "r2": req2,
            "cj1": '[{"model_id":"gpt-4o-mini","score":0.91}]',
            "cj2": '[{"model_id":"llama3-8b-8192","score":0.80}]',
        })

        await conn.execute(text("""
            INSERT INTO model_runs (id, request_id, model_id, latency_ms, tokens_in, tokens_out,
                                   cost_usd, status, fallback_used)
            VALUES
              (:m1, :r1, 'gpt-4o-mini',   1200, 100, 200, 0.000135, 'success', 0),
              (:m2, :r2, 'llama3-8b-8192', 400,  80, 150, 0.000016, 'success', 1)
        """), {"m1": str(uuid.uuid4()), "r1": req1,
               "m2": str(uuid.uuid4()), "r2": req2})

    yield engine, req1, req2
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def override_session(test_engine):
    engine, req1, req2 = test_engine
    TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _get_test_session() -> AsyncIterator[AsyncSession]:
        async with TestSession() as s:
            yield s

    app.dependency_overrides[get_session] = _get_test_session
    yield req1, req2
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests — GET /admin/routing-stats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_routing_stats_returns_correct_aggregates(override_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/admin/routing-stats")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_requests"] == 2
    assert data["success_rate"] == 1.0
    assert data["error_rate"] == 0.0
    assert data["fallback_rate"] == 0.5       # 1 of 2 used fallback
    assert data["avg_latency_ms"] == pytest.approx(800.0, abs=1)
    assert data["total_cost_usd"] == pytest.approx(0.000151, abs=1e-6)


@pytest.mark.asyncio
async def test_routing_stats_keys_present(override_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/admin/routing-stats")
    data = resp.json()
    for key in ("total_requests", "success_rate", "error_rate",
                "avg_latency_ms", "total_cost_usd", "fallback_rate"):
        assert key in data


# ---------------------------------------------------------------------------
# Tests — GET /admin/models-performance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_models_performance_returns_two_rows(override_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/admin/models-performance")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_models_performance_schema(override_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/admin/models-performance")
    row = resp.json()[0]
    for key in ("model_id", "total_requests", "success_rate", "avg_latency_ms", "total_cost_usd"):
        assert key in row


@pytest.mark.asyncio
async def test_models_performance_values(override_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/admin/models-performance")
    data = {row["model_id"]: row for row in resp.json()}
    assert data["gpt-4o-mini"]["total_requests"] == 1
    assert data["gpt-4o-mini"]["success_rate"] == 1.0
    assert data["llama3-8b-8192"]["total_requests"] == 1


# ---------------------------------------------------------------------------
# Tests — GET /admin/decisions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decisions_list_returns_two_rows(override_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/admin/decisions")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_decisions_list_schema(override_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/admin/decisions")
    row = resp.json()[0]
    for key in ("request_id", "created_at", "selected_model", "status", "cost_usd", "fallback_used"):
        assert key in row


@pytest.mark.asyncio
async def test_decisions_list_respects_limit(override_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/admin/decisions?limit=1")
    assert len(resp.json()) == 1


# ---------------------------------------------------------------------------
# Tests — GET /admin/decisions/{request_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decision_detail_returns_full_record(override_session):
    req1, _ = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/admin/decisions/{req1}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["request_id"] == req1
    assert data["routing_decision"]["selected_model"] == "gpt-4o-mini"
    assert data["model_run"]["model_id"] == "gpt-4o-mini"
    assert data["model_run"]["status"] == "success"
    assert data["model_run"]["fallback_used"] is False


@pytest.mark.asyncio
async def test_decision_detail_404_for_unknown_id(override_session):
    fake_id = str(uuid.uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/admin/decisions/{fake_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_decision_detail_422_for_bad_uuid(override_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/admin/decisions/not-a-uuid")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_decision_detail_has_prompt_meta_key(override_session):
    req1, _ = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/admin/decisions/{req1}")
    data = resp.json()
    assert "prompt_meta" in data
    assert "strategy" in data
