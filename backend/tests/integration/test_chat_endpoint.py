"""
Integration tests for POST /v1/chat/completions.

Strategy:
  - In-process SQLite DB (same pattern as test_models_endpoint.py).
  - Provider `generate()` is monkey-patched so no real HTTP calls are made.
  - Four test cases: success, 404 (unknown model), 503 (key missing), 422 (bad schema).
"""
import uuid
from typing import AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import get_session
from app.main import app
from app.schemas.chat import ChatMessage, ChatResponse, ChatResponseChoice

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Fresh in-memory SQLite engine with the models table seeded."""
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
        # Seed one model per provider so all paths are reachable.
        await conn.execute(text("""
            INSERT INTO models VALUES
              ('gpt-4o-mini',             'openai',    '[]', 128000, 0.72, 0.00015, 0.0006, 800,  1),
              ('claude-3-haiku-20240307', 'anthropic', '[]', 200000, 0.78, 0.00025, 0.0013, 950,  1),
              ('llama3-8b-8192',          'groq',      '[]',   8192, 0.58, 0.00005, 0.00008, 350, 1)
        """))

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def override_session(test_engine):
    """Override FastAPI's DB dependency with our SQLite engine."""
    TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def _get_test_session() -> AsyncIterator[AsyncSession]:
        async with TestSession() as s:
            yield s

    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helper: a valid ChatResponse the mock provider returns
# ---------------------------------------------------------------------------
def _make_mock_response(model: str) -> ChatResponse:
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_completions_success(override_session):
    """A well-formed request with a healthy provider → 200 with correct shape."""
    mock_response = _make_mock_response("gpt-4o-mini")

    with patch(
        "app.providers.openai_provider.OpenAIProvider.health_check",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.providers.openai_provider.OpenAIProvider.generate",
        new=AsyncMock(return_value=mock_response),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": "Hello"}],
                },
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["object"] == "chat.completion"
    assert data["model"] == "gpt-4o-mini"
    assert len(data["choices"]) == 1
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert data["choices"][0]["finish_reason"] == "stop"
    assert "usage" in data


@pytest.mark.asyncio
async def test_chat_completions_model_not_found(override_session):
    """Requesting a model not in the DB → 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/chat/completions",
            json={
                "model": "nonexistent-model-xyz",
                "messages": [{"role": "user", "content": "Hi"}],
            },
        )

    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_chat_completions_provider_unavailable(override_session):
    """When health_check() → False the endpoint returns 503 with provider_unavailable."""
    with patch(
        "app.providers.openai_provider.OpenAIProvider.health_check",
        new=AsyncMock(return_value=False),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": "Hi"}],
                },
            )

    assert resp.status_code == 503
    detail = resp.json()["detail"]
    assert detail["error"] == "provider_unavailable"


@pytest.mark.asyncio
async def test_chat_request_schema_validation(override_session):
    """A request missing the required 'messages' field → 422 Unprocessable Entity."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o-mini"},  # 'messages' omitted
        )

    assert resp.status_code == 422
