"""Load active models from the database."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model_registry import Model


async def load_active_models(session: AsyncSession) -> list[Model]:
    """Return all enabled models from the registry. Re-queries per request (no cache)."""
    result = await session.execute(
        select(Model).where(Model.enabled == True).order_by(Model.id)
    )
    return list(result.scalars().all())
