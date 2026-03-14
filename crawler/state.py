"""Crawl queue state management with PostgreSQL."""
import structlog
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from shared.models.crawl_job import CrawlJob
from shared.models.crawl_queue import CrawlQueue

logger = structlog.get_logger()


class CrawlStateManager:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_job(self, brand_id: int | None, level: int) -> CrawlJob:
        """Create a new crawl job."""
        job = CrawlJob(brand_id=brand_id, level=level, status="pending")
        self.session.add(job)
        await self.session.flush()
        logger.info("crawl.job_created", job_id=job.id, level=level)
        return job

    async def start_job(self, job_id: int):
        """Mark job as running."""
        await self.session.execute(
            update(CrawlJob)
            .where(CrawlJob.id == job_id)
            .values(status="running", started_at=func.now())
        )
        await self.session.flush()

    async def complete_job(self, job_id: int):
        """Mark job as completed."""
        await self.session.execute(
            update(CrawlJob)
            .where(CrawlJob.id == job_id)
            .values(status="completed", completed_at=func.now())
        )
        await self.session.flush()

    async def fail_job(self, job_id: int, error: str):
        """Mark job as failed."""
        await self.session.execute(
            update(CrawlJob)
            .where(CrawlJob.id == job_id)
            .values(status="failed", error_message=error, completed_at=func.now())
        )
        await self.session.flush()

    async def enqueue_urls(
        self, job_id: int, urls: list[dict], level: int
    ):
        """Batch insert URLs into crawl queue.

        Each dict in urls should have: url, and optionally parent_*_id keys.
        """
        items = []
        for url_data in urls:
            item = CrawlQueue(
                job_id=job_id,
                url=url_data["url"],
                level=level,
                status="pending",
                parent_brand_id=url_data.get("parent_brand_id"),
                parent_model_id=url_data.get("parent_model_id"),
                parent_year_id=url_data.get("parent_year_id"),
                parent_category_id=url_data.get("parent_category_id"),
                parent_subgroup_id=url_data.get("parent_subgroup_id"),
            )
            items.append(item)
        self.session.add_all(items)
        await self.session.flush()
        logger.info("crawl.urls_enqueued", job_id=job_id, count=len(items), level=level)

    async def claim_next(self, job_id: int) -> CrawlQueue | None:
        """Atomically claim the next pending URL for processing.

        Uses FOR UPDATE SKIP LOCKED to avoid race conditions between workers.
        """
        # This requires PostgreSQL - for SQLite tests, use simpler query
        result = await self.session.execute(
            select(CrawlQueue)
            .where(CrawlQueue.job_id == job_id, CrawlQueue.status == "pending")
            .order_by(CrawlQueue.level, CrawlQueue.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        item = result.scalar_one_or_none()
        if item:
            item.status = "processing"
            item.processed_at = func.now()
            await self.session.flush()
            logger.info("crawl.url_claimed", queue_id=item.id, url=item.url[:80])
        return item

    async def mark_done(self, queue_id: int):
        """Mark a queue item as done."""
        await self.session.execute(
            update(CrawlQueue)
            .where(CrawlQueue.id == queue_id)
            .values(status="done")
        )
        await self.session.flush()

    async def mark_failed(self, queue_id: int, error_message: str):
        """Mark a queue item as failed and increment retry count."""
        result = await self.session.execute(
            select(CrawlQueue).where(CrawlQueue.id == queue_id)
        )
        item = result.scalar_one()
        item.retries += 1
        if item.retries >= item.max_retries:
            item.status = "failed"
        else:
            item.status = "pending"  # Will be retried
        item.error_message = error_message
        await self.session.flush()

    async def reset_stale(self, timeout_minutes: int = 10):
        """Reset URLs stuck in 'processing' state (stale detection)."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
        result = await self.session.execute(
            update(CrawlQueue)
            .where(
                CrawlQueue.status == "processing",
                CrawlQueue.processed_at < cutoff
            )
            .values(status="pending")
        )
        if result.rowcount and result.rowcount > 0:
            logger.warning("crawl.stale_reset", count=result.rowcount)
        await self.session.flush()

    async def get_progress(self, job_id: int) -> dict:
        """Get progress counters for a job."""
        result = await self.session.execute(
            select(
                CrawlQueue.status,
                func.count(CrawlQueue.id)
            )
            .where(CrawlQueue.job_id == job_id)
            .group_by(CrawlQueue.status)
        )
        counts = {row[0]: row[1] for row in result.all()}
        total = sum(counts.values())
        return {
            "total": total,
            "pending": counts.get("pending", 0),
            "processing": counts.get("processing", 0),
            "done": counts.get("done", 0),
            "failed": counts.get("failed", 0),
        }
