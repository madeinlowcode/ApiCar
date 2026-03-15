# Architecture - API CatCar

## Stack

- **Language**: Python 3.12
- **API**: FastAPI + Uvicorn
- **Database**: PostgreSQL 16 + SQLAlchemy 2.0 (async)
- **Cache/Queue**: Redis 7 + ARQ (async task queue)
- **Browser**: Playwright (Chromium headless)
- **Containers**: Docker Compose

## Project Structure

```
api-car/
├── app/                          # FastAPI application
│   ├── main.py                   # Entry point, health check
│   ├── dependencies.py           # FastAPI dependencies (DB session)
│   ├── exceptions.py             # Custom exception handlers
│   ├── api/v1/                   # API route handlers
│   │   ├── router.py             # Main router aggregator
│   │   ├── brands.py             # GET /brands, /brands/{slug}
│   │   ├── models.py             # GET /brands/{slug}/models, /models/{id}
│   │   ├── years.py              # GET /models/{id}/years
│   │   ├── categories.py         # GET /years/{id}/categories
│   │   ├── subgroups.py          # GET /categories/{id}/subgroups
│   │   ├── search.py             # GET /parts/search
│   │   └── admin.py              # POST /admin/crawl/start, GET /admin/crawl/status
│   ├── schemas/                  # Pydantic response/request schemas
│   │   ├── brand.py
│   │   ├── model.py
│   │   ├── part.py
│   │   └── pagination.py
│   ├── services/
│   │   └── catalog.py            # Business logic layer
│   └── cache/
│       └── redis_cache.py        # Redis caching utilities
│
├── crawler/                      # Crawl engine
│   ├── engine.py                 # CrawlEngine - orchestrator, level detection
│   ├── browser.py                # BrowserPool - Playwright browser management
│   ├── rate_limiter.py           # RateLimiter - polite scraping (2-5s delay)
│   ├── state.py                  # CrawlStateManager - queue management
│   ├── tasks.py                  # ARQ task definitions
│   ├── worker.py                 # ARQ worker settings
│   ├── utils.py                  # URL helpers, base64, content hash
│   ├── validators/
│   │   └── model.py              # Data validation for crawled entities
│   └── parsers/                  # One parser per crawl level
│       ├── base.py               # BaseParser abstract class
│       ├── homepage.py           # L1: Extract brands from homepage
│       ├── brand_models.py       # L2: Extract models (table-based catalogs)
│       ├── link_models.py        # L2: Extract models (link-based catalogs)
│       ├── market_selection.py   # L2: Handle market/brand gateway pages
│       ├── model_years.py        # L3: Extract year/variant combos
│       ├── categories.py         # L4: Extract 10 parts categories
│       ├── subgroups.py          # L5: Extract subgroups within categories
│       └── parts.py              # L6: Extract individual parts
│
├── shared/                       # Shared between app and crawler
│   ├── config.py                 # Settings (pydantic-settings, reads .env)
│   ├── database.py               # SQLAlchemy engine + session factory
│   └── models/                   # ORM models
│       ├── base.py               # Base class + TimestampMixin
│       ├── brand.py              # Brand (32 brands, 4 regions)
│       ├── market.py             # Market (per-brand region tabs)
│       ├── model.py              # Model (catalog_code, name, production_date)
│       ├── model_year.py         # ModelYear (year + VIN restriction)
│       ├── parts_category.py     # PartsCategory (10 per model_year)
│       ├── subgroup.py           # Subgroup (MG, illustration_number)
│       ├── part.py               # Part (part_number, description, qty)
│       ├── crawl_job.py          # CrawlJob (status tracking)
│       └── crawl_queue.py        # CrawlQueue (URL queue with parent refs)
│
├── alembic/                      # Database migrations
│   └── versions/
├── scripts/                      # Operational scripts
│   ├── vps-setup.sh              # VPS initial setup (Docker, swap, firewall)
│   ├── deploy.sh                 # Deploy code to VPS via rsync
│   ├── backup.sh                 # PostgreSQL backup
│   ├── restore.sh                # PostgreSQL restore
│   ├── backup-level.sh           # Smart backup with level detection
│   └── status.sh                 # Dashboard with crawl progress
├── docker/                       # Dockerfiles
│   ├── Dockerfile.api            # FastAPI server
│   ├── Dockerfile.worker         # ARQ worker (Playwright included)
│   ├── Dockerfile.crawler        # Dedicated crawler container
│   └── Dockerfile.dev            # Development image
├── docker-compose.yml            # Development compose
├── docker-compose.prod.yml       # Production compose (tuned PostgreSQL)
├── docker-compose.dev.yml        # Dev overrides
├── run_crawl.py                  # Original crawl runner (deprecated)
├── run_crawl_resilient.py        # Resilient crawl runner (USE THIS)
└── pyproject.toml                # Dependencies and tool config
```

## Data Flow

```
catcar.info  ──Playwright──>  Parser  ──SQLAlchemy──>  PostgreSQL
                                                           │
                                                      FastAPI ──> JSON API
```

## Database Schema

```
regions (implicit in brand)
  └── brands (32 total, 4 regions: Europe/Japan/Korea/USA)
       └── markets (39 total, per-brand region tabs)
       └── models (3,843 total)
            └── model_years (8,771 total)
                 └── parts_categories (10 per model_year)
                      └── subgroups (MG + illustration_number)
                           └── parts (part_number, description, qty, PR codes)
```

### Key Relationships

- Brand → Market: one-to-many (brand has multiple market tabs)
- Brand → Model: one-to-many
- Model → ModelYear: one-to-many
- ModelYear → PartsCategory: one-to-many (always 10 categories)
- PartsCategory → Subgroup: one-to-many
- Subgroup → Part: one-to-many

### Crawl Queue

The `crawl_queue` table acts as a persistent BFS queue:
- Each row = one URL to crawl
- `level` = 1-6 (which parser to use)
- `parent_*_id` = foreign key to the parent entity (for data linking)
- `status` = pending | processing | done | failed
- `FOR UPDATE SKIP LOCKED` ensures atomic claims (no race conditions)

## Docker Services

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| api | Dockerfile.api | 8000 | FastAPI server |
| worker | Dockerfile.worker | - | ARQ async task worker |
| crawler | Dockerfile.crawler | - | Dedicated crawl process (profile: crawl) |
| postgres | postgres:16-alpine | 5432 | Database |
| redis | redis:7-alpine | 6379 | Cache + task queue |

### Profiles

- Default: `api`, `worker`, `postgres`, `redis`
- Crawl: add `--profile crawl` to also start `crawler`

## Crawl Levels

| Level | Parser | Input | Output | Notes |
|-------|--------|-------|--------|-------|
| 1 | HomepageParser | catcar.info homepage | brands | 32 brands across 4 regions |
| 2 | BrandModelsParser / LinkModelsParser | brand page | models + markets | Auto-detects table vs link format |
| 3 | ModelYearsParser | model page | model_years | Year + VIN restriction |
| 4 | CategoriesParser | year page | parts_categories | Always 10 categories |
| 5 | SubgroupsParser | category page | subgroups | MG, illustration, description |
| 6 | PartsParser | subgroup page | parts | Position, part_number, description |

### Level 2 Auto-Detection

The crawler engine auto-detects the page format at Level 2:
- **Gateway pages** (h1 = "Market"/"Brand"/"Assortment class"): Follows links, re-enqueues at L2
- **Table-based** (h1 = "Catalog"): Uses BrandModelsParser (VW-style)
- **Link-based** (h1 = "Model" + links): Uses LinkModelsParser (BMW, Ford)
- **Year-first** (h1 = "Year and region selection"): Skipped (not yet supported)

## API Endpoints

Base URL: `/api/v1`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check (DB + Redis status) |
| GET | `/api/v1/brands` | List brands (?region=, ?search=) |
| GET | `/api/v1/brands/{slug}` | Brand detail + markets |
| GET | `/api/v1/brands/{slug}/models` | Models for brand (?market=, ?search=) |
| GET | `/api/v1/models/{id}` | Model detail |
| GET | `/api/v1/models/{id}/years` | Years/variants for model |
| GET | `/api/v1/years/{id}/categories` | Parts categories for year |
| GET | `/api/v1/categories/{id}/subgroups` | Subgroups (?search=) |
| GET | `/api/v1/subgroups/{id}/parts` | Parts in subgroup |
| GET | `/api/v1/parts/search` | Global search (?part_number=, ?description=) |
| GET | `/api/v1/admin/crawl/status` | Crawl job status (requires ADMIN_API_KEY) |
| POST | `/api/v1/admin/crawl/start` | Start new crawl (requires ADMIN_API_KEY) |

## Configuration

Environment variables (via `.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| DATABASE_URL | postgresql+asyncpg://catcar:catcar@localhost:5432/catcar | Async PostgreSQL URL |
| REDIS_URL | redis://localhost:6379/0 | Redis connection |
| ADMIN_API_KEY | change-me-in-production | API key for admin endpoints |
| LOG_LEVEL | INFO | Logging level |
