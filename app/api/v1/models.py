from fastapi import APIRouter, Depends, Query
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from app.services.model_service import ModelService
from app.exceptions import NotFoundException

router = APIRouter(prefix="/models", tags=["models"])


@router.get("/{model_id}")
async def get_model(model_id: int, db: AsyncSession = Depends(get_db)):
    service = ModelService(db)
    result = await service.get_model(model_id)
    if result is None:
        raise NotFoundException(f"Model {model_id} not found")
    return result


@router.get("/{model_id}/years")
async def get_model_years(
    model_id: int,
    year: Optional[int] = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    service = ModelService(db)
    result = await service.get_model_years(model_id=model_id, year=year, page=page, per_page=per_page)
    if result is None:
        raise NotFoundException(f"Model {model_id} not found")
    return result
