"""Monitored crawl execution script.

Run from project root:
    python run_crawl.py [--level N] [--brand SLUG] [--resume JOB_ID]

Connects directly to PostgreSQL and runs Playwright locally.
Prints progress in real-time so you can monitor data quality.
"""
import asyncio
import argparse
import sys
import time
from datetime import datetime

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from crawler.browser import BrowserPool
from crawler.rate_limiter import RateLimiter, RateLimitConfig
from crawler.state import CrawlStateManager
from crawler.engine import CrawlEngine
from shared.config import settings


# ── Pretty printing helpers ──────────────────────────────────────────

def ts():
    return datetime.now().strftime("%H:%M:%S")


def banner(msg):
    print(f"\n{'='*60}")
    print(f"  [{ts()}] {msg}")
    print(f"{'='*60}")


def info(msg):
    print(f"  [{ts()}] {msg}")


def warn(msg):
    print(f"  [{ts()}] ⚠ {msg}")


def error(msg):
    print(f"  [{ts()}] ✗ {msg}")


def success(msg):
    print(f"  [{ts()}] ✓ {msg}")


# ── Database stats ───────────────────────────────────────────────────

async def get_table_counts(session: AsyncSession) -> dict:
    """Get row counts for all data tables."""
    tables = ["brands", "markets", "models", "model_years",
              "parts_categories", "subgroups", "parts"]
    counts = {}
    for table in tables:
        result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
        counts[table] = result.scalar()
    return counts


async def get_queue_stats(session: AsyncSession, job_id: int) -> dict:
    """Get queue breakdown by level and status."""
    from shared.models.crawl_queue import CrawlQueue
    result = await session.execute(
        select(
            CrawlQueue.level,
            CrawlQueue.status,
            func.count(CrawlQueue.id),
        )
        .where(CrawlQueue.job_id == job_id)
        .group_by(CrawlQueue.level, CrawlQueue.status)
    )
    stats = {}
    for level, status, count in result.all():
        if level not in stats:
            stats[level] = {}
        stats[level][status] = count
    return stats


async def get_recent_errors(session: AsyncSession, job_id: int, limit: int = 5) -> list:
    """Get recent failed queue items."""
    from shared.models.crawl_queue import CrawlQueue
    result = await session.execute(
        select(CrawlQueue.url, CrawlQueue.error_message, CrawlQueue.level)
        .where(CrawlQueue.job_id == job_id, CrawlQueue.status == "failed")
        .order_by(CrawlQueue.processed_at.desc())
        .limit(limit)
    )
    return result.all()


def print_progress(queue_stats: dict, table_counts: dict):
    """Print a nice progress report."""
    level_names = {
        1: "Brands", 2: "Models", 3: "Years",
        4: "Categories", 5: "Subgroups", 6: "Parts",
    }
    print()
    print(f"  {'Level':<12} {'Pending':>8} {'Processing':>11} {'Done':>8} {'Failed':>8}")
    print(f"  {'-'*12} {'-'*8} {'-'*11} {'-'*8} {'-'*8}")
    for level in sorted(queue_stats.keys()):
        s = queue_stats[level]
        name = level_names.get(level, f"L{level}")
        print(f"  {name:<12} {s.get('pending',0):>8} {s.get('processing',0):>11} "
              f"{s.get('done',0):>8} {s.get('failed',0):>8}")

    print()
    print(f"  Database:")
    for table, count in table_counts.items():
        if count > 0:
            print(f"    {table:<20} {count:>8} rows")


def print_errors(errors: list):
    if not errors:
        return
    print()
    warn(f"Recent errors ({len(errors)}):")
    for url, err, level in errors:
        short_url = url[:60] + "..." if len(url) > 60 else url
        short_err = err[:80] if err else "?"
        print(f"    L{level} {short_url}")
        print(f"         {short_err}")


# ── Main crawl loop ─────────────────────────────────────────────────

async def run_crawl(
    max_level: int = 6,
    brand_slug: str | None = None,
    resume_job_id: int | None = None,
):
    """Run the crawl with real-time monitoring."""
    db_engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_size=5,
        max_overflow=5,
    )
    SessionFactory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    banner(f"CRAWL START — max_level={max_level}, brand={brand_slug or 'ALL'}")
    info(f"Database: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else settings.DATABASE_URL}")

    async with BrowserPool(pool_size=1, headless=True) as browser:
        rate_config = RateLimitConfig(
            min_delay=2.0,
            max_delay=5.0,
            max_concurrent=1,
        )
        limiter = RateLimiter(rate_config)

        async with SessionFactory() as session:
            state = CrawlStateManager(session)
            engine = CrawlEngine(browser, limiter, state)

            # Create or resume job
            if resume_job_id:
                job_id = resume_job_id
                info(f"Resuming job #{job_id}")
                # Reset any stale processing items
                await state.reset_stale(timeout_minutes=5)
                await session.commit()
            else:
                job = await state.create_job(brand_id=None, level=1)
                job_id = job.id
                await session.commit()
                info(f"Created job #{job_id}")

                # Seed level 1
                seed_url = "https://www.catcar.info/"
                await state.enqueue_urls(job_id, [{"url": seed_url}], level=1)
                await session.commit()
                info(f"Seeded: {seed_url}")

            # Process loop
            await state.start_job(job_id)
            await session.commit()

            processed = 0
            start_time = time.time()
            last_report_time = start_time

            while True:
                item = await state.claim_next(job_id)

                if item is None:
                    progress = await state.get_progress(job_id)
                    if progress["processing"] == 0 and progress["pending"] == 0:
                        break
                    await asyncio.sleep(2)
                    continue

                # Stop when we reach levels beyond max_level
                if item.level > max_level:
                    # Put the item back to pending (unclaim it)
                    from sqlalchemy import update as sa_update
                    from shared.models.crawl_queue import CrawlQueue as CQ
                    await session.execute(
                        sa_update(CQ).where(CQ.id == item.id).values(status="pending")
                    )
                    await session.commit()
                    info(f"Reached level {item.level} — stopping (max_level={max_level})")
                    break

                # Process the URL
                level_names = {
                    1: "Homepage", 2: "Models", 3: "Years",
                    4: "Categories", 5: "Subgroups", 6: "Parts",
                }
                level_name = level_names.get(item.level, f"L{item.level}")
                short_url = item.url[:70] + "..." if len(item.url) > 70 else item.url
                info(f"[L{item.level} {level_name}] {short_url}")

                ok = await engine.process_url(item)
                processed += 1

                status_icon = "✓" if ok else "✗"
                elapsed = time.time() - start_time
                rate = processed / elapsed * 60 if elapsed > 0 else 0
                print(f"    {status_icon} #{processed} ({rate:.1f}/min)")

                # Periodic progress report every 30 seconds
                now = time.time()
                if now - last_report_time > 30:
                    last_report_time = now
                    queue_stats = await get_queue_stats(session, job_id)
                    table_counts = await get_table_counts(session)
                    banner(f"PROGRESS REPORT — {processed} URLs processed")
                    print_progress(queue_stats, table_counts)
                    errors = await get_recent_errors(session, job_id)
                    print_errors(errors)

            # Final report
            await state.complete_job(job_id)
            await session.commit()

            elapsed = time.time() - start_time
            queue_stats = await get_queue_stats(session, job_id)
            table_counts = await get_table_counts(session)

            banner("CRAWL COMPLETE")
            info(f"Job #{job_id} finished in {elapsed/60:.1f} minutes")
            info(f"Processed {processed} URLs ({processed/elapsed*60:.1f}/min)")
            print_progress(queue_stats, table_counts)

            errors = await get_recent_errors(session, job_id, limit=10)
            print_errors(errors)

            # Data quality summary
            print()
            total_failed = sum(
                s.get("failed", 0) for s in queue_stats.values()
            )
            total_done = sum(
                s.get("done", 0) for s in queue_stats.values()
            )
            if total_done + total_failed > 0:
                success_rate = total_done / (total_done + total_failed) * 100
                info(f"Success rate: {success_rate:.1f}%")

    await db_engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Run monitored crawl")
    parser.add_argument(
        "--level", type=int, default=2,
        help="Maximum level to crawl (1-6, default: 2 for brands+models)"
    )
    parser.add_argument(
        "--brand", type=str, default=None,
        help="Crawl only this brand slug (not yet implemented)"
    )
    parser.add_argument(
        "--resume", type=int, default=None,
        help="Resume an existing job by ID"
    )
    args = parser.parse_args()

    if args.level < 1 or args.level > 6:
        print("Error: --level must be between 1 and 6")
        sys.exit(1)

    asyncio.run(run_crawl(
        max_level=args.level,
        brand_slug=args.brand,
        resume_job_id=args.resume,
    ))


if __name__ == "__main__":
    main()
