# Continuation Guide for Claude Code (VPS Session)

> This document tells the next Claude Code session exactly what state the project is in
> and what needs to be done to continue.

## Current Situation

You are on a VPS. The project was developed locally and migrated here to continue the
data crawl on a stable server that runs 24/7.

### What's already done

- Full project codebase is ready (API + Crawler + Docker)
- Crawl Levels 1-3 are 100% complete
- Level 4 is approximately 55% complete
- All parsers for all 6 levels are written and tested
- Docker Compose stack works (api, worker, crawler, postgres, redis)
- Resilient crawl runner (`run_crawl_resilient.py`) handles auto-resume

### What you need to do

1. **Restore the database backup** (if not already done)
2. **Start the crawler container** to resume the crawl
3. **Monitor progress** and handle any issues
4. **Make backups** when levels complete

## Step-by-Step: Getting Started

### 1. Check if database has data

```bash
docker compose -f docker-compose.prod.yml exec -T postgres psql -U catcar -c "
SELECT level, status, COUNT(*)
FROM crawl_queue
GROUP BY level, status
ORDER BY level, status;
"
```

If this returns data, the backup was already restored. Skip to step 3.

### 2. Restore backup (if needed)

```bash
# Make sure postgres is running
docker compose -f docker-compose.prod.yml up -d postgres
sleep 5

# Restore (file should be in backups/)
./scripts/restore.sh backups/catcar_L4_partial_55pct_2026-03-15.sql.gz
```

### 3. Start all services

```bash
# Start API + Worker + Redis
docker compose -f docker-compose.prod.yml up -d

# Start crawler
docker compose -f docker-compose.prod.yml --profile crawl up -d crawler
```

### 4. Verify crawler is working

```bash
# Check container is running
docker compose -f docker-compose.prod.yml ps

# Watch logs (should see URLs being processed)
docker compose -f docker-compose.prod.yml logs -f --tail 20 crawler
```

You should see output like:
```
[HH:MM:SS] RESILIENT CRAWL - max_level=6
[HH:MM:SS] Found existing job #9 (status=running)
[HH:MM:SS] Reset N stale items to pending
[HH:MM:SS] ok L4 #1 (X.X/min) https://www.catcar.info/...
```

### 5. Monitor

Check progress periodically:
```bash
docker compose -f docker-compose.prod.yml exec -T postgres psql -U catcar -c "
SELECT level, status, COUNT(*) FROM crawl_queue GROUP BY level, status ORDER BY level, status;
"
```

## Expected Timeline

| Phase | URLs | Estimated Duration |
|-------|------|--------------------|
| Finish L4 | ~4,850 | ~8-13 hours |
| Complete L5 | ~244,000 | ~11-17 days |
| Complete L6 | millions | weeks |

## When a Level Completes

When you see all URLs for a level in "done" status, make a backup:

```bash
./scripts/backup-level.sh
# or manually:
docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U catcar --format=custom catcar \
    | gzip > backups/catcar_LX_complete_$(date +%Y-%m-%d_%H-%M).sql.gz
```

## Crawler Behavior

### Auto-resume
- If the crawler crashes, Docker restarts it automatically (`restart: unless-stopped`)
- On restart, it resets stale "processing" items and continues from pending

### Disk protection
- Stops cleanly when disk < 10GB free
- Warns at < 15GB free

### Graceful shutdown
- `docker compose stop crawler` sends SIGTERM
- Crawler finishes current URL, then exits cleanly
- On next start, it resumes from where it stopped

### Rate limiting
- 2-5 second random delay between requests
- 1 concurrent request max
- 3 retries with exponential backoff on errors

## Important Files

| File | Purpose |
|------|---------|
| `run_crawl_resilient.py` | Main crawl runner (PID 1 in crawler container) |
| `crawler/engine.py` | Crawl orchestrator, level detection, parser dispatch |
| `crawler/state.py` | Queue management (claim, done, failed, reset stale) |
| `crawler/parsers/*.py` | One parser per level |
| `shared/models/*.py` | SQLAlchemy ORM models |
| `docker-compose.prod.yml` | Production Docker Compose |
| `scripts/backup.sh` | Database backup script |
| `scripts/restore.sh` | Database restore script |
| `scripts/status.sh` | Status dashboard |

## Troubleshooting

### "No pending items" but level not complete
Check for failed items:
```sql
SELECT level, COUNT(*) FROM crawl_queue WHERE status='failed' GROUP BY level;
```
To retry failed items:
```sql
UPDATE crawl_queue SET status='pending', retries=0 WHERE status='failed';
```

### Crawler container keeps restarting
Check logs for the crash reason:
```bash
docker compose -f docker-compose.prod.yml logs --tail 100 crawler
```

Common causes:
- Database connection timeout: check postgres is healthy
- Memory OOM: check `docker stats`
- VARCHAR too small: check for "value too long" errors, fix with ALTER TABLE

### Can't connect to database
```bash
# Check postgres is running and healthy
docker compose -f docker-compose.prod.yml ps postgres
docker compose -f docker-compose.prod.yml exec -T postgres pg_isready -U catcar
```
