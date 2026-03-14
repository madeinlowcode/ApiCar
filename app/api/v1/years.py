from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from app.services.model_service import ModelService
from app.exceptions import NotFoundException

router = APIRouter(prefix="/model-years", tags=["model-years"])


@router.get("/{year_id}/categories")
async def get_year_categories(
    year_id: int,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    service = ModelService(db)
    result = await service.get_year_categories(year_id=year_id, page=page, per_page=per_page)
    if result is None:
        raise NotFoundException(f"Model year {year_id} not found")
    return result
