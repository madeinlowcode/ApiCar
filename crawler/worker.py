"""arq worker entry point for async crawl processing."""
import structlog
from arq import create_pool
from arq.connections import RedisSettings
from shared.config import settings
from shared.logging import setup_logging
from shared.database import AsyncSessionLocal
from crawler.browser import BrowserPool
from crawler.rate_limiter import RateLimiter, RateLimitConfig
from crawler.state import CrawlStateManager
from crawler.engine import CrawlEngine

logger = structlog.get_logger()


async def process_crawl_job(ctx: dict, job_id: int):
    """Process all pending URLs for a crawl job."""
    setup_logging()

    async with BrowserPool(pool_size=1, headless=True) as browser:
        rate_limiter = RateLimiter(RateLimitConfig())

        async with AsyncSessionLocal() as session:
            state = CrawlStateManager(session)
            engine = CrawlEngine(browser, rate_limiter, state)

            await engine.run_job(job_id)
            await session.commit()


async def start_brand_crawl(ctx: dict, brand_slug: str):
    """Initialize a full crawl for a brand."""
    setup_logging()

    async with AsyncSessionLocal() as session:
        from shared.models.brand import Brand
        from sqlalchemy import select

        result = await session.execute(
            select(Brand).where(Brand.slug == brand_slug)
        )
        brand = result.scalar_one_or_none()
        if not brand:
            logger.error("crawl.brand_not_found", slug=brand_slug)
            return

        state = CrawlStateManager(session)
        job = await state.create_job(brand_id=brand.id, level=2)
        await state.enqueue_urls(
            job.id,
            [{"url": brand.catalog_url, "parent_brand_id": brand.id}],
            level=2
        )
        await session.commit()

        logger.info("crawl.brand_crawl_queued", brand=brand_slug, job_id=job.id)

    # Now process the job
    await process_crawl_job(ctx, job.id)


class WorkerSettings:
    """arq worker configuration."""
    functions = [process_crawl_job, start_brand_crawl]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = 1
    job_timeout = 3600  # 1 hour — crawl jobs process many URLs in a loop
    max_tries = 3
    health_check_interval = 30
