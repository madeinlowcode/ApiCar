# VPS Deploy Guide - API CatCar

## Prerequisites

- VPS with Ubuntu 22.04+ or Debian 12+
- Minimum 4GB RAM, 50GB+ disk
- SSH access as root

## Step 1: VPS Initial Setup

```bash
# On VPS as root
bash scripts/vps-setup.sh
```

This installs Docker, creates swap, configures firewall, and generates `.env` with random passwords.

## Step 2: Clone Repository

```bash
cd /opt
git clone <repo-url> catcar
cd catcar
```

## Step 3: Restore Database Backup

The backup file `catcar_L4_partial_55pct_2026-03-15.sql.gz` contains all crawl data up to L4 (55% complete).
You need to download it from Google Drive and place it in the `backups/` directory.

```bash
# Place backup file in backups/
mkdir -p backups
# Copy backup file here (from Drive or SCP)

# Start only PostgreSQL first
docker compose -f docker-compose.prod.yml up -d postgres
# Wait for healthy
docker compose -f docker-compose.prod.yml ps

# Restore
./scripts/restore.sh backups/catcar_L4_partial_55pct_2026-03-15.sql.gz
```

## Step 4: Start All Services

```bash
# Start API + Worker + Redis (without crawler)
docker compose -f docker-compose.prod.yml up -d

# Verify everything is running
docker compose -f docker-compose.prod.yml ps

# Test API health
curl http://localhost:8000/health
```

## Step 5: Resume Crawl

```bash
# Start the dedicated crawler container
docker compose -f docker-compose.prod.yml --profile crawl up -d crawler

# Check logs
docker compose -f docker-compose.prod.yml logs -f crawler
```

The crawler will automatically:
1. Find the existing job (#9)
2. Reset any stale "processing" items
3. Continue from where it left off (L4 pending URLs)
4. Process L4 → L5 → L6 sequentially
5. Stop when all levels are done

## Step 6: Monitor Progress

```bash
# Quick status check
docker compose -f docker-compose.prod.yml exec -T postgres psql -U catcar -c "
SELECT level, status, COUNT(*)
FROM crawl_queue
GROUP BY level, status
ORDER BY level, status;
"

# Watch crawler logs
docker compose -f docker-compose.prod.yml logs -f --tail 50 crawler

# Use status script
./scripts/status.sh

# Continuous monitoring
./scripts/status.sh --watch
```

## Managing the Crawl

### Stop crawl gracefully
```bash
docker compose -f docker-compose.prod.yml stop crawler
```

### Restart crawl
```bash
docker compose -f docker-compose.prod.yml --profile crawl up -d crawler
```

### Limit crawl to specific level
Edit the CMD in docker-compose.prod.yml crawler service, or:
```bash
docker compose -f docker-compose.prod.yml exec crawler python run_crawl_resilient.py --level 4
```

### Make backup at any point
```bash
./scripts/backup.sh
# or for smart backup with level detection:
./scripts/backup-level.sh
```

## Production Compose Details

`docker-compose.prod.yml` includes:
- **Memory limits**: API 512MB, Worker 2GB, Crawler 2GB, Postgres 4GB, Redis 256MB
- **Tuned PostgreSQL**: shared_buffers=1GB, effective_cache_size=3GB, work_mem=16MB
- **Localhost-only ports**: PostgreSQL and Redis bound to 127.0.0.1
- **env_file**: reads `.env` for secrets
- **shm_size**: 256MB for Playwright/Chromium

## Disk Space

Monitor disk usage:
```bash
df -h /
docker system df
```

The crawler has built-in disk protection:
- **Stops at < 10GB free** (exits cleanly)
- **Warns at < 15GB free** (continues but logs warning)

To free space:
```bash
# Remove old Docker images
docker system prune -f

# Remove old backups
ls -lh backups/
```

## Troubleshooting

### Crawler not processing
```bash
# Check if crawler is running
docker compose -f docker-compose.prod.yml --profile crawl ps

# Check logs for errors
docker compose -f docker-compose.prod.yml logs --tail 100 crawler

# Check for stale items in queue
docker compose -f docker-compose.prod.yml exec -T postgres psql -U catcar -c "
SELECT status, COUNT(*) FROM crawl_queue WHERE status='processing' GROUP BY status;
"
```

### Database connection issues
```bash
# Check postgres health
docker compose -f docker-compose.prod.yml exec -T postgres pg_isready -U catcar

# Check connections
docker compose -f docker-compose.prod.yml exec -T postgres psql -U catcar -c "
SELECT count(*) FROM pg_stat_activity WHERE datname='catcar';
"
```

### Memory issues
```bash
# Check container memory usage
docker stats --no-stream

# If crawler OOM, reduce browser pool or increase memory limit
```
