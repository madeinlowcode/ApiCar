"""Dry-run crawl test: navigate all 6 levels and show extracted data without saving."""
import asyncio
import json
import sys

from playwright.async_api import async_playwright

# Add project root to path
sys.path.insert(0, "/app")

from crawler.parsers.homepage import HomepageParser
from crawler.parsers.brand_models import BrandModelsParser
from crawler.parsers.model_years import ModelYearsParser
from crawler.parsers.categories import CategoriesParser
from crawler.parsers.subgroups import SubgroupsParser
from crawler.parsers.parts import PartsParser
from crawler.utils import ensure_english_url


async def get_snapshot(page, url):
    nav_url = ensure_english_url(url)
    await page.goto(nav_url, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(5000)
    return await page.locator("body").aria_snapshot()


def show(title, items, fields, max_items=5):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"  Total: {len(items)} items")
    print(f"{'='*60}")
    for i, item in enumerate(items[:max_items]):
        vals = {f: item.get(f, "") for f in fields}
        print(f"  [{i+1}] {json.dumps(vals, ensure_ascii=False)}")
    if len(items) > max_items:
        print(f"  ... and {len(items) - max_items} more")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # ── LEVEL 1: Homepage → Brands ──
        print("\n>>> LEVEL 1: Crawling homepage...")
        snapshot = await get_snapshot(page, "https://www.catcar.info/")
        brands = await HomepageParser().parse(snapshot)
        show("BRANDS", brands, ["name", "region", "url"])

        # Show region breakdown
        regions = {}
        for b in brands:
            r = b.get("region", "?")
            regions[r] = regions.get(r, 0) + 1
        print(f"\n  Region breakdown: {json.dumps(regions)}")

        # Find VW
        vw = next((b for b in brands if "Volkswagen" in b.get("name", "")), None)
        if not vw:
            print("ERROR: Volkswagen not found!")
            await browser.close()
            return

        # ── LEVEL 2: VW → Models (Europe) + Market Tabs ──
        print(f"\n>>> LEVEL 2: Crawling VW models...")
        snapshot = await get_snapshot(page, vw["url"])
        parser = BrandModelsParser()
        models = await parser.parse(snapshot)
        market_tabs = parser.extract_market_tabs(snapshot)
        show("VW MODELS (default market)", models, ["code", "name", "market", "production_date"])

        print(f"\n  Market tabs found: {len(market_tabs)}")
        for tab in market_tabs:
            print(f"    - {tab['name']}")

        # Test a second market (USA)
        usa_tab = next((t for t in market_tabs if t["name"] == "USA"), None)
        if usa_tab:
            print(f"\n>>> LEVEL 2b: Crawling VW USA models...")
            snapshot_usa = await get_snapshot(page, usa_tab["url"])
            models_usa = await parser.parse(snapshot_usa)
            show("VW MODELS (USA)", models_usa, ["code", "name", "market", "production_date"])

        # Find Golf
        golf = next((m for m in models if "Golf" in m.get("name", "")), None)
        if not golf:
            print("ERROR: Golf not found! First 3 models:")
            for m in models[:3]:
                print(f"  {m}")
            await browser.close()
            return

        # ── LEVEL 3: Golf → Years ──
        print(f"\n>>> LEVEL 3: Crawling Golf years...")
        snapshot = await get_snapshot(page, golf["url"])
        years = await ModelYearsParser().parse(snapshot)
        show("GOLF YEARS", years, ["year", "restriction"])

        # Pick a year (prefer recent, fallback to last)
        target_year = next((y for y in years if y.get("year") == 2020), None)
        if not target_year:
            target_year = next((y for y in years if y.get("year") == 1997), years[-1] if years else None)
        if not target_year:
            print("ERROR: No years found!")
            await browser.close()
            return

        # ── LEVEL 4: Golf Year → Categories ──
        print(f"\n>>> LEVEL 4: Crawling Golf {target_year['year']} categories...")
        snapshot = await get_snapshot(page, target_year["url"])
        categories = await CategoriesParser().parse(snapshot)
        show("CATEGORIES", categories, ["name", "url"], max_items=10)

        if not categories:
            print("ERROR: No categories found!")
            print("Snapshot preview:")
            print(snapshot[:1000])
            await browser.close()
            return

        # Pick Engine category
        engine_cat = next((c for c in categories if "engine" in c.get("name", "").lower()), categories[0])

        # ── LEVEL 5: Engine → Subgroups ──
        print(f"\n>>> LEVEL 5: Crawling '{engine_cat['name']}' subgroups...")
        snapshot = await get_snapshot(page, engine_cat["url"])
        subgroups = await SubgroupsParser().parse(snapshot)
        show("SUBGROUPS", subgroups, ["ill_no", "description", "remark", "model_data"])

        if not subgroups:
            print("ERROR: No subgroups found!")
            print("Snapshot preview:")
            print(snapshot[:1000])
            await browser.close()
            return

        # Pick first subgroup
        sg = subgroups[0]

        # ── LEVEL 6: Subgroup → Parts ──
        print(f"\n>>> LEVEL 6: Crawling parts for '{sg['description']}'...")
        snapshot = await get_snapshot(page, sg["url"])
        parts = await PartsParser().parse(snapshot)
        show("PARTS", parts, ["position", "part_no", "description", "quantity", "model_data"])

        # ── SUMMARY ──
        print(f"\n{'='*60}")
        print(f"  DRY RUN SUMMARY")
        print(f"{'='*60}")
        print(f"  Level 1 - Brands:     {len(brands)} ({json.dumps(regions)})")
        print(f"  Level 2 - Models:     {len(models)} (VW Europe)")
        if usa_tab and models_usa:
            print(f"  Level 2b- Models:     {len(models_usa)} (VW USA)")
        print(f"  Market tabs:          {len(market_tabs)} ({', '.join(t['name'] for t in market_tabs)})")
        print(f"  Level 3 - Years:      {len(years)} (Golf)")
        print(f"  Level 4 - Categories: {len(categories)} (Golf {target_year['year']})")
        print(f"  Level 5 - Subgroups:  {len(subgroups)} ({engine_cat['name']})")
        print(f"  Level 6 - Parts:      {len(parts)} ({sg['description']})")
        print(f"{'='*60}")
        print(f"\n  ALL 6 LEVELS OK!" if all([brands, models, years, categories, subgroups, parts]) else "\n  SOME LEVELS FAILED!")

        await browser.close()


asyncio.run(main())
