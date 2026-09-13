"""
Idempotent seed script — inserts 3 real models into the `models` table.
Run once on container start; skips if already seeded.

Pricing sourced from official provider pages (September 2026):
  gpt-4o-mini:          $0.150 / $0.600  per 1M tokens (in/out)
  claude-3-haiku:       $0.250 / $1.250  per 1M tokens (in/out)
  llama3-8b-8192 Groq:  $0.050 / $0.080  per 1M tokens (in/out)  [free tier available]
Per-1K values = per-1M / 1000.
"""
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.config import settings
from app.models.model_registry import Model

SEED_MODELS = [
    Model(
        id="gpt-4o-mini",
        provider="openai",
        capabilities=["general", "coding", "reasoning", "qa"],
        context_window=128_000,
        quality_score=0.72,
        input_price_per_1k=0.000150,   # $0.150 / 1M
        output_price_per_1k=0.000600,  # $0.600 / 1M
        avg_latency_ms=800,
        enabled=True,
    ),
    Model(
        id="claude-3-haiku-20240307",
        provider="anthropic",
        capabilities=["general", "summarization", "coding", "reasoning", "long_context"],
        context_window=200_000,
        quality_score=0.78,
        input_price_per_1k=0.000250,   # $0.250 / 1M
        output_price_per_1k=0.001250,  # $1.250 / 1M
        avg_latency_ms=950,
        enabled=True,
    ),
    Model(
        id="llama3-8b-8192",
        provider="groq",
        capabilities=["general", "qa", "summarization"],
        context_window=8_192,
        quality_score=0.58,
        input_price_per_1k=0.000050,   # $0.050 / 1M
        output_price_per_1k=0.000080,  # $0.080 / 1M
        avg_latency_ms=350,
        enabled=True,
    ),
]


async def seed() -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        for model in SEED_MODELS:
            existing = await session.get(Model, model.id)
            if existing is None:
                session.add(model)
                print(f"  ✓ Seeded model: {model.id}")
            else:
                print(f"  - Skipped (already exists): {model.id}")
        await session.commit()

    await engine.dispose()
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
