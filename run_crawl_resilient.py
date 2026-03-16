"""Resilient crawl runner — auto-resumes on crash.

Designed to run as PID 1 in a Docker container with restart: unless-stopped.
If the crawl crashes, it automatically resumes from the last state.

Usage:
    python run_crawl_resilient.py [--level N] [--job JOB_ID]

Docker will restart the container on crash, and this script will:
1. Find or create the crawl job
2. Reset stale "processing" items
3. Continue from where it left off
4. Exit 0 when all levels are done (container stops)
5. Exit 1 on crash (container restarts automatically)
"""
import asyncio
import argparse
import sys
import time
import signal
from datetime import datetime

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from crawler.browser import BrowserPool
from crawler.rate_limiter import RateLimiter, RateLimitConfig
from crawler.state import CrawlStateManager
from crawler.engine import CrawlEngine
from shared.config import settings


# ── Graceful shutdown ────────────────────────────────────────────
shutdown_requested = False

def handle_signal(signum, frame):
    global shutdown_requested
    print(f"\n  [{ts()}] Received signal {signum}, finishing current URL...")
    shutdown_requested = True

signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)


# ── Helpers ──────────────────────────────────────────────────────
def ts():
    return datetime.now().strftime("%H:%M:%S")

def banner(msg):
    print(f"\n{'='*60}")
    print(f"  [{ts()}] {msg}")
    print(f"{'='*60}", flush=True)

def info(msg):
    print(f"  [{ts()}] {msg}", flush=True)


async def find_or_create_job(session: AsyncSession, state: CrawlStateManager) -> int:
    """Find the latest active job or create a new one."""
    from shared.models.crawl_job import CrawlJob
    result = await session.execute(
        select(CrawlJob)
        .where(CrawlJob.status.in_(["running", "pending"]))
        .order_by(CrawlJob.id.desc())
        .limit(1)
    )
    job = result.scalar_one_or_none()

    if job:
        info(f"Found existing job #{job.id} (status={job.status})")
        return job.id

    # Check if there are any pending items without an active job
    from shared.models.crawl_queue import CrawlQueue
    result = await session.execute(
        select(func.count(CrawlQueue.id)).where(CrawlQueue.status == "pending")
    )
    pending = result.scalar()

    if pending and pending > 0:
        # Find the job these items belong to
        result = await session.execute(
            select(CrawlJob).order_by(CrawlJob.id.desc()).limit(1)
        )
        job = result.scalar_one_or_none()
        if job:
            if job.status != "running":
                job.status = "running"
                await session.commit()
            info(f"Resumed job #{job.id} ({pending} pending items)")
            return job.id

    # Create fresh job
    job = await state.create_job(brand_id=None, level=1)
    await session.commit()
    info(f"Created new job #{job.id}")

    # Seed
    await state.enqueue_urls(job.id, [{"url": "https://www.catcar.info/"}], level=1)
    await session.commit()
    info("Seeded homepage URL")
    return job.id


async def run_crawl(max_level: int = 6, job_id: int | None = None):
    """Main crawl loop with auto-resume."""
    global shutdown_requested
    db_engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_size=5,
        max_overflow=5,
    )
    SessionFactory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    banner(f"RESILIENT CRAWL — max_level={max_level}")
    info(f"Database: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else '...'}")

    import os
    min_delay = float(os.environ.get("CRAWL_MIN_DELAY", "1.0"))
    max_delay = float(os.environ.get("CRAWL_MAX_DELAY", "2.0"))
    info(f"Rate limiter: {min_delay}-{max_delay}s delay")

    async with BrowserPool(pool_size=1, headless=True) as browser:
        rate_config = RateLimitConfig(
            min_delay=min_delay,
            max_delay=max_delay,
            max_concurrent=1,
        )
        limiter = RateLimiter(rate_config)

        async with SessionFactory() as session:
            state = CrawlStateManager(session)

            # Find or create job
            if job_id:
                current_job_id = job_id
                info(f"Using specified job #{current_job_id}")
            else:
                current_job_id = await find_or_create_job(session, state)

            # Always reset stale items on start (we might be recovering from crash)
            reset_count = await state.reset_stale(timeout_minutes=5)
            if reset_count:
                info(f"Reset {reset_count} stale items to pending")
            await session.commit()

            # Ensure job is running
            await state.start_job(current_job_id)
            await session.commit()

            engine = CrawlEngine(browser, limiter, state)

            # Process loop
            processed = 0
            failed = 0
            start_time = time.time()
            last_report_time = start_time

            while not shutdown_requested:
                item = await state.claim_next(current_job_id)

                if item is None:
                    from shared.models.crawl_queue import CrawlQueue as CQ
                    # Check if truly done
                    result = await session.execute(
                        select(func.count(CQ.id)).where(
                            CQ.job_id == current_job_id,
                            CQ.status.in_(["pending", "processing"])
                        )
                    )
                    remaining = result.scalar()
                    if remaining == 0:
                        break
                    await asyncio.sleep(2)
                    continue

                # Stop at max level
                if item.level > max_level:
                    from sqlalchemy import update as sa_update
                    from shared.models.crawl_queue import CrawlQueue as CQ
                    await session.execute(
                        sa_update(CQ).where(CQ.id == item.id).values(status="pending")
                    )
                    await session.commit()
                    info(f"Reached level {item.level} — stopping (max={max_level})")
                    break

                # Process
                level_names = {
                    1: "Brands", 2: "Models", 3: "Years",
                    4: "Categories", 5: "Subgroups", 6: "Parts",
                }
                level_name = level_names.get(item.level, f"L{item.level}")
                short_url = item.url[:70] + "..." if len(item.url) > 70 else item.url

                ok = await engine.process_url(item)
                processed += 1
                if not ok:
                    failed += 1

                elapsed = time.time() - start_time
                rate = processed / elapsed * 60 if elapsed > 0 else 0
                icon = "✓" if ok else "✗"
                print(f"  [{ts()}] {icon} L{item.level} #{processed} ({rate:.1f}/min) {short_url}", flush=True)

                # Progress report every 60 seconds
                now = time.time()
                if now - last_report_time > 60:
                    last_report_time = now
                    from shared.models.crawl_queue import CrawlQueue as CQ
                    result = await session.execute(
                        select(
                            CQ.level,
                            CQ.status,
                            func.count(CQ.id),
                        )
                        .where(CQ.job_id == current_job_id)
                        .group_by(CQ.level, CQ.status)
                    )
                    banner(f"PROGRESS — {processed} processed, {failed} failed, {rate:.1f}/min")
                    for level, status, count in result.all():
                        name = level_names.get(level, f"L{level}")
                        print(f"    {name:<12} {status:<12} {count:>8}", flush=True)

                    # Check disk space
                    try:
                        import shutil
                        total, used, free = shutil.disk_usage("/")
                        free_gb = free / (1024**3)
                        if free_gb < 10:
                            banner(f"DISK CRITICAL: {free_gb:.1f} GB free — STOPPING CRAWL")
                            info("Crawl paused to prevent disk full. Free space and restart.")
                            shutdown_requested = True
                        elif free_gb < 15:
                            info(f"⚠ LOW DISK: {free_gb:.1f} GB free — consider freeing space")
                    except:
                        pass

            # Completion
            if not shutdown_requested:
                await state.complete_job(current_job_id)
                await session.commit()
                banner("CRAWL COMPLETE")
            else:
                banner("CRAWL PAUSED (signal received)")

            elapsed = time.time() - start_time
            info(f"Processed {processed} URLs in {elapsed/60:.1f} min ({processed/max(elapsed,1)*60:.1f}/min)")
            if processed > 0:
                info(f"Success rate: {(processed-failed)/processed*100:.1f}%")

    await db_engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Resilient crawl runner")
    parser.add_argument("--level", type=int, default=6, help="Max level (1-6, default: 6)")
    parser.add_argument("--job", type=int, default=None, help="Specific job ID to resume")
    args = parser.parse_args()

    try:
        asyncio.run(run_crawl(max_level=args.level, job_id=args.job))
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(0)
    except Exception as e:
        print(f"\n  CRASH: {e}", flush=True)
        sys.exit(1)  # Exit 1 → Docker restarts the container


if __name__ == "__main__":
    main()
