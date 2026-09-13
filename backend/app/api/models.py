from typing import Sequence

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.model_registry import Model
from app.schemas.admin import ModelOut

router = APIRouter()


@router.get("/models", response_model=list[ModelOut])
async def list_models(session: AsyncSession = Depends(get_session)) -> Sequence[Model]:
    result = await session.execute(select(Model).where(Model.enabled == True))
    return result.scalars().all()
