"""Integration tests for streaming chat + routing_metadata SSE event."""
from __future__ import annotations

import json
import uuid
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.analyzer.heuristic_analyzer import AnalysisResult
from app.db import get_session
from app.main import app
from app.routing.engine import RoutingResult

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
_AUTH = {"Authorization": "Bearer dev-local-key-change-me"}


@pytest_asyncio.fixture(scope="function")
async def stream_db_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS models (
                id TEXT PRIMARY KEY, provider TEXT NOT NULL,
                capabilities TEXT NOT NULL DEFAULT '[]',
                context_window INTEGER NOT NULL, quality_score REAL NOT NULL,
                input_price_per_1k REAL NOT NULL, output_price_per_1k REAL NOT NULL,
                avg_latency_ms INTEGER NOT NULL, enabled INTEGER NOT NULL DEFAULT 1
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS requests (
                id TEXT PRIMARY KEY, user_id TEXT, prompt_meta TEXT,
                strategy TEXT NOT NULL DEFAULT 'balanced',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS routing_decisions (
                id TEXT PRIMARY KEY, request_id TEXT NOT NULL,
                selected_model TEXT NOT NULL, reason TEXT,
                candidates_json TEXT, confidence REAL
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS model_runs (
                id TEXT PRIMARY KEY, request_id TEXT NOT NULL, model_id TEXT NOT NULL,
                latency_ms INTEGER, tokens_in INTEGER, tokens_out INTEGER,
                cost_usd REAL, status TEXT NOT NULL DEFAULT 'success',
                fallback_used INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """))
        await conn.execute(text("""
            INSERT INTO models VALUES
              ('gpt-4o-mini', 'openai', '["general"]', 128000, 0.72, 0.00015, 0.0006, 800, 1)
        """))
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def stream_db_session(stream_db_engine):
    TestSession = async_sessionmaker(stream_db_engine, class_=AsyncSession, expire_on_commit=False)

    async def _get_test_session() -> AsyncIterator[AsyncSession]:
        async with TestSession() as s:
            yield s

    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.clear()


def _routing_result() -> RoutingResult:
    model = MagicMock()
    model.id = "gpt-4o-mini"
    model.provider = "openai"
    model.input_price_per_1k = 0.00015
    model.output_price_per_1k = 0.0006

    scored = MagicMock()
    scored.model = model
    scored.score = 0.9

    analysis = AnalysisResult(
        task_type="general", complexity="low",
        required_capabilities=["general"], context_requirement="low",
        estimated_input_tokens=5, confidence=0.6,
    )
    return RoutingResult(
        selected=model, analysis=analysis, ranked=[scored],
        strategy="balanced", reason="Best quality match.",
    )


async def _fake_stream(_self, _request):
    yield "Hello"
    yield " world"


def _parse_sse(raw: str) -> list[tuple[str | None, str]]:
    """Return list of (event_name, data) from SSE body."""
    events: list[tuple[str | None, str]] = []
    current_event: str | None = None
    for line in raw.split("\n"):
        if line.startswith("event: "):
            current_event = line[7:].strip()
        elif line.startswith("data: "):
            events.append((current_event, line[6:].strip()))
            current_event = None
    return events


@pytest.mark.asyncio
async def test_streaming_emits_routing_metadata_event(stream_db_session):
    routing = _routing_result()

    with patch("app.api.chat.route", new=AsyncMock(return_value=routing)), \
         patch("app.providers.openai_provider.OpenAIProvider.stream", new=_fake_stream):

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "Hi"}], "stream": True},
                headers=_AUTH,
            )

    assert resp.status_code == 200
    events = _parse_sse(resp.text)

    routing_events = [(e, d) for e, d in events if e == "routing_metadata"]
    assert len(routing_events) == 1

    meta = json.loads(routing_events[0][1])
    assert meta["selected_model"] == "gpt-4o-mini"
    assert meta["strategy"] == "balanced"
    assert "candidates" in meta
    assert meta["fallback_used"] is False

    assert any(d == "[DONE]" for _, d in events)
