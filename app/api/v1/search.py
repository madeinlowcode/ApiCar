from fastapi import APIRouter, Depends, Query
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from app.services.parts_service import PartsService

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
async def search_parts(
    q: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    service = PartsService(db)
    if q:
        return await service.search(query_str=q, page=page, per_page=per_page)
    # Empty search
    return {
        "items": [],
        "total": 0,
        "page": page,
        "per_page": per_page,
        "pages": 0,
    }
