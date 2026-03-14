from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.brand import Brand
from shared.models.crawl_job import CrawlJob


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
        brand_id = None
        if brand_slug:
            result = await db.execute(select(Brand).where(Brand.slug == brand_slug))
            brand = result.scalar_one_or_none()
            if brand is None:
                raise ValueError(f"Brand with slug '{brand_slug}' not found")
            brand_id = brand.id

        job = CrawlJob(
            brand_id=brand_id,
            level=0,
            status="pending",
            progress={},
        )
        db.add(job)
        await db.flush()

        await redis.enqueue_job("process_crawl_job", job.id)

        await db.commit()

        return {
            "id": job.id,
            "status": job.status,
            "brand_slug": brand_slug,
        }
