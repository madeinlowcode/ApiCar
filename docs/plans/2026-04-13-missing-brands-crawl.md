# Missing Brands Crawl - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Crawl 8 missing brands (Honda, Kia, Hyundai, Nissan, Mazda, Subaru, Chrysler, Jaguar) from catcar.info and extract all models, categories, subgroups, and parts.

**Architecture:** Two generic HTML parsers that handle all page types by extracting links from `<td class="table__td">` and `<a class="groups-parts__item">`. A recursive HTTP crawler navigates the full hierarchy. Jaguar handled separately with Playwright.

**Tech Stack:** Python 3.12, httpx, BeautifulSoup4, pytest, PostgreSQL

---

## Pre-requisites

Collect HTML fixtures from the VPS (already on `/tmp/fixtures/`). Copy to local `tests/fixtures/brands/`.

---

### Task 1: Create HTML Fixtures Directory

**Files:**
- Create: `tests/fixtures/brands/` (directory)

**Step 1: Copy fixtures from VPS to local**

```bash
mkdir -p tests/fixtures/brands
```

Then use sftpc to download from VPS:
- `/tmp/fixtures/honda_homepage.html`
- `/tmp/fixtures/honda_year.html`
- `/tmp/fixtures/kia_homepage.html`
- `/tmp/fixtures/kia_year.html`
- `/tmp/fixtures/kia_region_models.html`
- `/tmp/fixtures/kia_categories.html`
- `/tmp/fixtures/nissan_homepage.html`
- `/tmp/fixtures/nissan_region.html`
- `/tmp/fixtures/mazda_homepage.html`
- `/tmp/fixtures/mazda_region.html`
- `/tmp/fixtures/subaru_homepage.html`
- `/tmp/fixtures/subaru_region.html`
- `/tmp/fixtures/hyundai_homepage.html`
- `/tmp/fixtures/chrysler_homepage.html`
- `/tmp/fixtures/chrysler_market.html`

**Step 2: Commit**

```bash
git add tests/fixtures/brands/
git commit -m "test: add HTML fixtures for missing brand pages"
```

---

### Task 2: Write Tests for Year Tabs Parser

**Files:**
- Create: `tests/test_brand_parsers.py`
- Create: `crawler/parsers/brand_navigation.py`

**Step 1: Write failing tests for `parse_year_tabs`**

```python
"""Tests for brand navigation parsers."""
import pytest
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "brands"


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class TestParseYearTabs:
    """Extract year tabs from homepage of Honda, Kia, Hyundai, Chrysler."""

    def test_honda_years(self):
        from crawler.parsers.brand_navigation import parse_year_tabs
        html = read_fixture("honda_homepage.html")
        years = parse_year_tabs(html)
        assert len(years) > 10
        assert all("url" in y and "year" in y for y in years)
        assert any(y["year"] == "2011" for y in years)
        assert all("catcar.info" in y["url"] for y in years)

    def test_kia_years(self):
        from crawler.parsers.brand_navigation import parse_year_tabs
        html = read_fixture("kia_homepage.html")
        years = parse_year_tabs(html)
        assert len(years) > 10
        assert any(y["year"] == "2018" for y in years)

    def test_hyundai_years(self):
        from crawler.parsers.brand_navigation import parse_year_tabs
        html = read_fixture("hyundai_homepage.html")
        years = parse_year_tabs(html)
        assert len(years) > 10
        assert any(y["year"] == "2018" for y in years)

    def test_chrysler_years(self):
        from crawler.parsers.brand_navigation import parse_year_tabs
        html = read_fixture("chrysler_homepage.html")
        years = parse_year_tabs(html)
        assert len(years) > 5
        assert any(y["year"] == "2017" for y in years)

    def test_nissan_no_years(self):
        from crawler.parsers.brand_navigation import parse_year_tabs
        html = read_fixture("nissan_homepage.html")
        years = parse_year_tabs(html)
        assert len(years) == 0  # Nissan has no year tabs
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_brand_parsers.py::TestParseYearTabs -v`
Expected: FAIL with "cannot import name 'parse_year_tabs'"

**Step 3: Implement `parse_year_tabs`**

```python
"""Parsers for navigating brand pages on catcar.info.

Handles brands that use a different layout than Mercedes/VW/Audi/BMW:
- Year tabs: Honda, Kia, Hyundai, Chrysler
- Region links: Nissan, Mazda, Subaru
- groups-parts__item links: Kia categories/subgroups
- table__td links: Honda/Nissan/Mazda/Subaru models
"""
import re
from bs4 import BeautifulSoup


def parse_year_tabs(html: str) -> list[dict]:
    """Extract year tabs from pages with <ul class="tabs"><li>...<a>YYYY</a>.

    Returns list of {"year": "2018", "url": "http://..."}.
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for li in soup.select("ul.tabs li a"):
        url = li.get("href", "")
        text = li.get_text(strip=True)
        if text.isdigit() and len(text) == 4 and "catcar.info" in url:
            results.append({"year": text, "url": url})
    return results
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_brand_parsers.py::TestParseYearTabs -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add crawler/parsers/brand_navigation.py tests/test_brand_parsers.py
git commit -m "feat: add parse_year_tabs for brands with year navigation"
```

---

### Task 3: Write Tests and Implement Region/Market Links Parser

**Files:**
- Modify: `tests/test_brand_parsers.py`
- Modify: `crawler/parsers/brand_navigation.py`

**Step 1: Write failing tests for `parse_region_links`**

```python
class TestParseRegionLinks:
    """Extract region/market links from brand pages."""

    def test_nissan_regions(self):
        from crawler.parsers.brand_navigation import parse_region_links
        html = read_fixture("nissan_homepage.html")
        regions = parse_region_links(html)
        assert len(regions) >= 4
        assert all("url" in r and "name" in r for r in regions)
        assert any("Europe" in r["name"] for r in regions)

    def test_mazda_markets(self):
        from crawler.parsers.brand_navigation import parse_region_links
        html = read_fixture("mazda_homepage.html")
        regions = parse_region_links(html)
        assert len(regions) >= 3
        assert any("Europe" in r["name"] for r in regions)

    def test_subaru_regions(self):
        from crawler.parsers.brand_navigation import parse_region_links
        html = read_fixture("subaru_homepage.html")
        regions = parse_region_links(html)
        assert len(regions) >= 3
        assert any("Europe" in r["name"] for r in regions)

    def test_kia_year_page_has_regions(self):
        from crawler.parsers.brand_navigation import parse_region_links
        html = read_fixture("kia_year.html")
        regions = parse_region_links(html)
        assert len(regions) >= 1
```

**Step 2: Run to verify fail**

Run: `pytest tests/test_brand_parsers.py::TestParseRegionLinks -v`

**Step 3: Implement `parse_region_links`**

Region links appear as `<a>` tags inside market/region sections. They are NOT inside `<ul class="tabs">` and NOT inside `<td class="table__td">`. They typically appear in list items or direct links with text like "Europe", "USA", "Canada", "Japan".

```python
def parse_region_links(html: str) -> list[dict]:
    """Extract region/market links from brand pages.

    Looks for <a> links with region-like text (Europe, USA, Canada, Japan, etc.)
    that point to catcar.info URLs. Excludes year tabs and model table links.

    Returns list of {"name": "Europe LHD", "url": "http://..."}.
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen_urls = set()

    # Pattern 1: <li><a> links outside of tabs (Chrysler markets)
    # Pattern 2: Direct <a> links with region text (Nissan, Mazda, Subaru)
    for a in soup.find_all("a", href=True):
        url = a["href"]
        text = a.get_text(strip=True)

        if not url or "catcar.info" not in url or url in seen_urls:
            continue
        if not text or text.isdigit() or len(text) > 50:
            continue

        # Skip year tabs, model links in table cells, and navigation
        parent = a.parent
        if parent and parent.name == "li" and parent.parent and "tabs" in (parent.parent.get("class") or []):
            continue
        if parent and parent.name == "td":
            continue

        # Check if URL contains region/market indicators
        if "region==" in url or "market==" in url or "Region" in url:
            seen_urls.add(url)
            results.append({"name": text, "url": url})

    return results
```

**Step 4: Run tests, iterate until pass**

Run: `pytest tests/test_brand_parsers.py::TestParseRegionLinks -v`

**Step 5: Commit**

```bash
git add crawler/parsers/brand_navigation.py tests/test_brand_parsers.py
git commit -m "feat: add parse_region_links for Nissan, Mazda, Subaru, Kia"
```

---

### Task 4: Write Tests and Implement Table Model Links Parser

**Files:**
- Modify: `tests/test_brand_parsers.py`
- Modify: `crawler/parsers/brand_navigation.py`

**Step 1: Write failing tests for `parse_table_links`**

```python
class TestParseTableLinks:
    """Extract model links from <td class='table__td'><a>."""

    def test_honda_models(self):
        from crawler.parsers.brand_navigation import parse_table_links
        html = read_fixture("honda_year.html")
        models = parse_table_links(html)
        assert len(models) >= 5
        assert all("url" in m and "name" in m for m in models)
        assert any("ACCORD" in m["name"] for m in models)
        assert any("CIVIC" in m["name"] or "CITY" in m["name"] for m in models)

    def test_nissan_models(self):
        from crawler.parsers.brand_navigation import parse_table_links
        html = read_fixture("nissan_region.html")
        models = parse_table_links(html)
        assert len(models) >= 5
        assert any("INTERSTAR" in m["name"] or "NV" in m["name"] for m in models)

    def test_mazda_models(self):
        from crawler.parsers.brand_navigation import parse_table_links
        html = read_fixture("mazda_region.html")
        models = parse_table_links(html)
        assert len(models) >= 5
        assert any("323" in m["name"] for m in models)

    def test_subaru_models(self):
        from crawler.parsers.brand_navigation import parse_table_links
        html = read_fixture("subaru_region.html")
        models = parse_table_links(html)
        assert len(models) >= 5
        assert any("LEGACY" in m["name"] for m in models)
```

**Step 2: Run to verify fail**

**Step 3: Implement `parse_table_links`**

```python
def parse_table_links(html: str) -> list[dict]:
    """Extract links from <td class="table__td"><a> elements.

    Used for model listings on Honda, Nissan, Mazda, Subaru pages.
    Returns list of {"name": "ACCORD", "url": "http://..."}.
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen_urls = set()

    for td in soup.select("td.table__td"):
        a = td.find("a", href=True)
        if not a:
            continue
        url = a["href"]
        text = a.get_text(strip=True)
        if not url or "catcar.info" not in url or not text:
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        results.append({"name": text, "url": url})

    return results
```

**Step 4: Run tests, verify pass**

**Step 5: Commit**

```bash
git add crawler/parsers/brand_navigation.py tests/test_brand_parsers.py
git commit -m "feat: add parse_table_links for Honda, Nissan, Mazda, Subaru models"
```

---

### Task 5: Write Tests and Implement Groups-Parts Links Parser

**Files:**
- Modify: `tests/test_brand_parsers.py`
- Modify: `crawler/parsers/brand_navigation.py`

**Step 1: Write failing tests for `parse_groups_parts_links`**

```python
class TestParseGroupsPartsLinks:
    """Extract links from <a class="groups-parts__item">."""

    def test_kia_models(self):
        from crawler.parsers.brand_navigation import parse_groups_parts_links
        html = read_fixture("kia_region_models.html")
        items = parse_groups_parts_links(html)
        assert len(items) >= 3
        assert all("url" in i and "name" in i for i in items)

    def test_kia_categories(self):
        from crawler.parsers.brand_navigation import parse_groups_parts_links
        html = read_fixture("kia_categories.html")
        items = parse_groups_parts_links(html)
        assert len(items) >= 5
        # Kia categories: ENGINE, TRANSMISSION, CHASSIS, BODY, TRIM, ELECTRICAL, ACCESSORY
        names = [i["name"].upper() for i in items]
        assert any("ENGINE" in n for n in names)
```

**Step 2: Run to verify fail**

**Step 3: Implement**

```python
def parse_groups_parts_links(html: str) -> list[dict]:
    """Extract links from <a class="groups-parts__item"> elements.

    Used for Kia/Hyundai model listings and category/subgroup navigation.
    Returns list of {"name": "ENGINE", "url": "http://..."}.
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen_urls = set()

    for a in soup.select("a.groups-parts__item"):
        url = a.get("href", "")
        text = a.get_text(strip=True)
        if not url or "catcar.info" not in url or url in seen_urls:
            continue
        seen_urls.add(url)
        # Extract name from URL-encoded data if text is empty
        if not text:
            continue
        results.append({"name": text, "url": url})

    return results
```

**Step 4: Run tests, verify pass**

**Step 5: Commit**

```bash
git add crawler/parsers/brand_navigation.py tests/test_brand_parsers.py
git commit -m "feat: add parse_groups_parts_links for Kia/Hyundai navigation"
```

---

### Task 6: Write Tests and Implement Auto-Detect Page Type

**Files:**
- Modify: `tests/test_brand_parsers.py`
- Modify: `crawler/parsers/brand_navigation.py`

**Step 1: Write failing tests for `detect_and_parse`**

```python
class TestDetectAndParse:
    """Auto-detect page type and extract all navigation links."""

    def test_honda_homepage_returns_years(self):
        from crawler.parsers.brand_navigation import detect_and_parse
        html = read_fixture("honda_homepage.html")
        result = detect_and_parse(html)
        assert result["type"] == "years"
        assert len(result["items"]) > 10

    def test_nissan_homepage_returns_regions(self):
        from crawler.parsers.brand_navigation import detect_and_parse
        html = read_fixture("nissan_homepage.html")
        result = detect_and_parse(html)
        assert result["type"] == "regions"
        assert len(result["items"]) >= 4

    def test_honda_year_returns_models(self):
        from crawler.parsers.brand_navigation import detect_and_parse
        html = read_fixture("honda_year.html")
        result = detect_and_parse(html)
        assert result["type"] == "table_links"
        assert len(result["items"]) >= 5

    def test_kia_categories_returns_groups(self):
        from crawler.parsers.brand_navigation import detect_and_parse
        html = read_fixture("kia_categories.html")
        result = detect_and_parse(html)
        assert result["type"] == "groups_parts"
        assert len(result["items"]) >= 5

    def test_parts_page_returns_parts(self):
        """When page has <tr name="POS"> with part numbers, return type=parts."""
        from crawler.parsers.brand_navigation import detect_and_parse
        # A page with parts table should be detected
        html = '<tr name="10"><td class="table__td">10</td><td class="table__td"><a href="http://tradesoft">A 123</a></td><td class="table__td"><b>BOLT</b></td><td class="table__td"></td><td class="table__td">1</td><td class="table__td">---</td></tr>'
        result = detect_and_parse(html)
        assert result["type"] == "parts"
```

**Step 2: Run to verify fail**

**Step 3: Implement `detect_and_parse`**

```python
def detect_and_parse(html: str) -> dict:
    """Auto-detect page type and extract navigation links.

    Returns {"type": str, "items": list[dict]} where type is one of:
    - "years": page has year tabs
    - "regions": page has region/market links
    - "groups_parts": page has groups-parts__item links
    - "table_links": page has table__td links
    - "parts": page has parts table (tr[name] with part numbers)
    - "empty": no recognizable content
    """
    soup = BeautifulSoup(html, "html.parser")

    # Check for parts table first (highest priority)
    parts_rows = soup.select("tr[name]")
    if parts_rows:
        for tr in parts_rows:
            tds = tr.select("td.table__td")
            if len(tds) >= 3 and tds[1].find("a"):
                return {"type": "parts", "items": []}

    # Check for groups-parts__item links
    groups = parse_groups_parts_links(html)
    if groups:
        return {"type": "groups_parts", "items": groups}

    # Check for year tabs
    years = parse_year_tabs(html)
    if years:
        return {"type": "years", "items": years}

    # Check for region/market links
    regions = parse_region_links(html)
    if regions:
        return {"type": "regions", "items": regions}

    # Check for table links (models)
    table_links = parse_table_links(html)
    if table_links:
        return {"type": "table_links", "items": table_links}

    return {"type": "empty", "items": []}
```

**Step 4: Run all tests**

Run: `pytest tests/test_brand_parsers.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add crawler/parsers/brand_navigation.py tests/test_brand_parsers.py
git commit -m "feat: add detect_and_parse for auto page type detection"
```

---

### Task 7: Create Recursive Brand Crawler Runner

**Files:**
- Create: `run_crawl_brands.py`

This is the main crawler script. It:
1. Seeds URLs for the 8 missing brands into crawl_queue
2. Claims URLs, fetches HTML via httpx
3. Uses `detect_and_parse` to determine page type
4. If navigation page: enqueue child URLs
5. If parts page: use `parse_parts_html` to extract and save parts
6. Uses raw SQL (no ORM) like `run_crawl_http.py`

Implementation follows the same pattern as `run_crawl_http.py` but with recursive level detection instead of fixed L6-only.

**Step 1: Implement the runner**

Key differences from `run_crawl_http.py`:
- Processes ALL levels (not just L6)
- Uses `detect_and_parse` to determine what to extract
- Enqueues child URLs when navigating
- Maps extracted data to correct DB tables based on depth

**Step 2: Test locally with a single URL**

**Step 3: Commit**

```bash
git add run_crawl_brands.py
git commit -m "feat: add recursive HTTP brand crawler for missing brands"
```

---

### Task 8: Create Dockerfile and Docker Compose Service

**Files:**
- Modify: `docker-compose.prod.yml`

**Step 1: Add `crawler-brands` service**

Reuses `Dockerfile.crawler-http` since it's also HTTP-only.

```yaml
  crawler-brands:
    build:
      context: .
      dockerfile: docker/Dockerfile.crawler-http
    command: ["python", "run_crawl_brands.py"]
    env_file: .env
    environment:
      DATABASE_URL: ${DATABASE_URL}
      CRAWL_MIN_DELAY: ${CRAWL_HTTP_MIN_DELAY:-0.3}
      CRAWL_MAX_DELAY: ${CRAWL_HTTP_MAX_DELAY:-0.8}
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 128M
    profiles:
      - crawl-brands
```

**Step 2: Commit**

```bash
git add docker-compose.prod.yml
git commit -m "feat: add crawler-brands service to docker-compose"
```

---

### Task 9: Deploy and Test on VPS

**Step 1: Upload all new files to VPS**
**Step 2: Build image**
**Step 3: Seed 8 brand URLs into crawl_queue**
**Step 4: Start with 1 crawler to validate**
**Step 5: Check logs for successful parsing**
**Step 6: Scale to 30 crawlers**
**Step 7: Monitor progress**

---

### Task 10: Handle Jaguar (Playwright)

Jaguar uses AJAX to load models — requires Playwright. Lower priority. Can be done after the HTTP brands are complete.

**Step 1: Investigate Jaguar page structure with Playwright**
**Step 2: Write parser for Jaguar-specific layout**
**Step 3: Run with 1 Playwright crawler**

---

## Execution Order

1. Tasks 1-6: Parsers + Tests (TDD) — local development
2. Task 7: Crawler runner — local development
3. Tasks 8-9: Deploy + Run — VPS
4. Task 10: Jaguar — VPS with Playwright
