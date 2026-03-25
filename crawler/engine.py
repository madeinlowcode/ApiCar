"""Crawl orchestrator - coordinates parsers, browser, state, and rate limiter."""
import asyncio
import structlog
from crawler.browser import BrowserPool
from crawler.rate_limiter import RateLimiter, RateLimitConfig
from crawler.state import CrawlStateManager
from crawler.utils import generate_content_hash, ensure_english_url
from shared.models.crawl_queue import CrawlQueue
from crawler.parsers.homepage import HomepageParser
from crawler.parsers.brand_models import BrandModelsParser
from crawler.parsers.link_models import LinkModelsParser
from crawler.parsers.model_years import ModelYearsParser
from crawler.parsers.categories import CategoriesParser
from crawler.parsers.subgroups import SubgroupsParser
from crawler.parsers.parts import PartsParser

logger = structlog.get_logger()

LEVEL_PARSERS = {
    1: HomepageParser,
    2: BrandModelsParser,
    3: ModelYearsParser,
    4: CategoriesParser,
    5: SubgroupsParser,
    6: PartsParser,
}


class CrawlEngine:
    def __init__(
        self,
        browser_pool: BrowserPool,
        rate_limiter: RateLimiter,
        state: CrawlStateManager,
    ):
        self.browser = browser_pool
        self.limiter = rate_limiter
        self.state = state

    # Headings that indicate a gateway page (no models, just navigation links)
    GATEWAY_HEADINGS = {"Market", "Brand", "Assortment class"}

    # Headings that indicate a year-first page (deferred — not yet supported)
    YEAR_FIRST_HEADINGS = {"Year and region selection", "Year / Model"}

    @staticmethod
    def _detect_h1(content: str) -> str:
        """Extract the h1 heading text from ARIA snapshot content."""
        import re
        h1_match = re.search(r'heading "([^"]+)" \[level=1\]', content)
        return h1_match.group(1).strip() if h1_match else ""

    @staticmethod
    def _pick_level2_parser(content: str):
        """Auto-detect catalog type for level 2 and return the appropriate parser.

        Returns:
          - A parser instance for model pages
          - None for gateway pages (engine handles enqueuing)

        Detection based on h1 heading and page structure:
          - "Market" / "Brand" / "Assortment class" → None (gateway)
          - "Model" + table → BrandModelsParser (Toyota after market)
          - "Model" + links → LinkModelsParser (BMW after sub-brand, Ford)
          - "Catalog" → BrandModelsParser (VW-style)
          - Year-first headings → None (not yet supported)
        """
        import re
        h1 = CrawlEngine._detect_h1(content)

        # Gateway pages — no models, just navigation
        if h1 in CrawlEngine.GATEWAY_HEADINGS:
            return None

        # Year-first pages — not yet supported, skip
        if h1 in CrawlEngine.YEAR_FIRST_HEADINGS:
            return None

        # "Model" pages: check if table-based or link-based
        if h1 == "Model":
            # Table with column headers = BrandModelsParser (Toyota/Europe)
            if re.search(r'columnheader "(?:Catalog|Code|Model)"', content):
                return BrandModelsParser()
            # Year list (Honda-style) — not yet supported
            if re.search(r'link "\d{4}":\s*\n\s+- /url:', content):
                return None
            return LinkModelsParser()

        # "Catalog" or default
        return BrandModelsParser()

    @staticmethod
    def _extract_gateway_links(content: str, queue_item) -> list[dict]:
        """Extract navigation links from gateway pages (market, sub-brand, class).

        Returns list of dicts with 'url' and 'parent_brand_id' for enqueuing as level 2.
        """
        import re
        from crawler.utils import ensure_english_url

        links = []
        seen_urls = set()
        brand_id = queue_item.parent_brand_id

        # Skip patterns
        skip_names = {
            "Русский", "English", "Connect CatCar catalogs", "Connect catalogs",
            "Check", "Motorcycle", "Motorcycle Classic",
        }
        # Skip URLs that are clearly not catalog pages
        skip_url_patterns = {"/en/", "/en?"}

        lines = content.split('\n')
        n = len(lines)
        link_re = re.compile(r'\s*- link "([^"]+)"(?:\s+\[.*?\])*:')
        url_re = re.compile(r'\s+- /url:\s+(https?://\S+)')

        for i in range(n):
            m = link_re.match(lines[i])
            if not m:
                continue

            name = m.group(1).strip()

            # Skip UI links and non-catalog links
            if name in skip_names:
                continue
            if len(name) < 2:
                continue

            # Find URL in next few lines
            for j in range(i + 1, min(i + 5, n)):
                url_m = url_re.match(lines[j])
                if url_m and 'catcar.info' in url_m.group(1):
                    raw_url = url_m.group(1).strip()
                    # Skip homepage and non-catalog URLs
                    if any(p in raw_url for p in skip_url_patterns):
                        break
                    url = ensure_english_url(raw_url)
                    if url not in seen_urls:
                        seen_urls.add(url)
                        links.append({
                            "url": url,
                            "parent_brand_id": brand_id,
                        })
                    break

        return links

    async def _handle_no_year_table_categories(self, content: str, queue_item, nav_url: str):
        """Handle Mercedes-style category pages with table format [№, Name].

        Mercedes models go directly to "Main group" page (no year selection).
        Categories are in a table, not image links like Ford.
        We create a synthetic model_year and parse categories from the table.
        """
        import re
        from sqlalchemy import select as sa_select
        from shared.models import ModelYear, PartsCategory

        session = self.state.session
        model_id = queue_item.parent_model_id

        # Create synthetic model_year if not exists
        result = await session.execute(
            sa_select(ModelYear).where(
                ModelYear.model_id == model_id,
                ModelYear.year == 0,
            )
        )
        my = result.scalar_one_or_none()
        if not my:
            my = ModelYear(
                model_id=model_id,
                year=0,
                restriction="no-year-selection",
                catalog_url=nav_url,
            )
            session.add(my)
            await session.flush()

        # Parse table categories: rows with [№, Name] where Name has a link
        lines = content.split('\n')
        n = len(lines)
        row_re = re.compile(r'^\s+- row "(.+?)"(?:\s+\[.*?\])*:')
        cell_re = re.compile(r'^\s+- cell "([^"]*)"(?:\s+\[.*?\])*')
        link_re = re.compile(r'^\s+- link "([^"]+)"(?:\s+\[.*?\])*:')
        url_re = re.compile(r'^\s+- /url:\s+(https?://\S+)')

        categories = []
        for i in range(n):
            rm = row_re.match(lines[i])
            if not rm:
                continue
            row_text = rm.group(1)
            # Skip header
            if '№' in row_text and 'Name' in row_text:
                continue

            # Find link and URL within this row
            cat_name = None
            cat_url = None
            for j in range(i + 1, min(i + 10, n)):
                if j >= n:
                    break
                lm = link_re.match(lines[j])
                if lm and cat_name is None:
                    cat_name = lm.group(1).strip()
                um = url_re.match(lines[j])
                if um and 'catcar.info' in um.group(1):
                    cat_url = um.group(1).strip()
                    break
                if row_re.match(lines[j]):
                    break

            if cat_name and cat_url:
                categories.append({"name": cat_name, "url": ensure_english_url(cat_url)})

        logger.info(
            "crawl.mercedes_categories",
            url=queue_item.url[:80],
            model_id=model_id,
            categories=len(categories),
        )

        # Save categories
        saved = []
        for idx, item in enumerate(categories):
            result = await session.execute(
                sa_select(PartsCategory).where(
                    PartsCategory.model_year_id == my.id,
                    PartsCategory.category_index == idx,
                )
            )
            cat = result.scalar_one_or_none()
            if cat:
                cat.name = item["name"]
                cat.catalog_url = item["url"]
            else:
                cat = PartsCategory(
                    model_year_id=my.id,
                    category_index=idx,
                    name=item["name"],
                    catalog_url=item["url"],
                )
                session.add(cat)
            await session.flush()
            saved.append({"id": cat.id, "url": item["url"], "parent_category_id": cat.id})

        # Enqueue subgroup URLs (level 5)
        if saved:
            await self.state.enqueue_urls(queue_item.job_id, saved, 5)

        await self.state.mark_done(queue_item.id)
        await session.commit()
        return None

    async def _handle_submodel_page(self, content: str, queue_item, nav_url: str):
        """Handle brands with a sub-model selection page (Mitsubishi).

        The page shows a table of sub-models [№, Model, Description] with links.
        We create synthetic model_year entries (year=0) for each sub-model
        and enqueue their URLs for further processing at the next level.
        """
        import re
        from sqlalchemy import select as sa_select
        from shared.models import ModelYear

        session = self.state.session
        model_id = queue_item.parent_model_id

        # Extract sub-models from table rows
        lines = content.split('\n')
        n = len(lines)
        row_re = re.compile(r'^\s+- row "(.+?)"(?:\s+\[.*?\])*:')
        link_re = re.compile(r'^\s+- link "([^"]+)"(?:\s+\[.*?\])*:')
        url_re = re.compile(r'^\s+- /url:\s+(https?://\S+)')

        submodels = []
        for i in range(n):
            rm = row_re.match(lines[i])
            if not rm:
                continue
            row_text = rm.group(1)
            # Skip header
            if 'Model' in row_text and 'Description' in row_text:
                continue

            # Find link and URL within this row
            link_name = None
            link_url = None
            for j in range(i + 1, min(i + 15, n)):
                if j >= n:
                    break
                lm = link_re.match(lines[j])
                if lm and link_name is None:
                    link_name = lm.group(1).strip()
                um = url_re.match(lines[j])
                if um and 'catcar.info' in um.group(1):
                    link_url = um.group(1).strip()
                    break
                # Stop at next row
                if row_re.match(lines[j]):
                    break

            if link_name and link_url:
                # Use row text as description (e.g., "1 Z11A 3000/2WD")
                submodels.append({
                    "code": link_name,
                    "description": row_text,
                    "url": ensure_english_url(link_url),
                })

        logger.info(
            "crawl.submodel_page",
            url=queue_item.url[:80],
            model_id=model_id,
            submodels=len(submodels),
        )

        # Create model_year entries for each sub-model
        saved = []
        for sm in submodels:
            restriction = f"{sm['code']} {sm['description']}"[:200]
            result = await session.execute(
                sa_select(ModelYear).where(
                    ModelYear.model_id == model_id,
                    ModelYear.year == 0,
                    ModelYear.restriction == restriction,
                )
            )
            my = result.scalar_one_or_none()
            if not my:
                my = ModelYear(
                    model_id=model_id,
                    year=0,
                    restriction=restriction,
                    catalog_url=sm["url"],
                )
                session.add(my)
            else:
                my.catalog_url = sm["url"]
            await session.flush()
            saved.append({
                "id": my.id,
                "url": sm["url"],
                "parent_year_id": my.id,
            })

        # Enqueue sub-model URLs as level 4 (categories)
        # The sub-model page likely leads to "Main groups" or directly to categories
        if saved:
            await self.state.enqueue_urls(queue_item.job_id, saved, 4)
            logger.info(
                "crawl.submodel_enqueued",
                count=len(saved),
                model_id=model_id,
            )

        await self.state.mark_done(queue_item.id)
        await session.commit()
        return None

    async def _handle_no_year_page(self, content: str, queue_item, nav_url: str):
        """Handle brands that skip year selection and go directly to categories.

        Ford, Opel, Renault etc. go: Model → Main groups (categories).
        We create a synthetic model_year (year=0) and parse categories at level 4.
        """
        from sqlalchemy import select as sa_select
        from shared.models import ModelYear, Model

        session = self.state.session
        model_id = queue_item.parent_model_id

        # Create synthetic model_year if not exists
        result = await session.execute(
            sa_select(ModelYear).where(
                ModelYear.model_id == model_id,
                ModelYear.year == 0,
            )
        )
        my = result.scalar_one_or_none()
        if not my:
            my = ModelYear(
                model_id=model_id,
                year=0,
                restriction="no-year-selection",
                catalog_url=nav_url,
            )
            session.add(my)
            await session.flush()

        # Parse categories from this page
        categories_parser = CategoriesParser()
        raw_cats = await categories_parser.parse(content)
        validator = categories_parser.get_validator()

        validated = []
        for item in raw_cats:
            try:
                v = validator(**item)
                validated.append(v.model_dump())
            except Exception as e:
                logger.warning("crawl.validation_failed", error=str(e), item=item)

        logger.info(
            "crawl.no_year_redirect",
            url=queue_item.url[:80],
            model_id=model_id,
            categories=len(validated),
        )

        # Save categories as level 4
        from shared.models import PartsCategory
        saved = []
        for idx, item in enumerate(validated):
            result = await session.execute(
                sa_select(PartsCategory).where(
                    PartsCategory.model_year_id == my.id,
                    PartsCategory.category_index == idx,
                )
            )
            cat = result.scalar_one_or_none()
            if cat:
                cat.name = item["name"]
                cat.catalog_url = item["url"]
            else:
                cat = PartsCategory(
                    model_year_id=my.id,
                    category_index=idx,
                    name=item["name"],
                    catalog_url=item["url"],
                )
                session.add(cat)
            await session.flush()
            saved.append({"id": cat.id, "url": item["url"], "parent_category_id": cat.id})

        # Enqueue subgroup URLs (level 5)
        if saved:
            await self.state.enqueue_urls(
                queue_item.job_id,
                saved,
                5,  # subgroups level
            )
            logger.info(
                "crawl.no_year_categories_enqueued",
                count=len(saved),
                model_id=model_id,
            )

        await self.state.mark_done(queue_item.id)
        await session.commit()
        return None  # Signal that we handled everything

    async def _save_data(self, session, level: int, validated_items: list[dict], queue_item) -> list[dict]:
        """Save parsed data to DB and return items with their DB IDs for child URL enqueuing.

        Uses select-then-update-or-insert (upsert) so re-runs are safe against
        unique-constraint violations.

        Returns list of dicts with 'id', 'url' and parent FK info for enqueuing children.
        """
        from sqlalchemy import select as sa_select, func
        from shared.models import Brand, Market, Model, ModelYear, PartsCategory, Subgroup, Part
        from crawler.utils import slugify

        saved = []

        if level == 1:
            # Upsert brands — unique key: slug
            for item in validated_items:
                slug = slugify(item["name"])
                result = await session.execute(
                    sa_select(Brand).where(Brand.slug == slug)
                )
                brand = result.scalar_one_or_none()
                if brand:
                    brand.name = item["name"]
                    brand.catalog_url = item["url"]
                    brand.logo_url = item.get("logo_url")
                else:
                    brand = Brand(
                        name=item["name"],
                        slug=slug,
                        region=item.get("region", "Europe"),
                        catalog_path=item.get("catalog_path", "/"),
                        catalog_url=item["url"],
                        logo_url=item.get("logo_url"),
                    )
                    session.add(brand)
                await session.flush()
                saved.append({"id": brand.id, "url": item["url"], "parent_brand_id": brand.id})

        elif level == 2:
            # Upsert markets (unique: brand_id + name) and models (unique: brand_id + market_id + catalog_code)
            brand_id = queue_item.parent_brand_id
            for item in validated_items:
                market_name = item.get("market", "General")
                result = await session.execute(
                    sa_select(Market).where(Market.brand_id == brand_id, Market.name == market_name)
                )
                market = result.scalar_one_or_none()
                if market:
                    market.catalog_url = item.get("url", "")
                else:
                    market = Market(brand_id=brand_id, name=market_name, catalog_url=item.get("url", ""))
                    session.add(market)
                    await session.flush()

                catalog_code = item.get("code", "")
                result = await session.execute(
                    sa_select(Model).where(
                        Model.brand_id == brand_id,
                        Model.market_id == market.id,
                        Model.catalog_code == catalog_code,
                    )
                )
                model = result.scalar_one_or_none()
                if model:
                    model.name = item["name"]
                    model.production_date = item.get("production_date")
                    model.production_codes = item.get("production_codes")
                    model.catalog_url = item["url"]
                else:
                    model = Model(
                        brand_id=brand_id,
                        market_id=market.id,
                        catalog_code=catalog_code,
                        name=item["name"],
                        production_date=item.get("production_date"),
                        production_codes=item.get("production_codes"),
                        catalog_url=item["url"],
                    )
                    session.add(model)
                await session.flush()
                saved.append({"id": model.id, "url": item["url"], "parent_model_id": model.id})

        elif level == 3:
            # Upsert model years — unique index: (model_id, year, COALESCE(restriction, ''))
            model_id = queue_item.parent_model_id
            for item in validated_items:
                restriction = item.get("restriction")
                result = await session.execute(
                    sa_select(ModelYear).where(
                        ModelYear.model_id == model_id,
                        ModelYear.year == item["year"],
                        # Match NULL restriction as empty string to align with COALESCE index
                        func.coalesce(ModelYear.restriction, '') == (restriction or ''),
                    )
                )
                my = result.scalar_one_or_none()
                if my:
                    my.catalog_url = item["url"]
                else:
                    my = ModelYear(
                        model_id=model_id,
                        year=item["year"],
                        restriction=restriction,
                        catalog_url=item["url"],
                    )
                    session.add(my)
                await session.flush()
                saved.append({"id": my.id, "url": item["url"], "parent_year_id": my.id})

        elif level == 4:
            # Upsert categories — unique: (model_year_id, category_index)
            year_id = queue_item.parent_year_id
            for idx, item in enumerate(validated_items):
                result = await session.execute(
                    sa_select(PartsCategory).where(
                        PartsCategory.model_year_id == year_id,
                        PartsCategory.category_index == idx,
                    )
                )
                cat = result.scalar_one_or_none()
                if cat:
                    cat.name = item["name"]
                    cat.catalog_url = item["url"]
                else:
                    cat = PartsCategory(
                        model_year_id=year_id,
                        category_index=idx,
                        name=item["name"],
                        catalog_url=item["url"],
                    )
                    session.add(cat)
                await session.flush()
                saved.append({"id": cat.id, "url": item["url"], "parent_category_id": cat.id})

        elif level == 5:
            # Upsert subgroups — unique: (category_id, illustration_number)
            category_id = queue_item.parent_category_id
            for item in validated_items:
                illustration_number = item.get("ill_no", "")
                result = await session.execute(
                    sa_select(Subgroup).where(
                        Subgroup.category_id == category_id,
                        Subgroup.illustration_number == illustration_number,
                    )
                )
                sg = result.scalar_one_or_none()
                if sg:
                    sg.main_group = item.get("main_group", "")
                    sg.description = item["description"]
                    sg.remark = item.get("remark")
                    sg.model_data = item.get("model_data")
                    sg.catalog_url = item["url"]
                else:
                    sg = Subgroup(
                        category_id=category_id,
                        main_group=item.get("main_group", ""),
                        illustration_number=illustration_number,
                        description=item["description"],
                        remark=item.get("remark"),
                        model_data=item.get("model_data"),
                        catalog_url=item["url"],
                    )
                    session.add(sg)
                await session.flush()
                saved.append({"id": sg.id, "url": item["url"], "parent_subgroup_id": sg.id})

        elif level == 6:
            # Upsert parts (leaf level — no children to enqueue)
            # unique index: (subgroup_id, part_number, COALESCE(position, ''))
            # Only update if content_hash changed (or was absent).
            subgroup_id = queue_item.parent_subgroup_id
            for item in validated_items:
                position = str(item.get("position", "")) or None
                part_number = str(item.get("part_no", ""))
                result = await session.execute(
                    sa_select(Part).where(
                        Part.subgroup_id == subgroup_id,
                        Part.part_number == part_number,
                        func.coalesce(Part.position, '') == (position or ''),
                    )
                )
                part = result.scalar_one_or_none()
                new_hash = item.get("content_hash")
                if part:
                    if part.content_hash != new_hash:
                        part.description = item["description"]
                        part.remark = item.get("remark")
                        part.quantity = item.get("quantity")
                        part.model_data = item.get("model_data")
                        part.content_hash = new_hash
                else:
                    qty = item.get("quantity")
                    part = Part(
                        subgroup_id=subgroup_id,
                        position=position,
                        part_number=part_number,
                        description=item["description"],
                        remark=item.get("remark"),
                        quantity=str(qty) if qty is not None else None,
                        model_data=item.get("model_data"),
                        content_hash=new_hash,
                    )
                    session.add(part)
            await session.flush()
            # No children for level 6

        return saved

    async def _enqueue_market_tabs(self, session, content: str, queue_item):
        """Extract market tab URLs from a brand page and enqueue unseen ones.

        When visiting a brand page (level 2), the page shows models for one market
        and has tabs linking to other markets (Europe, USA, Brazil, etc.).
        We enqueue those extra market URLs as additional level 2 items so the
        crawler processes all markets.
        """
        from sqlalchemy import select as sa_select

        # Try both parser types for market tabs
        tabs = BrandModelsParser().extract_market_tabs(content)
        if not tabs:
            tabs = LinkModelsParser().extract_market_tabs(content)
        if not tabs:
            return

        # Find URLs already in the queue for this job at level 2
        result = await session.execute(
            sa_select(CrawlQueue.url).where(
                CrawlQueue.job_id == queue_item.job_id,
                CrawlQueue.level == 2,
            )
        )
        existing_urls = {row[0] for row in result.all()}

        # Also exclude the current page URL (prevents infinite loops like Mazda USA)
        current_url = ensure_english_url(queue_item.url)
        existing_urls.add(current_url)
        existing_urls.add(queue_item.url)

        brand_id = queue_item.parent_brand_id
        new_tabs = []
        for tab in tabs:
            url = ensure_english_url(tab["url"])
            if url not in existing_urls and tab["url"] not in existing_urls:
                new_tabs.append({
                    "url": url,
                    "parent_brand_id": brand_id,
                })

        if new_tabs:
            await self.state.enqueue_urls(queue_item.job_id, new_tabs, 2)
            logger.info(
                "crawl.market_tabs_enqueued",
                count=len(new_tabs),
                brand_id=brand_id,
                markets=[t["name"] for t in tabs],
            )

    async def process_url(self, queue_item) -> bool:
        """Process a single URL from the queue.

        Returns True if successful, False if failed.
        """
        parser_cls = LEVEL_PARSERS.get(queue_item.level)
        if not parser_cls:
            logger.error("crawl.unknown_level", level=queue_item.level)
            await self.state.mark_failed(queue_item.id, f"Unknown level: {queue_item.level}")
            return False

        parser = parser_cls()
        page = None
        # Capture IDs before try block to avoid MissingGreenlet on lazy load after rollback
        item_id = queue_item.id
        item_url = queue_item.url
        item_level = queue_item.level
        item_job_id = queue_item.job_id

        try:
            async with self.limiter:
                page = await self.browser.acquire()

                nav_url = ensure_english_url(queue_item.url)
                logger.info("crawl.navigating", url=nav_url[:80], level=queue_item.level)
                await page.goto(nav_url, wait_until="domcontentloaded", timeout=60000)
                # Wait extra for JS rendering
                await page.wait_for_timeout(5000)

                # Get ARIA snapshot for parsing (parsers expect this YAML-like format)
                content = await page.locator("body").aria_snapshot()
                content_hash = generate_content_hash(content)

                # Level 2: auto-detect catalog type and pick correct parser
                if queue_item.level == 2:
                    parser = self._pick_level2_parser(content)

                    if parser is None:
                        # Gateway page (market/sub-brand/class selection)
                        # Extract links and enqueue as new level 2 items
                        h1 = self._detect_h1(content)
                        gateway_links = self._extract_gateway_links(content, queue_item)

                        session = self.state.session
                        if gateway_links:
                            # Deduplicate against existing queue URLs
                            from sqlalchemy import select as sa_select
                            result = await session.execute(
                                sa_select(CrawlQueue.url).where(
                                    CrawlQueue.job_id == queue_item.job_id,
                                    CrawlQueue.level == 2,
                                )
                            )
                            existing_urls = {row[0] for row in result.all()}
                            new_links = [
                                l for l in gateway_links
                                if l["url"] not in existing_urls
                            ]

                            if new_links:
                                await self.state.enqueue_urls(
                                    queue_item.job_id, new_links, 2
                                )
                                logger.info(
                                    "crawl.gateway_enqueued",
                                    h1=h1,
                                    count=len(new_links),
                                    url=queue_item.url[:60],
                                )
                        else:
                            logger.warning(
                                "crawl.gateway_no_links",
                                h1=h1,
                                url=queue_item.url[:60],
                            )

                        # Mark done and commit
                        await self.state.mark_done(queue_item.id)
                        await session.commit()
                        return True

                    raw_data = await parser.parse(content, page_url=nav_url)

                # Level 3: detect page type — some brands skip year selection
                elif queue_item.level == 3:
                    import re as _re
                    h1 = self._detect_h1(content)

                    if h1 in ("Main groups", "Hauptgruppen"):
                        # Ford-style: no year selection, go directly to categories (link+img)
                        result = await self._handle_no_year_page(
                            content, queue_item, nav_url
                        )
                        if result is None:
                            return True
                        raw_data = []

                    elif h1 in ("Main group",):
                        # Mercedes-style: no year selection, categories in table [№, Name]
                        result = await self._handle_no_year_table_categories(
                            content, queue_item, nav_url
                        )
                        if result is None:
                            return True
                        raw_data = []

                    elif h1 == "Model" and _re.search(
                        r'columnheader "(?:№|Model|Description)"', content
                    ):
                        # Mitsubishi-style: sub-model selection table
                        # Parse sub-models as synthetic model_years (year=0)
                        result = await self._handle_submodel_page(
                            content, queue_item, nav_url
                        )
                        if result is None:
                            return True
                        raw_data = []

                    else:
                        raw_data = await parser.parse(content)
                else:
                    raw_data = await parser.parse(content)

                # Validate each item
                validator = parser.get_validator()
                validated = []
                for item in raw_data:
                    try:
                        validated_item = validator(**item)
                        validated.append(validated_item.model_dump())
                    except Exception as e:
                        logger.warning("crawl.validation_failed", error=str(e), item=item)

                logger.info(
                    "crawl.parsed",
                    url=queue_item.url[:80],
                    level=queue_item.level,
                    items=len(validated),
                    skipped=len(raw_data) - len(validated),
                )

                # Save data, enqueue children, and mark done — all on the same session
                # so the entire cycle is one atomic commit.
                session = self.state.session
                try:
                    saved_items = await self._save_data(session, queue_item.level, validated, queue_item)

                    # Enqueue child URLs for non-leaf levels
                    if queue_item.level < 6 and saved_items:
                        child_level = queue_item.level + 1
                        child_urls = []
                        for item in saved_items:
                            url_entry = {"url": item["url"]}
                            # Copy parent FK from the saved item
                            for key in [
                                "parent_brand_id",
                                "parent_model_id",
                                "parent_year_id",
                                "parent_category_id",
                                "parent_subgroup_id",
                            ]:
                                if key in item:
                                    url_entry[key] = item[key]
                            child_urls.append(url_entry)

                        await self.state.enqueue_urls(queue_item.job_id, child_urls, child_level)
                        logger.info(
                            "crawl.children_enqueued",
                            count=len(child_urls),
                            level=child_level,
                        )

                    # For level 2 (brand models): enqueue other market tab URLs
                    # so all markets are crawled, not just the default one
                    if queue_item.level == 2:
                        await self._enqueue_market_tabs(
                            session, content, queue_item
                        )

                    await self.state.mark_done(queue_item.id)
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise

                return True

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)[:500]}"
            logger.error("crawl.failed", queue_id=item_id, error=error_msg[:200])
            try:
                await self.state.mark_failed(item_id, error_msg[:500])
                await self.state.session.commit()
            except Exception:
                await self.state.session.rollback()
            return False
        finally:
            if page:
                await self.browser.release(page)

    async def run_job(self, job_id: int):
        """Process all pending URLs for a job."""
        await self.state.start_job(job_id)
        logger.info("crawl.job_started", job_id=job_id)

        try:
            while True:
                item = await self.state.claim_next(job_id)
                if item is None:
                    # Check if there are still processing items
                    progress = await self.state.get_progress(job_id)
                    if progress["processing"] == 0 and progress["pending"] == 0:
                        break
                    await asyncio.sleep(2)  # Avoid CPU spin while waiting for workers
                    continue

                await self.process_url(item)

            await self.state.complete_job(job_id)
            logger.info("crawl.job_completed", job_id=job_id)
        except Exception as e:
            await self.state.fail_job(job_id, str(e))
            logger.error("crawl.job_failed", job_id=job_id, error=str(e))
            raise
