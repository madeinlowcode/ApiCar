# Crawl Operations Guide

> This document is for Claude Code sessions operating the crawler on VPS.

## Quick Reference

### Check crawl status
```sql
-- Run via: docker compose exec -T postgres psql -U catcar -c "..."
SELECT level, status, COUNT(*)
FROM crawl_queue
GROUP BY level, status
ORDER BY level, status;
```

### Check table counts
```sql
SELECT 'brands' as t, COUNT(*) FROM brands
UNION ALL SELECT 'markets', COUNT(*) FROM markets
UNION ALL SELECT 'models', COUNT(*) FROM models
UNION ALL SELECT 'model_years', COUNT(*) FROM model_years
UNION ALL SELECT 'parts_categories', COUNT(*) FROM parts_categories
UNION ALL SELECT 'subgroups', COUNT(*) FROM subgroups
UNION ALL SELECT 'parts', COUNT(*) FROM parts
ORDER BY 1;
```

### Check DB size
```sql
SELECT pg_size_pretty(pg_database_size('catcar'));
```

## Understanding the Crawl

### How it works

1. `run_crawl_resilient.py` runs as PID 1 in the `crawler` container
2. It finds the existing job (job #9) or creates a new one
3. It resets any stale "processing" items (stuck from crash)
4. It claims URLs one at a time from `crawl_queue` (atomic via `FOR UPDATE SKIP LOCKED`)
5. For each URL, it opens Playwright, navigates, takes ARIA snapshot, parses data
6. Parsed data is saved to the corresponding table (brands, models, etc.)
7. Child URLs are enqueued for the next level
8. On crash, Docker restarts the container and it resumes automatically

### Crawl levels in detail

| Level | URLs (estimated) | Time per URL | Total estimate |
|-------|-------------------|-------------|----------------|
| L1 Brands | 2 | 5-10s | < 1 min |
| L2 Models | 168 | 5-10s | ~20 min |
| L3 Years | 7,390 | 5-10s | ~12 hours |
| L4 Categories | 10,827 | 5-10s | ~18 hours |
| L5 Subgroups | ~244,000 | 5-10s | ~14 days |
| L6 Parts | ~millions | 5-10s | weeks |

### Rate limiting

- Min delay: 2 seconds between requests
- Max delay: 5 seconds between requests
- Max concurrent: 1 request at a time
- Exponential backoff on errors (429, 5xx)
- Max 3 retries per URL

## Resuming a Crawl

The crawler is designed to auto-resume. Just start the container:

```bash
# Using production compose
docker compose -f docker-compose.prod.yml --profile crawl up -d crawler

# Or using dev compose
docker compose --profile crawl up -d crawler
```

It will:
1. Find job #9 (or latest running/pending job)
2. Reset stale items (stuck in "processing" for > 5 min)
3. Continue from pending URLs, ordered by level then ID

### Limiting max level

To prevent advancing to the next level:
```bash
# Stop the crawler
docker compose -f docker-compose.prod.yml stop crawler

# Run manually with level limit
docker compose -f docker-compose.prod.yml run --rm crawler \
    python run_crawl_resilient.py --level 4
```

Or modify the CMD in docker-compose.prod.yml:
```yaml
crawler:
    ...
    command: ["python", "run_crawl_resilient.py", "--level", "4"]
```

## Making Backups

### Full backup (recommended)
```bash
./scripts/backup.sh
```

### Smart backup with level detection
```bash
./scripts/backup-level.sh
```

### Manual backup
```bash
docker compose exec -T postgres pg_dump -U catcar --format=custom catcar \
    | gzip > backups/catcar_$(date +%Y-%m-%d_%H-%M).sql.gz
```

### Backup strategy
- Each backup is a **complete snapshot** of the entire database
- Backups are NOT incremental — each one contains everything
- You can only restore ONE backup (the latest one)
- Do NOT try to merge backups from different machines (ID conflicts)

## Fixing Common Issues

### Crawler stops/crashes silently

The `restart: unless-stopped` policy will auto-restart it. Check logs:
```bash
docker compose -f docker-compose.prod.yml logs --tail 200 crawler
```

### URLs stuck in "processing"

The resilient runner auto-resets stale items on startup. To manually reset:
```sql
UPDATE crawl_queue SET status='pending'
WHERE status='processing'
AND processed_at < NOW() - INTERVAL '10 minutes';
```

### VARCHAR column too small

If you see errors like `value too long for type character varying(N)`:
```sql
-- Example: increase parts_categories.name to 500
ALTER TABLE parts_categories ALTER COLUMN name TYPE VARCHAR(500);
```
Also update the corresponding model in `shared/models/`.

### Disk space critical

The crawler auto-stops at < 10GB free. To free space:
```bash
# Clean Docker
docker system prune -f
docker builder prune -f

# Remove old backups
ls -lh backups/
rm backups/old_backup.sql.gz

# Check what's using space
du -sh /var/lib/docker/
df -h
```

### Database performance

If queries are slow:
```sql
-- Check table sizes
SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
FROM pg_stat_user_tables ORDER BY pg_total_relation_size(relid) DESC;

-- Run VACUUM ANALYZE after large data loads
VACUUM ANALYZE;

-- Check slow queries
SELECT query, calls, mean_exec_time
FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;
```

## Monitoring Checklist

When checking on the crawl:

1. Is the crawler container running? `docker compose ps`
2. Is it processing? Check `crawl_queue` status counts
3. Are there errors? Check `status='failed'` count
4. Is disk space OK? `df -h /`
5. Is memory OK? `docker stats --no-stream`
6. How long until current level finishes? (pending_count * avg_seconds_per_url)
