"""High-level task functions for crawl operations."""
import structlog
from arq import create_pool
from arq.connections import RedisSettings
from shared.config import settings

logger = structlog.get_logger()


async def enqueue_brand_crawl(brand_slug: str):
    """Enqueue a brand crawl job via arq."""
    redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    job = await redis.enqueue_job("start_brand_crawl", brand_slug)
    logger.info("task.brand_crawl_enqueued", brand=brand_slug, job_id=job.job_id)
    return job.job_id


async def enqueue_crawl_job(job_id: int):
    """Enqueue processing of an existing crawl job."""
    redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    job = await redis.enqueue_job("process_crawl_job", job_id)
    logger.info("task.crawl_job_enqueued", job_id=job_id, arq_job=job.job_id)
    return job.job_id
