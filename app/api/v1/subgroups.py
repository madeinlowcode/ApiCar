from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from app.services.model_service import ModelService
from app.exceptions import NotFoundException

router = APIRouter(prefix="/subgroups", tags=["subgroups"])


@router.get("/{subgroup_id}/parts")
async def get_subgroup_parts(
    subgroup_id: int,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    service = ModelService(db)
    result = await service.get_subgroup_parts(subgroup_id=subgroup_id, page=page, per_page=per_page)
    if result is None:
        raise NotFoundException(f"Subgroup {subgroup_id} not found")
    return result
