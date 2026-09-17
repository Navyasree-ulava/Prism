"""Integration tests for fallback behaviour — Phase 4.

Strategy
--------
- Use an in-process SQLite database with seeded model rows.
- Patch ``app.api.chat.route`` to return a deterministic RoutingResult with
  a two-model ranked list (primary + fallback).
- Patch the primary provider's ``generate`` to raise an httpx error.
- Assert the fallback model's ``generate`` is called and the response
  has ``fallback_used: true``.
- All tests use the HTTPX ASGI test client — no real HTTP calls.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.analyzer.heuristic_analyzer import AnalysisResult
from app.auth import verify_api_key
from app.db import get_session
from app.main import app
from app.routing.engine import RoutingResult
from app.schemas.chat import ChatMessage, ChatResponse, ChatResponseChoice

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
_AUTH = {"Authorization": "Bearer dev-local-key-change-me"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
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
            INSERT INTO models VALUES
              ('gpt-4o-mini',  'openai',    '["general","coding","reasoning"]',
               128000, 0.72, 0.00015, 0.0006, 800, 1),
              ('llama3-8b-8192', 'groq',   '["general","qa"]',
               8192,   0.58, 0.00005, 0.00008, 350, 1)
        """))
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def override_session(test_engine):
    TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def _get_test_session() -> AsyncIterator[AsyncSession]:
        async with TestSession() as s:
            yield s

    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _model_stub(model_id: str, provider: str) -> MagicMock:
    m = MagicMock()
    m.id = model_id
    m.provider = provider
    m.input_price_per_1k = 0.00015
    m.output_price_per_1k = 0.0006
    return m


def _scored_stub(model_id: str, provider: str, score: float = 0.85) -> MagicMock:
    s = MagicMock()
    s.model = _model_stub(model_id, provider)
    s.score = score
    return s


def _mock_routing_result_two_candidates() -> RoutingResult:
    """Two-model ranked list: openai primary, groq fallback."""
    analysis = AnalysisResult(
        task_type="general",
        complexity="low",
        required_capabilities=["general"],
        context_requirement="low",
        estimated_input_tokens=10,
        confidence=0.7,
    )
    primary = _scored_stub("gpt-4o-mini", "openai", score=0.90)
    fallback = _scored_stub("llama3-8b-8192", "groq", score=0.75)
    return RoutingResult(
        selected=primary.model,
        analysis=analysis,
        ranked=[primary, fallback],
        strategy="balanced",
        reason="Best cost efficiency match given 'balanced' strategy.",
    )


def _good_response(model: str = "gpt-4o-mini") -> ChatResponse:
    return ChatResponse(
        id=f"chatcmpl-{uuid.uuid4().hex}",
        model=model,
        choices=[
            ChatResponseChoice(
                index=0,
                message=ChatMessage(role="assistant", content="Hello!"),
                finish_reason="stop",
            )
        ],
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    )


def _http_503() -> httpx.HTTPStatusError:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 503
    return httpx.HTTPStatusError("503", request=MagicMock(), response=resp)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fallback_used_when_primary_fails(override_session):
    """Primary raises 503 → fallback model called → fallback_used=true."""
    routing = _mock_routing_result_two_candidates()
    fallback_response = _good_response("llama3-8b-8192")

    with (
        patch("app.api.chat.route", new=AsyncMock(return_value=routing)),
        # Reset health tracker so primary isn't pre-filtered.
        patch("app.api.chat._health_tracker") as mock_ht,
        patch("app.providers.openai_provider.OpenAIProvider.generate",
              new=AsyncMock(side_effect=_http_503())),
        patch("app.providers.groq_provider.GroqProvider.generate",
              new=AsyncMock(return_value=fallback_response)),
        patch("app.providers.openai_provider.OpenAIProvider.health_check",
              new=AsyncMock(return_value=True)),
        patch("app.providers.groq_provider.GroqProvider.health_check",
              new=AsyncMock(return_value=True)),
    ):
        # Mock health tracker: primary passes is_healthy, record_failure for primary,
        # then fallback passes is_healthy.
        mock_ht.is_healthy.return_value = True
        mock_ht.record_failure = MagicMock()
        mock_ht.record_success = MagicMock()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "Hello"}]},
                headers=_AUTH,
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["routing"]["fallback_used"] is True
    assert data["routing"]["selected_model"] == "llama3-8b-8192"


@pytest.mark.asyncio
async def test_no_fallback_when_primary_succeeds(override_session):
    """Primary succeeds → fallback_used=false."""
    routing = _mock_routing_result_two_candidates()
    primary_response = _good_response("gpt-4o-mini")

    with (
        patch("app.api.chat.route", new=AsyncMock(return_value=routing)),
        patch("app.api.chat._health_tracker") as mock_ht,
        patch("app.providers.openai_provider.OpenAIProvider.generate",
              new=AsyncMock(return_value=primary_response)),
        patch("app.providers.openai_provider.OpenAIProvider.health_check",
              new=AsyncMock(return_value=True)),
    ):
        mock_ht.is_healthy.return_value = True
        mock_ht.record_failure = MagicMock()
        mock_ht.record_success = MagicMock()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "Hello"}]},
                headers=_AUTH,
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["routing"]["fallback_used"] is False
    assert data["routing"]["selected_model"] == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_503_when_both_primary_and_fallback_fail(override_session):
    """Both providers fail → 503 returned to client."""
    routing = _mock_routing_result_two_candidates()

    with (
        patch("app.api.chat.route", new=AsyncMock(return_value=routing)),
        patch("app.api.chat._health_tracker") as mock_ht,
        patch("app.providers.openai_provider.OpenAIProvider.generate",
              new=AsyncMock(side_effect=_http_503())),
        patch("app.providers.groq_provider.GroqProvider.generate",
              new=AsyncMock(side_effect=_http_503())),
        patch("app.providers.openai_provider.OpenAIProvider.health_check",
              new=AsyncMock(return_value=True)),
        patch("app.providers.groq_provider.GroqProvider.health_check",
              new=AsyncMock(return_value=True)),
    ):
        mock_ht.is_healthy.return_value = True
        mock_ht.record_failure = MagicMock()
        mock_ht.record_success = MagicMock()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "Hello"}]},
                headers=_AUTH,
            )

    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_health_tracker_failure_recorded_for_failing_model(override_session):
    """Verify record_failure() is called for the primary model on failure."""
    routing = _mock_routing_result_two_candidates()
    fallback_response = _good_response("llama3-8b-8192")

    with (
        patch("app.api.chat.route", new=AsyncMock(return_value=routing)),
        patch("app.api.chat._health_tracker") as mock_ht,
        patch("app.providers.openai_provider.OpenAIProvider.generate",
              new=AsyncMock(side_effect=_http_503())),
        patch("app.providers.groq_provider.GroqProvider.generate",
              new=AsyncMock(return_value=fallback_response)),
        patch("app.providers.openai_provider.OpenAIProvider.health_check",
              new=AsyncMock(return_value=True)),
        patch("app.providers.groq_provider.GroqProvider.health_check",
              new=AsyncMock(return_value=True)),
    ):
        mock_ht.is_healthy.return_value = True
        mock_ht.record_failure = MagicMock()
        mock_ht.record_success = MagicMock()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "Hello"}]},
                headers=_AUTH,
            )

    # record_failure must have been called with the primary model id.
    primary_id = routing.ranked[0].model.id
    mock_ht.record_failure.assert_any_call(primary_id)
