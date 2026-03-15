# Project Status - API CatCar

> Last updated: 2026-03-15

## Overview

API REST that crawls and serves data from catcar.info (online automotive parts catalog).
The site has no public API, so we crawl it with Playwright, store data in PostgreSQL,
and serve via FastAPI.

## Current State

### Crawl Progress (as of 2026-03-15 12:50 UTC)

| Level | Name | Status | Done | Pending | Total |
|-------|------|--------|------|---------|-------|
| 1 | Brands | COMPLETE | 2 | 0 | 2 |
| 2 | Models | COMPLETE | 168 | 0 | 168 |
| 3 | Years/Variants | COMPLETE | 7,390 | 0 | 7,390 |
| 4 | Categories | IN PROGRESS (55%) | 5,975 | 4,852 | 10,827 |
| 5 | Subgroups | QUEUED | 0 | 243,932 | 243,932 |
| 6 | Parts | NOT STARTED | 0 | 0 | ~millions |

### Database Table Counts

| Table | Rows | Notes |
|-------|------|-------|
| brands | 32 | All brands extracted (4 regions) |
| markets | 39 | Per-brand market tabs |
| models | 3,843 | All models across all brands/markets |
| model_years | 8,771 | Year + VIN restriction combos |
| parts_categories | 110,412 | 10 categories per model_year (partial) |
| subgroups | 0 | Waiting for L5 crawl |
| parts | 0 | Waiting for L6 crawl |

### Backup Available

File: `catcar_L4_partial_55pct_2026-03-15.sql.gz` (9.2 MB)
Contains: Complete L1-L3 + partial L4 (55%) + L5 queue entries

### Job Info

- Job ID: **9**
- Job status: **running**
- The crawl queue has all URLs pre-enqueued up to L5

## What Needs to Be Done

### Immediate (VPS)

1. **Restore backup** on VPS PostgreSQL
2. **Resume crawl from L4** (4,852 pending URLs) using the resilient runner
3. **Complete L4** (~2-3 hours at current rate)
4. **Complete L5** - 243,932 subgroup URLs (this is the bulk of the work)
5. **Complete L6** - Parts extraction (millions of URLs, will take days/weeks)

### After Crawl Completes

6. Run full API test suite against populated database
7. Verify search endpoint works with real part numbers
8. Performance-tune queries with proper indexes
9. Set up periodic re-crawl (Celery Beat or cron)

## What's Working

- FastAPI server with all endpoints
- All 6 level parsers (homepage, brand_models, model_years, categories, subgroups, parts)
- Resilient crawl runner with auto-resume on crash
- Docker Compose stack (api, worker, crawler, postgres, redis)
- Backup/restore scripts
- Rate limiting (2-5s delay, 1 concurrent request)
- Stale URL detection and reset

## Known Issues / Fixes Applied

1. **VARCHAR too small**: `parts_categories.name` was VARCHAR(100), some Ford categories exceeded it. Fixed to VARCHAR(300). Already applied via ALTER TABLE on running DB and in model code.

2. **Model.production_date**: Was VARCHAR(50), Mercedes had longer values. Fixed to VARCHAR(200). Already in code and DB.

3. **Crawl process dying**: The old approach (`docker exec -d worker python run_crawl.py`) created a child process that Docker didn't manage. Fixed with dedicated `run_crawl_resilient.py` as PID 1 in crawler container.

4. **`shutdown_requested` variable**: The `run_crawl_resilient.py` had a bug where `global shutdown_requested` was missing in `run_crawl()`. Fixed on 2026-03-15.
