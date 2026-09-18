"""End-to-end: POST /v1/chat/completions → DB rows → GET /admin/decisions.

Regression coverage for Phase 5 persistence bug:
  SQLAlchemy unit-of-work was flushing `model_runs` INSERT before `requests`
  INSERT (alphabetical table ordering), causing a ForeignKeyViolationError on
  PostgreSQL.  Fixed by calling ``await session.flush([request_row])`` after
  adding the parent row so FK-dependent child rows see it.

These tests use SQLite with PRAGMA foreign_keys=ON so the same class of bug
would be caught here in CI (not just in live Docker/PostgreSQL runs).
"""
from __future__ import annotations

import uuid
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.analyzer.heuristic_analyzer import AnalysisResult
from app.db import get_session
from app.main import app
from app.routing.engine import RoutingResult
from app.schemas.chat import ChatMessage, ChatResponse, ChatResponseChoice

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
_AUTH = {"Authorization": "Bearer dev-local-key-change-me"}


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------


async def _create_full_schema(conn) -> None:
    """Create the minimal schema needed for Phase 5 logging tests in SQLite.

    FK references are declared explicitly so that PRAGMA foreign_keys=ON will
    enforce them at the same level PostgreSQL does.
    """
    await conn.execute(text("""
        CREATE TABLE IF NOT EXISTS models (
            id TEXT PRIMARY KEY, provider TEXT NOT NULL,
            capabilities TEXT NOT NULL DEFAULT '[]',
            context_window INTEGER NOT NULL, quality_score REAL NOT NULL,
            input_price_per_1k REAL NOT NULL, output_price_per_1k REAL NOT NULL,
            avg_latency_ms INTEGER NOT NULL, enabled INTEGER NOT NULL DEFAULT 1
        )
    """))
    # users table is referenced by requests.user_id FK
    await conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE
        )
    """))
    await conn.execute(text("""
        CREATE TABLE IF NOT EXISTS requests (
            id TEXT PRIMARY KEY,
            user_id TEXT REFERENCES users(id),
            prompt_meta TEXT,
            strategy TEXT NOT NULL DEFAULT 'balanced',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """))
    await conn.execute(text("""
        CREATE TABLE IF NOT EXISTS routing_decisions (
            id TEXT PRIMARY KEY,
            request_id TEXT NOT NULL REFERENCES requests(id),
            selected_model TEXT NOT NULL REFERENCES models(id),
            reason TEXT, candidates_json TEXT, confidence REAL
        )
    """))
    await conn.execute(text("""
        CREATE TABLE IF NOT EXISTS model_runs (
            id TEXT PRIMARY KEY,
            request_id TEXT NOT NULL REFERENCES requests(id),
            model_id TEXT NOT NULL REFERENCES models(id),
            latency_ms INTEGER, tokens_in INTEGER, tokens_out INTEGER,
            cost_usd REAL, status TEXT NOT NULL DEFAULT 'success',
            fallback_used INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """))
    await conn.execute(text("""
        INSERT INTO models VALUES
          ('gpt-4o-mini',   'openai', '["general","coding"]', 128000, 0.72, 0.00015, 0.0006,  800, 1),
          ('llama3-8b-8192','groq',   '["general","qa"]',      8192,  0.58, 0.00005, 0.00008, 350, 1)
    """))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def full_db_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)

    # Enforce FK constraints on every SQLite connection so the same
    # ForeignKeyViolationError we fixed in PostgreSQL would surface in tests.
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await _create_full_schema(conn)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def full_db_session(full_db_engine):
    TestSession = async_sessionmaker(full_db_engine, class_=AsyncSession, expire_on_commit=False)

    async def _get_test_session() -> AsyncIterator[AsyncSession]:
        async with TestSession() as s:
            yield s

    app.dependency_overrides[get_session] = _get_test_session
    yield TestSession
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _routing_result() -> RoutingResult:
    primary = MagicMock()
    primary.id = "gpt-4o-mini"
    primary.provider = "openai"
    primary.input_price_per_1k = 0.00015
    primary.output_price_per_1k = 0.0006

    scored = MagicMock()
    scored.model = primary
    scored.score = 0.85

    analysis = AnalysisResult(
        task_type="general", complexity="low",
        required_capabilities=["general"], context_requirement="low",
        estimated_input_tokens=10, confidence=0.6,
    )
    return RoutingResult(
        selected=primary, analysis=analysis, ranked=[scored],
        strategy="balanced", reason="Best quality match given 'balanced' strategy.",
    )


def _mock_response() -> ChatResponse:
    return ChatResponse(
        id=f"chatcmpl-{uuid.uuid4().hex}",
        model="gpt-4o-mini",
        choices=[ChatResponseChoice(
            index=0, message=ChatMessage(role="assistant", content="Hi!"),
            finish_reason="stop",
        )],
        usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_log_request_persists_all_three_rows(full_db_engine):
    """log_request() writes requests + routing_decisions + model_runs atomically.

    Regression test for: SQLAlchemy unit-of-work flushing `model_runs` INSERT
    before `requests` INSERT (alphabetical table ordering) causing a
    ForeignKeyViolationError on PostgreSQL.  The fix is an explicit
    ``await session.flush([request_row])`` after adding the parent row.

    SQLite FK enforcement (PRAGMA foreign_keys=ON) is active for this engine
    fixture, so the same class of bug will be caught here in CI.
    """
    from app.services.request_logger import log_request

    TestSession = async_sessionmaker(full_db_engine, class_=AsyncSession, expire_on_commit=False)
    routing = _routing_result()
    response = _mock_response()

    async with TestSession() as session:
        await log_request(
            session=session,
            routing_result=routing,
            response=response,
            actual_model=routing.selected,
            latency_ms=250,
            fallback_used=False,
            strategy="balanced",
            cost_usd=0.000045,
            status="success",
        )

    # Verify all three tables received exactly one row each.
    async with TestSession() as session:
        req_count = (await session.execute(text("SELECT COUNT(*) FROM requests"))).scalar()
        rd_count  = (await session.execute(text("SELECT COUNT(*) FROM routing_decisions"))).scalar()
        mr_count  = (await session.execute(text("SELECT COUNT(*) FROM model_runs"))).scalar()

    assert req_count == 1, f"Expected 1 requests row, got {req_count}"
    assert rd_count  == 1, f"Expected 1 routing_decisions row, got {rd_count}"
    assert mr_count  == 1, f"Expected 1 model_runs row, got {mr_count}"


@pytest.mark.asyncio
async def test_chat_request_appears_in_admin_decisions(full_db_session):
    """Successful chat → row visible via GET /admin/decisions."""
    routing = _routing_result()
    mock_resp = _mock_response()

    with patch("app.api.chat.route", new=AsyncMock(return_value=routing)), \
         patch("app.providers.openai_provider.OpenAIProvider.generate",
               new=AsyncMock(return_value=mock_resp)):

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "Hello"}]},
                headers=_AUTH,
            )
            assert resp.status_code == 200

            admin = await client.get("/admin/decisions?limit=10")

    assert admin.status_code == 200
    rows = admin.json()
    assert len(rows) == 1
    assert rows[0]["selected_model"] == "gpt-4o-mini"
    assert rows[0]["status"] == "success"
    assert rows[0]["cost_usd"] > 0


@pytest.mark.asyncio
async def test_failed_chat_logged_with_error_status(full_db_session):
    """503 from FallbackError → error row in admin stats."""
    routing = _routing_result()

    from app.reliability.fallback import FallbackError

    with patch("app.api.chat.route", new=AsyncMock(return_value=routing)), \
         patch("app.api.chat.call_with_fallback",
               new=AsyncMock(side_effect=FallbackError("all failed"))):

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "Hello"}]},
                headers=_AUTH,
            )
            assert resp.status_code == 503

            stats = await client.get("/admin/routing-stats")

    data = stats.json()
    assert data["total_requests"] == 1
    assert data["error_rate"] == 1.0
    assert data["success_rate"] == 0.0


@pytest.mark.asyncio
async def test_cost_uses_actual_token_counts(full_db_session):
    """Routing cost reflects provider usage tokens, not estimates only."""
    routing = _routing_result()
    mock_resp = _mock_response()

    with patch("app.api.chat.route", new=AsyncMock(return_value=routing)), \
         patch("app.providers.openai_provider.OpenAIProvider.generate",
               new=AsyncMock(return_value=mock_resp)):

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "Hello"}]},
                headers=_AUTH,
            )

    # 100 in × 0.00015/1k + 50 out × 0.0006/1k = 0.000015 + 0.000030 = 0.000045
    assert resp.json()["routing"]["cost_usd"] == pytest.approx(0.000045, abs=1e-9)
