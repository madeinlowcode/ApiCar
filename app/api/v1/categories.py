from fastapi import APIRouter, Depends, Query
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from app.services.model_service import ModelService
from app.exceptions import NotFoundException

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("/{category_id}/subgroups")
async def get_category_subgroups(
    category_id: int,
    search: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    service = ModelService(db)
    result = await service.get_category_subgroups(category_id=category_id, search=search, page=page, per_page=per_page)
    if result is None:
        raise NotFoundException(f"Category {category_id} not found")
    return result
