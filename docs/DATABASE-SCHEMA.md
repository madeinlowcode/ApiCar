# Database Schema - API CatCar

## Entity Relationship

```
brands (32)
├── markets (39)               # brand_id FK
└── models (3,843)             # brand_id FK, market_id FK (nullable)
    └── model_years (8,771)    # model_id FK
        └── parts_categories   # model_year_id FK
            └── subgroups      # category_id FK
                └── parts      # subgroup_id FK
```

## Tables

### brands
```sql
CREATE TABLE brands (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    region VARCHAR(50),              -- Europe, Japan, Korea, USA
    catalog_path VARCHAR(100),       -- "/audivw/", "/bmw/"
    catalog_url TEXT,                -- Full URL with base64 params
    logo_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### markets
```sql
CREATE TABLE markets (
    id SERIAL PRIMARY KEY,
    brand_id INTEGER NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,      -- "Europe", "USA", "Brazil"
    catalog_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(brand_id, name)
);
```

### models
```sql
CREATE TABLE models (
    id SERIAL PRIMARY KEY,
    brand_id INTEGER NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    market_id INTEGER REFERENCES markets(id) ON DELETE SET NULL,
    catalog_code VARCHAR(20),        -- "GOLF", "AMA"
    name VARCHAR(200) NOT NULL,      -- "Golf/Variant/4Motion"
    production_date VARCHAR(200),    -- "1998-..." (VARCHAR(200) for long Mercedes values)
    production_codes VARCHAR(200),   -- "B;D;G;J;K"
    catalog_url TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(brand_id, market_id, catalog_code)
);
```

### model_years
```sql
CREATE TABLE model_years (
    id SERIAL PRIMARY KEY,
    model_id INTEGER NOT NULL REFERENCES models(id) ON DELETE CASCADE,
    year INTEGER,
    restriction VARCHAR(200),        -- "1J-W-000 001 >>", "Golf 5G1***"
    catalog_url TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### parts_categories
```sql
CREATE TABLE parts_categories (
    id SERIAL PRIMARY KEY,
    model_year_id INTEGER NOT NULL REFERENCES model_years(id) ON DELETE CASCADE,
    category_index SMALLINT NOT NULL,  -- 0-9
    name VARCHAR(300) NOT NULL,        -- "Engine", "Gearbox" (VARCHAR(300) for long Ford names)
    catalog_url TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(model_year_id, category_index)
);
```

### subgroups
```sql
CREATE TABLE subgroups (
    id SERIAL PRIMARY KEY,
    category_id INTEGER NOT NULL REFERENCES parts_categories(id) ON DELETE CASCADE,
    main_group VARCHAR(10),            -- MG column
    illustration_number VARCHAR(20),   -- "10003"
    description VARCHAR(300),          -- "base engine"
    remark VARCHAR(300),               -- "1.0 ltr."
    model_data TEXT,                   -- "petrol eng.+ CHZD"
    catalog_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(category_id, illustration_number)
);
```

### parts
```sql
CREATE TABLE parts (
    id SERIAL PRIMARY KEY,
    subgroup_id INTEGER NOT NULL REFERENCES subgroups(id) ON DELETE CASCADE,
    position VARCHAR(10),              -- Position in diagram
    part_number VARCHAR(50) NOT NULL,  -- OEM: "04C100032F"
    description TEXT,
    remark VARCHAR(300),
    quantity VARCHAR(10),              -- ST column
    model_data TEXT,                   -- PR codes
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
-- Critical index for search:
CREATE INDEX idx_parts_part_number ON parts(part_number);
```

### crawl_jobs
```sql
CREATE TABLE crawl_jobs (
    id SERIAL PRIMARY KEY,
    brand_id INTEGER REFERENCES brands(id),
    level INTEGER DEFAULT 1,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, running, completed, failed
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### crawl_queue
```sql
CREATE TABLE crawl_queue (
    id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES crawl_jobs(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    level INTEGER NOT NULL,            -- 1-6
    status VARCHAR(20) DEFAULT 'pending',  -- pending, processing, done, failed
    retries INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    error_message TEXT,
    content_hash VARCHAR(64),
    processed_at TIMESTAMPTZ,
    -- Parent references for data linking
    parent_brand_id INTEGER,
    parent_model_id INTEGER,
    parent_year_id INTEGER,
    parent_category_id INTEGER,
    parent_subgroup_id INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_crawl_queue_job_status ON crawl_queue(job_id, status);
CREATE INDEX idx_crawl_queue_level ON crawl_queue(level);
```

## Important Notes

- All FKs use `ON DELETE CASCADE` for clean hierarchical deletion
- `catalog_url` is stored on every entity because catcar.info uses base64-encoded URL params that are the only reliable way to navigate back
- The `crawl_queue.parent_*_id` columns link crawled URLs to their parent entities so the parser knows where to attach new data
- `FOR UPDATE SKIP LOCKED` is used on `crawl_queue` for atomic claim without contention
- The `parts.part_number` index is critical for the search endpoint
