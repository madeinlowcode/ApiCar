"""Lightweight HTTP-only crawler for L6 parts pages.

No Playwright/Chromium — uses httpx + raw SQL (no ORM).
Designed to run many parallel instances (~50 MB each vs ~800 MB with Playwright).

Usage:
    python run_crawl_http.py [--job JOB_ID]
"""
import asyncio
import argparse
import hashlib
import os
import random
import signal
import sys
import time
from datetime import datetime

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from crawler.parsers.parts_html import parse_parts_html
from crawler.validators.part import ParsedPart
from shared.config import settings

# ── Graceful shutdown ────────────────────────────────────────────
shutdown_requested = False

def handle_signal(signum, frame):
    global shutdown_requested
    print(f"\n  [{ts()}] Signal {signum}, finishing current URL...")
    shutdown_requested = True

signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)


def ts():
    return datetime.now().strftime("%H:%M:%S")

def banner(msg):
    print(f"\n{'='*60}\n  [{ts()}] {msg}\n{'='*60}", flush=True)

def info(msg):
    print(f"  [{ts()}] {msg}", flush=True)

def generate_content_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


async def run_crawl(job_id: int | None = None):
    """Main crawl loop — HTTP only, L6 only, raw SQL only."""
    global shutdown_requested

    pool_size = int(os.environ.get("DB_POOL_SIZE", "3"))
    max_overflow = int(os.environ.get("DB_MAX_OVERFLOW", "2"))
    min_delay = float(os.environ.get("CRAWL_MIN_DELAY", "0.3"))
    max_delay = float(os.environ.get("CRAWL_MAX_DELAY", "0.8"))

    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_size=pool_size,
        max_overflow=max_overflow,
    )

    banner("HTTP CRAWLER — L6 Parts only")
    info(f"Database: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else '...'}")
    info(f"Rate limiter: {min_delay}-{max_delay}s delay")

    # Find job
    async with engine.connect() as conn:
        if job_id:
            current_job_id = job_id
        else:
            result = await conn.execute(text(
                "SELECT id FROM crawl_jobs WHERE status IN ('running', 'pending') ORDER BY id DESC LIMIT 1"
            ))
            row = result.first()
            if not row:
                result = await conn.execute(text("SELECT id FROM crawl_jobs ORDER BY id DESC LIMIT 1"))
                row = result.first()
            if not row:
                raise RuntimeError("No crawl job found")
            current_job_id = row[0]
        info(f"Using job #{current_job_id}")

    # Process loop
    processed = 0
    failed = 0
    start_time = time.time()
    last_report_time = start_time
    empty_count = 0

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        http2=False,
    ) as client:
        while not shutdown_requested:
            # Claim next L6 URL (raw SQL with FOR UPDATE SKIP LOCKED)
            item = None
            async with engine.begin() as conn:
                result = await conn.execute(text("""
                    SELECT id, url, parent_subgroup_id
                    FROM crawl_queue
                    WHERE job_id = :job_id AND status = 'pending' AND level = 6
                    ORDER BY id
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                """), {"job_id": current_job_id})
                row = result.first()
                if row:
                    item = {"id": row[0], "url": row[1], "parent_subgroup_id": row[2]}
                    await conn.execute(text(
                        "UPDATE crawl_queue SET status = 'processing', processed_at = now() WHERE id = :id"
                    ), {"id": item["id"]})

            if item is None:
                empty_count += 1
                if empty_count >= 5:
                    async with engine.connect() as conn:
                        result = await conn.execute(text("""
                            SELECT COUNT(*) FROM crawl_queue
                            WHERE job_id = :job_id AND level = 6 AND status IN ('pending', 'processing')
                        """), {"job_id": current_job_id})
                        remaining = result.scalar()
                        if remaining == 0:
                            break
                        info(f"Waiting for L6 items... ({remaining} remaining)")
                await asyncio.sleep(2)
                continue

            empty_count = 0

            # Process the URL
            ok = await process_item(client, engine, item, min_delay, max_delay)
            processed += 1
            if not ok:
                failed += 1

            elapsed = time.time() - start_time
            rate = processed / elapsed * 60 if elapsed > 0 else 0
            icon = "✓" if ok else "✗"
            short_url = item["url"][:70] + "..." if len(item["url"]) > 70 else item["url"]
            print(f"  [{ts()}] {icon} L6 #{processed} ({rate:.1f}/min) {short_url}", flush=True)

            # Progress report every 120 seconds
            now = time.time()
            if now - last_report_time > 120:
                last_report_time = now
                async with engine.connect() as conn:
                    result = await conn.execute(text("""
                        SELECT status, COUNT(*) FROM crawl_queue
                        WHERE job_id = :job_id AND level = 6
                        GROUP BY status
                    """), {"job_id": current_job_id})
                    banner(f"PROGRESS — {processed} processed, {failed} failed, {rate:.1f}/min")
                    for status, count in result.all():
                        print(f"    L6 {status:<12} {count:>10}", flush=True)

    banner("HTTP CRAWLER STOPPED" if shutdown_requested else "L6 COMPLETE")
    elapsed = time.time() - start_time
    info(f"Processed {processed} URLs in {elapsed/60:.1f} min ({processed/max(elapsed,1)*60:.1f}/min)")
    await engine.dispose()


async def process_item(
    client: httpx.AsyncClient,
    engine,
    item: dict,
    min_delay: float,
    max_delay: float,
) -> bool:
    """Fetch a single L6 URL via HTTP and save parsed parts."""
    try:
        # Rate limit
        delay = random.uniform(min_delay, max_delay)
        await asyncio.sleep(delay)

        # Fetch
        resp = await client.get(item["url"], timeout=30.0)
        resp.raise_for_status()
        html = resp.text

        # Parse
        raw_items = parse_parts_html(html)

        # Validate
        validated = []
        for raw in raw_items:
            try:
                parsed = ParsedPart(**raw)
                d = parsed.model_dump()
                d["content_hash"] = generate_content_hash(
                    f"{d['part_no']}|{d.get('position','')}|{d['description']}"
                )
                validated.append(d)
            except Exception:
                continue

        # Save parts + mark done in single transaction
        subgroup_id = item["parent_subgroup_id"]
        async with engine.begin() as conn:
            if validated and subgroup_id:
                for v in validated:
                    position = str(v.get("position", "")) or None
                    qty = v.get("quantity")
                    await conn.execute(text("""
                        INSERT INTO parts (subgroup_id, position, part_number, description, remark, quantity, model_data, content_hash)
                        VALUES (:subgroup_id, :position, :part_number, :description, :remark, :quantity, :model_data, :content_hash)
                        ON CONFLICT (subgroup_id, part_number, COALESCE(position, ''))
                        DO UPDATE SET
                            description = EXCLUDED.description,
                            remark = EXCLUDED.remark,
                            quantity = EXCLUDED.quantity,
                            model_data = EXCLUDED.model_data,
                            content_hash = EXCLUDED.content_hash,
                            updated_at = now()
                        WHERE parts.content_hash IS DISTINCT FROM EXCLUDED.content_hash
                    """), {
                        "subgroup_id": subgroup_id,
                        "position": position,
                        "part_number": str(v.get("part_no", "")),
                        "description": v["description"],
                        "remark": v.get("remark"),
                        "quantity": str(qty) if qty is not None else None,
                        "model_data": v.get("model_data"),
                        "content_hash": v.get("content_hash"),
                    })
            await conn.execute(text(
                "UPDATE crawl_queue SET status = 'done' WHERE id = :id"
            ), {"id": item["id"]})
        return True

    except Exception as e:
        # Mark failed
        try:
            async with engine.begin() as conn:
                await conn.execute(text("""
                    UPDATE crawl_queue SET
                        retries = retries + 1,
                        status = CASE WHEN retries + 1 >= max_retries THEN 'failed' ELSE 'pending' END,
                        error_message = :error
                    WHERE id = :id
                """), {"id": item["id"], "error": str(e)[:500]})
        except Exception:
            pass
        return False


def main():
    parser = argparse.ArgumentParser(description="HTTP-only L6 parts crawler")
    parser.add_argument("--job", type=int, default=None, help="Specific job ID")
    args = parser.parse_args()

    try:
        asyncio.run(run_crawl(job_id=args.job))
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(0)
    except Exception as e:
        print(f"\n  CRASH: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
