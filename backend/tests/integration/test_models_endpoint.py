"""
Integration test for GET /v1/models.

Strategy: use an in-process SQLite database (via aiosqlite) so the test
is fully self-contained — no external Postgres required. The test:
  1. Creates tables in a fresh in-memory SQLite DB.
  2. Seeds the same 3 models as seed.py.
  3. Overrides FastAPI's get_session dependency.
  4. Calls GET /v1/models and asserts the 3 expected model IDs are returned.
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.db import Base, get_session
from app.main import app
from app.models.model_registry import Model

# ---------------------------------------------------------------------------
# In-memory SQLite engine (no Postgres needed in CI / local test runs)
# ---------------------------------------------------------------------------
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

SEED_MODELS = [
    Model(
        id="gpt-4o-mini",
        provider="openai",
        capabilities=["general", "coding", "reasoning", "qa"],
        context_window=128_000,
        quality_score=0.72,
        input_price_per_1k=0.000150,
        output_price_per_1k=0.000600,
        avg_latency_ms=800,
        enabled=True,
    ),
    Model(
        id="claude-3-haiku-20240307",
        provider="anthropic",
        capabilities=["general", "summarization", "coding", "reasoning", "long_context"],
        context_window=200_000,
        quality_score=0.78,
        input_price_per_1k=0.000250,
        output_price_per_1k=0.001250,
        avg_latency_ms=950,
        enabled=True,
    ),
    Model(
        id="llama3-8b-8192",
        provider="groq",
        capabilities=["general", "qa", "summarization"],
        context_window=8_192,
        quality_score=0.58,
        input_price_per_1k=0.000050,
        output_price_per_1k=0.000080,
        avg_latency_ms=350,
        enabled=True,
    ),
]


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Fresh in-memory SQLite engine per test function."""
    engine = create_async_engine(TEST_DB_URL, echo=False)

    # SQLite doesn't support ARRAY type — patch columns to use JSON-stored lists
    # We monkeypatch at the engine level via a connect event.
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as conn:
        # SQLite-compatible table creation (no ARRAY, no UUID type issues)
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

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def seeded_session(test_engine):
    """Session with 3 models seeded, overrides app dependency."""
    TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        for m in SEED_MODELS:
            # Insert using raw SQL to avoid SQLAlchemy ARRAY type issues with SQLite
            await session.execute(
                text(
                    "INSERT OR IGNORE INTO models "
                    "(id, provider, capabilities, context_window, quality_score, "
                    " input_price_per_1k, output_price_per_1k, avg_latency_ms, enabled) "
                    "VALUES (:id, :provider, :caps, :ctx, :qs, :ip, :op, :lat, :en)"
                ),
                {
                    "id": m.id,
                    "provider": m.provider,
                    "caps": str(m.capabilities),
                    "ctx": m.context_window,
                    "qs": m.quality_score,
                    "ip": m.input_price_per_1k,
                    "op": m.output_price_per_1k,
                    "lat": m.avg_latency_ms,
                    "en": 1 if m.enabled else 0,
                },
            )
        await session.commit()

    # Return a fresh session for dependency override
    session = TestSession()
    yield session
    await session.close()


@pytest.mark.asyncio
async def test_get_models_returns_three_rows(test_engine, seeded_session):
    """GET /v1/models should return the 3 seeded models."""
    TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_session():
        async with TestSession() as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/models")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

        returned_ids = {m["id"] for m in data}
        assert "gpt-4o-mini" in returned_ids
        assert "claude-3-haiku-20240307" in returned_ids
        assert "llama3-8b-8192" in returned_ids
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_models_schema(test_engine):
    """Each model in the response must have all required fields."""
    TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_session():
        async with TestSession() as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/models")

        required_fields = {
            "id", "provider", "capabilities", "context_window",
            "quality_score", "input_price_per_1k", "output_price_per_1k",
            "avg_latency_ms", "enabled",
        }
        for model in response.json():
            assert required_fields.issubset(model.keys()), f"Missing fields in {model}"
    finally:
        app.dependency_overrides.clear()
