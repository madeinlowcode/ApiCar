from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.brand import Brand
from shared.models.crawl_job import CrawlJob
from shared.config import settings


class CrawlService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_crawl_status(self):
        result = await self.db.execute(select(CrawlJob).order_by(CrawlJob.id.desc()).limit(50))
        jobs = result.scalars().all()

        job_list = [
            {
                "id": j.id,
                "brand_id": j.brand_id,
                "level": j.level,
                "status": j.status,
                "progress": j.progress,
                "error_message": j.error_message,
                "started_at": j.started_at.isoformat() if j.started_at else None,
                "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            }
            for j in jobs
        ]

        return {"jobs": job_list}

    async def get_failed_crawls(self):
        result = await self.db.execute(
            select(CrawlJob).where(CrawlJob.status == "failed").order_by(CrawlJob.id.desc())
        )
        jobs = result.scalars().all()

        items = [
            {
                "id": j.id,
                "brand_id": j.brand_id,
                "level": j.level,
                "status": j.status,
                "error_message": j.error_message,
            }
            for j in jobs
        ]

        return {"items": items}

    @staticmethod
    async def trigger_crawl(db: AsyncSession, redis, brand_slug: str = None):
        from shared.models.crawl_queue import CrawlQueue

        brand_id = None
        start_level = 1
        start_url = "https://www.catcar.info/"
        parent_kwargs = {}

        if brand_slug:
            result = await db.execute(select(Brand).where(Brand.slug == brand_slug))
            brand = result.scalar_one_or_none()
            if brand is None:
                raise ValueError(f"Brand with slug '{brand_slug}' not found")
            brand_id = brand.id
            start_level = 2
            start_url = brand.catalog_url
            parent_kwargs = {"parent_brand_id": brand.id}

        job = CrawlJob(
            brand_id=brand_id,
            level=start_level,
            status="pending",
        )
        db.add(job)
        await db.flush()

        queue_item = CrawlQueue(
            job_id=job.id,
            url=start_url,
            level=start_level,
            status="pending",
            **parent_kwargs,
        )
        db.add(queue_item)
        await db.flush()

        from arq import create_pool as arq_create_pool
        from arq.connections import RedisSettings
        arq_redis = await arq_create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        await arq_redis.enqueue_job("process_crawl_job", job.id)
        await arq_redis.close()

        await db.commit()

        return {
            "id": job.id,
            "status": job.status,
            "brand_slug": brand_slug,
            "level": start_level,
        }
