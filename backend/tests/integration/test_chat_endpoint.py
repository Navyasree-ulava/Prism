"""
Integration tests for POST /v1/chat/completions — Phase 3 (routing engine wired).

Strategy:
  - In-process SQLite DB (same pattern as other integration tests).
  - `app.routing.engine.route` is patched per test to return a deterministic
    RoutingResult, so no real scoring or DB-dependent routing runs.
  - Provider generate() is mocked — no real HTTP calls.
  - verify_api_key dependency is overridden for auth tests.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth import verify_api_key
from app.db import get_session
from app.main import app
from app.routing.engine import RoutingResult
from app.analyzer.heuristic_analyzer import AnalysisResult
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
              ('gpt-4o-mini',             'openai',    '["general","coding","reasoning","qa"]',
               128000, 0.72, 0.00015, 0.0006,  800,  1),
              ('claude-3-haiku-20240307', 'anthropic', '["general","summarization","coding","reasoning"]',
               200000, 0.78, 0.00025, 0.00125, 950,  1),
              ('llama3-8b-8192',          'groq',      '["general","qa"]',
               8192,   0.58, 0.00005, 0.00008, 350,  1)
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


def _mock_response(model: str = "gpt-4o-mini") -> ChatResponse:
    return ChatResponse(
        id=f"chatcmpl-{uuid.uuid4().hex}",
        model=model,
        choices=[
            ChatResponseChoice(
                index=0,
                message=ChatMessage(role="assistant", content="Hello from mock!"),
                finish_reason="stop",
            )
        ],
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    )


def _mock_routing_result(model_id: str = "gpt-4o-mini", provider: str = "openai") -> RoutingResult:
    """Build a minimal RoutingResult for patching engine.route()."""
    model_stub = MagicMock()
    model_stub.id = model_id
    model_stub.provider = provider
    model_stub.input_price_per_1k = 0.00015
    model_stub.output_price_per_1k = 0.0006

    scored = MagicMock()
    scored.model = model_stub
    scored.score = 0.85

    analysis = AnalysisResult(
        task_type="general",
        complexity="low",
        required_capabilities=["general"],
        context_requirement="low",
        estimated_input_tokens=10,
        confidence=0.6,
    )

    return RoutingResult(
        selected=model_stub,
        analysis=analysis,
        ranked=[scored],
        strategy="balanced",
        reason="Best cost efficiency match given 'balanced' strategy.",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_completions_success(override_session):
    """Full path: routing + generate → 200 with routing object."""
    mock_resp = _mock_response()
    mock_routing = _mock_routing_result()

    with patch("app.api.chat.route", new=AsyncMock(return_value=mock_routing)), \
         patch("app.providers.openai_provider.OpenAIProvider.health_check", new=AsyncMock(return_value=True)), \
         patch("app.providers.openai_provider.OpenAIProvider.generate", new=AsyncMock(return_value=mock_resp)):

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "Hello"}]},
                headers=_AUTH,
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["object"] == "chat.completion"
    assert "routing" in data
    assert data["routing"]["selected_model"] == "gpt-4o-mini"
    assert data["routing"]["strategy"] == "balanced"
    assert "candidates" in data["routing"]
    assert "cost_usd" in data["routing"]


@pytest.mark.asyncio
async def test_chat_completions_provider_unavailable(override_session):
    """When all providers fail (e.g. no API key configured), 503 is returned.

    Phase 4 note: the explicit health_check guard was removed. An unconfigured
    provider key now causes a non-retryable error inside call_with_fallback,
    which exhausts all candidates and surfaces a FallbackError → 503.
    """
    mock_routing = _mock_routing_result()

    # Simulate both primary and any fallback raising immediately (non-retryable)
    # by mocking call_with_fallback directly to raise FallbackError.
    from app.reliability.fallback import FallbackError

    with patch("app.api.chat.route", new=AsyncMock(return_value=mock_routing)), \
         patch("app.api.chat.call_with_fallback", new=AsyncMock(side_effect=FallbackError("no providers available"))):

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "Hello"}]},
                headers=_AUTH,
            )

    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_chat_request_schema_validation(override_session):
    """Missing 'messages' → 422 Unprocessable Entity."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o-mini"},
            headers=_AUTH,
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_chat_completions_no_auth(override_session):
    """Missing Authorization header → 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "Hello"}]},
            # No Authorization header
        )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_chat_completions_wrong_auth(override_session):
    """Wrong API key → 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "Hello"}]},
            headers={"Authorization": "Bearer wrong-key-123"},
        )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_x_routing_strategy_header_forwarded(override_session):
    """X-Routing-Strategy header value is passed to the routing engine."""
    mock_resp = _mock_response()
    mock_routing = _mock_routing_result()
    captured_strategy: list[str] = []

    async def fake_route(messages, strategy, session, health_tracker=None):
        captured_strategy.append(strategy)
        return mock_routing

    with patch("app.api.chat.route", new=fake_route), \
         patch("app.providers.openai_provider.OpenAIProvider.health_check", new=AsyncMock(return_value=True)), \
         patch("app.providers.openai_provider.OpenAIProvider.generate", new=AsyncMock(return_value=mock_resp)):

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "Hello"}]},
                headers={**_AUTH, "x-routing-strategy": "cost"},
            )

    assert captured_strategy == ["cost"]
