"""Playwright browser pool for async page management."""
import asyncio
import structlog
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = structlog.get_logger()


class BrowserPool:
    """Manages a pool of Playwright browser contexts."""

    def __init__(self, pool_size: int = 2, headless: bool = True):
        self._pool_size = pool_size
        self._headless = headless
        self._playwright = None
        self._browser: Browser | None = None
        self._available: asyncio.Queue[BrowserContext] = asyncio.Queue()
        self._all_contexts: list[BrowserContext] = []

    async def start(self):
        """Initialize browser and create context pool."""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self._headless)
        for _ in range(self._pool_size):
            context = await self._browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            self._all_contexts.append(context)
            await self._available.put(context)
        logger.info("browser_pool.started", pool_size=self._pool_size)

    async def acquire(self) -> Page:
        """Get a page from an available context."""
        context = await self._available.get()
        page = await context.new_page()
        return page

    async def release(self, page: Page):
        """Return a page's context to the pool."""
        context = page.context
        await page.close()
        await self._available.put(context)

    async def stop(self):
        """Close all contexts and browser."""
        for ctx in self._all_contexts:
            await ctx.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("browser_pool.stopped")

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.stop()
