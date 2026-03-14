"""Crawl orchestrator - coordinates parsers, browser, state, and rate limiter."""
import asyncio
import structlog
from crawler.browser import BrowserPool
from crawler.rate_limiter import RateLimiter, RateLimitConfig
from crawler.state import CrawlStateManager
from crawler.utils import generate_content_hash
from crawler.parsers.homepage import HomepageParser
from crawler.parsers.brand_models import BrandModelsParser
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

    async def _save_data(self, session, level: int, validated_items: list[dict], queue_item) -> list[dict]:
        """Save parsed data to DB and return items with their DB IDs for child URL enqueuing.

        Uses select-then-update-or-insert (upsert) so re-runs are safe against
        unique-constraint violations.

        Returns list of dicts with 'id', 'url' and parent FK info for enqueuing children.
        """
        from sqlalchemy import select as sa_select
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
                        # Match NULL restriction as empty string for comparison
                        ModelYear.restriction == restriction,
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
                position = item.get("position")
                part_number = item.get("part_no", "")
                result = await session.execute(
                    sa_select(Part).where(
                        Part.subgroup_id == subgroup_id,
                        Part.part_number == part_number,
                        Part.position == position,
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
                    part = Part(
                        subgroup_id=subgroup_id,
                        position=position,
                        part_number=part_number,
                        description=item["description"],
                        remark=item.get("remark"),
                        quantity=item.get("quantity"),
                        model_data=item.get("model_data"),
                        content_hash=new_hash,
                    )
                    session.add(part)
            await session.flush()
            # No children for level 6

        return saved

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

        try:
            async with self.limiter:
                page = await self.browser.acquire()

                logger.info("crawl.navigating", url=queue_item.url[:80], level=queue_item.level)
                await page.goto(queue_item.url, wait_until="networkidle", timeout=30000)

                # Get page content for parsing and hashing
                content = await page.content()
                content_hash = generate_content_hash(content)

                # Parse the page
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

                    await self.state.mark_done(queue_item.id)
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise

                return True

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.error("crawl.failed", url=queue_item.url[:80], error=error_msg)
            await self.state.mark_failed(queue_item.id, error_msg)
            await self.state.session.commit()
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
