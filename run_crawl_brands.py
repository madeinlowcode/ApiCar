"""Recursive HTTP crawler for brand navigation pages on catcar.info.

Seeds brand homepage URLs, follows navigation links recursively using
detect_and_parse, and saves parts when reaching parts pages.

No Playwright/Chromium -- uses httpx + raw SQL (no ORM).

Usage:
    python run_crawl_brands.py --seed          # Seed brand URLs into crawl_queue
    python run_crawl_brands.py                 # Run the crawler
    python run_crawl_brands.py --job 42        # Use a specific job ID
    python run_crawl_brands.py --seed --job 42 # Seed into a specific job
"""
import asyncio
import argparse
import base64
import hashlib
import json
import os
import random
import re
import signal
import sys
import time
from datetime import datetime
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from crawler.parsers.brand_navigation import detect_and_parse
from crawler.parsers.parts_html import parse_parts_html
from crawler.validators.part import ParsedPart
from shared.config import settings

# ── Brand seed URLs ─────────────────────────────────────────────
BRAND_URLS = {
    "honda": "https://www.catcar.info/honda/?lang=en",
    "kia": "http://www.catcar.info/kia/?lang=en",
    "hyundai": "https://www.catcar.info/hyundai/?lang=en",
    "nissan": "https://www.catcar.info/nissan/?lang=en",
    "mazda": "https://www.catcar.info/mazda/?lang=en",
    "subaru": "https://www.catcar.info/subaru/?lang=en",
    "chrysler": "http://www.catcar.info/chrysler/?lang=en",
}

CRAWL_LEVEL = 7  # All brand-crawl URLs use level 7

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


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


# ── URL helpers ──────────────────────────────────────────────────

def ensure_lang_en(url: str) -> str:
    """Make sure the URL has lang=en query parameter."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    if "lang" not in params:
        separator = "&" if parsed.query else ""
        new_query = parsed.query + separator + "lang=en"
        return urlunparse(parsed._replace(query=new_query))
    return url


def decode_l_param(url: str) -> dict:
    """Decode the base64-encoded 'l' query parameter from a catcar URL.

    Returns a dict like {"10": "Market", "20": "Europe", "30": "MODEL NAME", ...}
    or empty dict on failure.
    """
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        l_value = params.get("l", [""])[0]
        if not l_value:
            return {}
        # Add padding if needed
        padding = 4 - len(l_value) % 4
        if padding != 4:
            l_value += "=" * padding
        decoded = base64.b64decode(l_value).decode("utf-8", errors="replace")
        # Try JSON first
        try:
            return json.loads(decoded)
        except (json.JSONDecodeError, ValueError):
            pass
        # Try key==value||key==value format
        result = {}
        for pair in decoded.split("||"):
            if "==" in pair:
                key, val = pair.split("==", 1)
                result[key] = val
        return result
    except Exception:
        return {}


def extract_brand_slug(url: str) -> str:
    """Extract brand slug from catcar URL path, e.g. 'honda' from /honda/..."""
    parsed = urlparse(url)
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if parts:
        return parts[0].lower()
    return ""


def extract_metadata_from_url(url: str) -> dict:
    """Extract model/category/subgroup context from the URL's l= parameter.

    Heuristic mapping of decoded l= keys:
      - Keys with values like region names -> market
      - Keys with model-like names (contains year or slash) -> model
      - Keys with category-like names (ENGINE, BODY, etc.) -> category
      - The last meaningful value -> subgroup description

    Returns dict with keys: market_name, model_name, category_name, subgroup_desc
    """
    decoded = decode_l_param(url)
    if not decoded:
        return {}

    values = list(decoded.values()) if isinstance(decoded, dict) else []
    result = {}

    # For JSON-style metadata like {"10":"Market","20":"Europe","30":"MODEL","40":"ENGINE"}
    # Values are ordered by their numeric keys
    if decoded and all(k.isdigit() for k in decoded.keys()):
        sorted_vals = [decoded[k] for k in sorted(decoded.keys(), key=int)]
        # Typical structure: [type_hint, region, model, category, ...]
        # But varies by brand. Use positional heuristics.
        for i, val in enumerate(sorted_vals):
            if not val:
                continue
            val_lower = val.lower()
            # Skip type hints like "Market", "Region"
            if val_lower in ("market", "region", "type"):
                continue
            if not result.get("market_name"):
                result["market_name"] = val
            elif not result.get("model_name"):
                result["model_name"] = val
            elif not result.get("category_name"):
                result["category_name"] = val
            elif not result.get("subgroup_desc"):
                result["subgroup_desc"] = val
    else:
        # key==value format
        for key, val in decoded.items():
            key_lower = key.lower()
            if "market" in key_lower or "region" in key_lower:
                result["market_name"] = val
            elif "mod" in key_lower or "model" in key_lower:
                result["model_name"] = val
            elif "group" in key_lower or "cat" in key_lower:
                result["category_name"] = val
            elif "dir" in key_lower or "sub" in key_lower or "st" in key_lower:
                if not result.get("subgroup_desc"):
                    result["subgroup_desc"] = val

    return result


# ── Seed mode ────────────────────────────────────────────────────

async def seed_brands(engine, job_id: int | None = None):
    """Create a crawl job and seed brand homepage URLs into crawl_queue."""

    async with engine.begin() as conn:
        if job_id:
            current_job_id = job_id
            info(f"Using existing job #{current_job_id}")
        else:
            # Create a new crawl job for brands (level=7)
            result = await conn.execute(text("""
                INSERT INTO crawl_jobs (level, status, progress, started_at)
                VALUES (:level, 'running', '{}', now())
                RETURNING id
            """), {"level": CRAWL_LEVEL})
            current_job_id = result.scalar_one()
            info(f"Created crawl job #{current_job_id}")

        # Insert brand URLs, skip if already exist
        seeded = 0
        for slug, url in BRAND_URLS.items():
            url = ensure_lang_en(url)
            # Check for existing URL in this job
            exists = await conn.execute(text("""
                SELECT 1 FROM crawl_queue
                WHERE job_id = :job_id AND url = :url
                LIMIT 1
            """), {"job_id": current_job_id, "url": url})
            if exists.first():
                info(f"  Skip {slug} (already seeded)")
                continue

            # Look up brand_id from brands table
            brand_result = await conn.execute(text("""
                SELECT id FROM brands WHERE slug = :slug LIMIT 1
            """), {"slug": slug})
            brand_row = brand_result.first()
            brand_id = brand_row[0] if brand_row else None

            await conn.execute(text("""
                INSERT INTO crawl_queue (job_id, url, level, status, retries, max_retries, parent_brand_id)
                VALUES (:job_id, :url, :level, 'pending', 0, 3, :brand_id)
            """), {
                "job_id": current_job_id,
                "url": url,
                "level": CRAWL_LEVEL,
                "brand_id": brand_id,
            })
            seeded += 1
            info(f"  Seeded {slug}: {url}")

    banner(f"SEEDED {seeded} brand URLs into job #{current_job_id}")
    return current_job_id


# ── DB entity resolution ─────────────────────────────────────────

async def find_or_create_brand(conn, slug: str, url: str) -> int | None:
    """Find brand by slug, return id or None."""
    result = await conn.execute(text(
        "SELECT id FROM brands WHERE slug = :slug LIMIT 1"
    ), {"slug": slug})
    row = result.first()
    return row[0] if row else None


async def find_or_create_market(conn, brand_id: int, market_name: str, url: str) -> int:
    """Find or create a market for the brand."""
    result = await conn.execute(text("""
        SELECT id FROM markets
        WHERE brand_id = :brand_id AND name = :name
        LIMIT 1
    """), {"brand_id": brand_id, "name": market_name})
    row = result.first()
    if row:
        return row[0]

    result = await conn.execute(text("""
        INSERT INTO markets (brand_id, name, catalog_url)
        VALUES (:brand_id, :name, :url)
        ON CONFLICT (brand_id, name) DO UPDATE SET catalog_url = EXCLUDED.catalog_url
        RETURNING id
    """), {"brand_id": brand_id, "name": market_name, "url": url})
    return result.scalar_one()


async def find_or_create_model(
    conn, brand_id: int, market_id: int, model_name: str, url: str
) -> int:
    """Find or create a model."""
    # Use model_name as catalog_code for brand-crawled models
    catalog_code = model_name[:50]
    result = await conn.execute(text("""
        SELECT id FROM models
        WHERE brand_id = :brand_id AND market_id = :market_id AND catalog_code = :code
        LIMIT 1
    """), {"brand_id": brand_id, "market_id": market_id, "code": catalog_code})
    row = result.first()
    if row:
        return row[0]

    result = await conn.execute(text("""
        INSERT INTO models (brand_id, market_id, catalog_code, name, catalog_url)
        VALUES (:brand_id, :market_id, :code, :name, :url)
        ON CONFLICT (brand_id, market_id, catalog_code)
        DO UPDATE SET catalog_url = EXCLUDED.catalog_url
        RETURNING id
    """), {
        "brand_id": brand_id,
        "market_id": market_id,
        "code": catalog_code,
        "name": model_name[:200],
        "url": url,
    })
    return result.scalar_one()


async def find_or_create_model_year(conn, model_id: int, url: str) -> int:
    """Find or create a model_year. Uses year=0 as placeholder for brand-crawled data."""
    result = await conn.execute(text("""
        SELECT id FROM model_years
        WHERE model_id = :model_id AND year = 0 AND restriction IS NULL
        LIMIT 1
    """), {"model_id": model_id})
    row = result.first()
    if row:
        return row[0]

    result = await conn.execute(text("""
        INSERT INTO model_years (model_id, year, catalog_url)
        VALUES (:model_id, 0, :url)
        RETURNING id
    """), {"model_id": model_id, "url": url})
    return result.scalar_one()


async def find_or_create_category(
    conn, model_year_id: int, category_name: str, url: str
) -> int:
    """Find or create a parts_category."""
    result = await conn.execute(text("""
        SELECT id FROM parts_categories
        WHERE model_year_id = :my_id AND name = :name
        LIMIT 1
    """), {"my_id": model_year_id, "name": category_name[:300]})
    row = result.first()
    if row:
        return row[0]

    # Get next category_index
    idx_result = await conn.execute(text("""
        SELECT COALESCE(MAX(category_index), 0) + 1
        FROM parts_categories
        WHERE model_year_id = :my_id
    """), {"my_id": model_year_id})
    next_idx = idx_result.scalar()

    result = await conn.execute(text("""
        INSERT INTO parts_categories (model_year_id, category_index, name, catalog_url)
        VALUES (:my_id, :idx, :name, :url)
        ON CONFLICT (model_year_id, category_index)
        DO UPDATE SET name = EXCLUDED.name, catalog_url = EXCLUDED.catalog_url
        RETURNING id
    """), {
        "my_id": model_year_id,
        "idx": next_idx,
        "name": category_name[:300],
        "url": url,
    })
    return result.scalar_one()


async def find_or_create_subgroup(
    conn, category_id: int, subgroup_desc: str, url: str
) -> int:
    """Find or create a subgroup."""
    # Use a hash of the URL as illustration_number to ensure uniqueness
    url_hash = hashlib.md5(url.encode()).hexdigest()[:16]
    illustration = f"brand-{url_hash}"

    result = await conn.execute(text("""
        SELECT id FROM subgroups
        WHERE category_id = :cat_id AND illustration_number = :illust
        LIMIT 1
    """), {"cat_id": category_id, "illust": illustration})
    row = result.first()
    if row:
        return row[0]

    result = await conn.execute(text("""
        INSERT INTO subgroups (category_id, main_group, illustration_number, description, catalog_url)
        VALUES (:cat_id, 'BRAND', :illust, :desc, :url)
        ON CONFLICT (category_id, illustration_number)
        DO UPDATE SET description = EXCLUDED.description, catalog_url = EXCLUDED.catalog_url
        RETURNING id
    """), {
        "cat_id": category_id,
        "illust": illustration,
        "desc": subgroup_desc[:600],
        "url": url,
    })
    return result.scalar_one()


async def resolve_subgroup_id(conn, url: str) -> int | None:
    """Resolve or create the full entity chain (brand > market > model > year > category > subgroup)
    from URL metadata. Returns subgroup_id or None if insufficient metadata.
    """
    brand_slug = extract_brand_slug(url)
    if not brand_slug:
        return None

    brand_id = await find_or_create_brand(conn, brand_slug, url)
    if not brand_id:
        return None

    meta = extract_metadata_from_url(url)
    market_name = meta.get("market_name", "Unknown")
    model_name = meta.get("model_name", "Unknown")
    category_name = meta.get("category_name", "Unknown")
    subgroup_desc = meta.get("subgroup_desc", category_name)

    market_id = await find_or_create_market(conn, brand_id, market_name, url)
    model_id = await find_or_create_model(conn, brand_id, market_id, model_name, url)
    model_year_id = await find_or_create_model_year(conn, model_id, url)
    category_id = await find_or_create_category(conn, model_year_id, category_name, url)
    subgroup_id = await find_or_create_subgroup(conn, category_id, subgroup_desc, url)

    return subgroup_id


# ── URL enqueueing ───────────────────────────────────────────────

async def enqueue_urls(conn, job_id: int, urls: list[str], parent_brand_id: int | None = None):
    """Insert new URLs into crawl_queue, skipping duplicates within the job."""
    if not urls:
        return 0

    enqueued = 0
    for url in urls:
        url = ensure_lang_en(url)
        # Check for existing URL in this job
        exists = await conn.execute(text("""
            SELECT 1 FROM crawl_queue
            WHERE job_id = :job_id AND url = :url
            LIMIT 1
        """), {"job_id": job_id, "url": url})
        if exists.first():
            continue

        await conn.execute(text("""
            INSERT INTO crawl_queue (job_id, url, level, status, retries, max_retries, parent_brand_id)
            VALUES (:job_id, :url, :level, 'pending', 0, 3, :brand_id)
        """), {
            "job_id": job_id,
            "url": url,
            "level": CRAWL_LEVEL,
            "brand_id": parent_brand_id,
        })
        enqueued += 1

    return enqueued


# ── Item processing ──────────────────────────────────────────────

async def process_item(
    client: httpx.AsyncClient,
    engine,
    item: dict,
    job_id: int,
    min_delay: float,
    max_delay: float,
) -> tuple[bool, str]:
    """Fetch a URL, detect page type, enqueue children or save parts.

    Returns (success: bool, page_type: str).
    """
    try:
        # Rate limit
        delay = random.uniform(min_delay, max_delay)
        await asyncio.sleep(delay)

        # Fetch
        resp = await client.get(item["url"], timeout=30.0)
        resp.raise_for_status()
        html = resp.text

        # Detect page type
        result = detect_and_parse(html)
        page_type = result["type"]
        items = result["items"]

        if page_type == "empty":
            # No links and no parts -- mark done
            async with engine.begin() as conn:
                await conn.execute(text(
                    "UPDATE crawl_queue SET status = 'done' WHERE id = :id"
                ), {"id": item["id"]})
            return True, "empty"

        if page_type == "parts":
            # Save parts
            await save_parts(engine, item, html, items)
            return True, "parts"

        # Navigation page -- enqueue child URLs
        child_urls = [it["url"] for it in items if it.get("url")]
        brand_id = item.get("parent_brand_id")

        async with engine.begin() as conn:
            enqueued = await enqueue_urls(conn, job_id, child_urls, parent_brand_id=brand_id)
            await conn.execute(text(
                "UPDATE crawl_queue SET status = 'done' WHERE id = :id"
            ), {"id": item["id"]})

        return True, f"{page_type}(+{enqueued})"

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
        return False, f"error: {str(e)[:80]}"


async def save_parts(engine, item: dict, html: str, raw_items: list[dict]):
    """Validate and save parts to DB, creating the entity chain as needed."""
    # Validate
    validated = []
    for raw in raw_items:
        try:
            parsed = ParsedPart(**raw)
            d = parsed.model_dump()
            d["content_hash"] = generate_content_hash(
                f"{d['part_no']}|{d.get('position', '')}|{d['description']}"
            )
            validated.append(d)
        except Exception:
            continue

    async with engine.begin() as conn:
        subgroup_id = None
        if validated:
            subgroup_id = await resolve_subgroup_id(conn, item["url"])

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


# ── Main crawl loop ──────────────────────────────────────────────

async def run_crawl(job_id: int | None = None, seed: bool = False):
    """Main crawl loop -- recursive HTTP brand crawler."""
    global shutdown_requested

    pool_size = int(os.environ.get("DB_POOL_SIZE", "3"))
    max_overflow = int(os.environ.get("DB_MAX_OVERFLOW", "2"))
    min_delay = float(os.environ.get("CRAWL_MIN_DELAY", "0.5"))
    max_delay = float(os.environ.get("CRAWL_MAX_DELAY", "1.2"))

    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_size=pool_size,
        max_overflow=max_overflow,
    )

    banner("BRAND CRAWLER -- Recursive HTTP")
    info(f"Database: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else '...'}")
    info(f"Rate limiter: {min_delay}-{max_delay}s delay")

    # Seed mode
    if seed:
        current_job_id = await seed_brands(engine, job_id)
        if not job_id:
            job_id = current_job_id
        # If only seeding, we can continue to crawl
        info("Seeding complete. Starting crawl...")

    # Find job
    async with engine.connect() as conn:
        if job_id:
            current_job_id = job_id
        else:
            result = await conn.execute(text("""
                SELECT id FROM crawl_jobs
                WHERE status IN ('running', 'pending') AND level = :level
                ORDER BY id DESC LIMIT 1
            """), {"level": CRAWL_LEVEL})
            row = result.first()
            if not row:
                result = await conn.execute(text("""
                    SELECT id FROM crawl_jobs WHERE level = :level ORDER BY id DESC LIMIT 1
                """), {"level": CRAWL_LEVEL})
                row = result.first()
            if not row:
                raise RuntimeError(
                    f"No crawl job found for level {CRAWL_LEVEL}. "
                    "Run with --seed first to create one."
                )
            current_job_id = row[0]
        info(f"Using job #{current_job_id}")

    # Process loop
    processed = 0
    failed = 0
    parts_pages = 0
    nav_pages = 0
    start_time = time.time()
    last_report_time = start_time
    empty_count = 0

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        http2=False,
    ) as client:
        while not shutdown_requested:
            # Claim next URL (raw SQL with FOR UPDATE SKIP LOCKED)
            item = None
            async with engine.begin() as conn:
                result = await conn.execute(text("""
                    SELECT id, url, parent_brand_id
                    FROM crawl_queue
                    WHERE job_id = :job_id AND status = 'pending' AND level = :level
                    ORDER BY id
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                """), {"job_id": current_job_id, "level": CRAWL_LEVEL})
                row = result.first()
                if row:
                    item = {
                        "id": row[0],
                        "url": row[1],
                        "parent_brand_id": row[2],
                    }
                    await conn.execute(text(
                        "UPDATE crawl_queue SET status = 'processing', processed_at = now() WHERE id = :id"
                    ), {"id": item["id"]})

            if item is None:
                empty_count += 1
                if empty_count >= 5:
                    async with engine.connect() as conn:
                        result = await conn.execute(text("""
                            SELECT COUNT(*) FROM crawl_queue
                            WHERE job_id = :job_id AND level = :level
                            AND status IN ('pending', 'processing')
                        """), {"job_id": current_job_id, "level": CRAWL_LEVEL})
                        remaining = result.scalar()
                        if remaining == 0:
                            break
                        info(f"Waiting for items... ({remaining} remaining)")
                await asyncio.sleep(2)
                continue

            empty_count = 0

            # Process the URL
            ok, page_type = await process_item(
                client, engine, item, current_job_id, min_delay, max_delay
            )
            processed += 1
            if not ok:
                failed += 1
            elif "parts" in page_type:
                parts_pages += 1
            elif page_type not in ("empty",):
                nav_pages += 1

            elapsed = time.time() - start_time
            rate = processed / elapsed * 60 if elapsed > 0 else 0
            icon = "+" if ok else "x"
            short_url = item["url"][:70] + "..." if len(item["url"]) > 70 else item["url"]
            print(
                f"  [{ts()}] {icon} #{processed} [{page_type}] ({rate:.1f}/min) {short_url}",
                flush=True,
            )

            # Progress report every 120 seconds
            now = time.time()
            if now - last_report_time > 120:
                last_report_time = now
                async with engine.connect() as conn:
                    result = await conn.execute(text("""
                        SELECT status, COUNT(*) FROM crawl_queue
                        WHERE job_id = :job_id AND level = :level
                        GROUP BY status
                    """), {"job_id": current_job_id, "level": CRAWL_LEVEL})
                    banner(
                        f"PROGRESS -- {processed} processed, {failed} failed, "
                        f"{parts_pages} parts pages, {nav_pages} nav pages, {rate:.1f}/min"
                    )
                    for status, count in result.all():
                        print(f"    L{CRAWL_LEVEL} {status:<12} {count:>10}", flush=True)

    banner("BRAND CRAWLER STOPPED" if shutdown_requested else "BRAND CRAWL COMPLETE")
    elapsed = time.time() - start_time
    info(f"Processed {processed} URLs in {elapsed/60:.1f} min ({processed/max(elapsed,1)*60:.1f}/min)")
    info(f"Parts pages: {parts_pages}, Nav pages: {nav_pages}, Failed: {failed}")
    await engine.dispose()


# ── Entry point ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Recursive HTTP brand crawler for catcar.info")
    parser.add_argument("--seed", action="store_true", help="Seed brand homepage URLs into crawl_queue")
    parser.add_argument("--job", type=int, default=None, help="Specific job ID to use")
    args = parser.parse_args()

    try:
        asyncio.run(run_crawl(job_id=args.job, seed=args.seed))
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
