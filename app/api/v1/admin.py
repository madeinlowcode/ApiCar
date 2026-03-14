from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from app.dependencies import verify_api_key
from app.services.crawl_service import CrawlService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/crawl/status", dependencies=[Depends(verify_api_key)])
async def get_crawl_status(db: AsyncSession = Depends(get_db)):
    service = CrawlService(db)
    return await service.get_crawl_status()


@router.get("/crawl/failed", dependencies=[Depends(verify_api_key)])
async def get_crawl_failed(db: AsyncSession = Depends(get_db)):
    service = CrawlService(db)
    return await service.get_failed_crawls()


@router.post("/crawl/start")
async def start_crawl(
    brand_slug: str | None = None,
    db: AsyncSession = Depends(get_db),
    request: Request = None,
    _: str = Depends(verify_api_key),
):
    redis = request.app.state.redis_pool
    result = await CrawlService.trigger_crawl(db, redis, brand_slug)
    return result
