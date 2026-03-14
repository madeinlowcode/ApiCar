from fastapi import APIRouter, Depends, Query
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from app.services.brand_service import BrandService
from app.exceptions import NotFoundException

router = APIRouter(prefix="/brands", tags=["brands"])


@router.get("")
async def get_brands(
    region: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    service = BrandService(db)
    return await service.list_brands(region=region, search=search, page=page, per_page=per_page)


@router.get("/{slug}")
async def get_brand_by_slug(slug: str, db: AsyncSession = Depends(get_db)):
    service = BrandService(db)
    result = await service.get_brand_by_slug(slug)
    if result is None:
        raise NotFoundException(f"Brand '{slug}' not found")
    return result


@router.get("/{slug}/models")
async def get_brand_models(
    slug: str,
    market_id: Optional[int] = Query(default=None),
    search: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    service = BrandService(db)
    result = await service.get_brand_models(slug=slug, market_id=market_id, search=search, page=page, per_page=per_page)
    if result is None:
        raise NotFoundException(f"Brand '{slug}' not found")
    return result
