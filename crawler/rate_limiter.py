"""Rate limiting with exponential backoff for polite scraping."""
import asyncio
import random
from dataclasses import dataclass, field
import structlog

logger = structlog.get_logger()


@dataclass
class RateLimitConfig:
    min_delay: float = 2.0
    max_delay: float = 5.0
    max_concurrent: int = 1
    max_retries: int = 3
    backoff_base: float = 2.0


class RateLimiter:
    def __init__(self, config: RateLimitConfig | None = None):
        self.config = config or RateLimitConfig()
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent)
        self._last_request_time: float = 0

    async def wait(self):
        """Wait a random delay between min_delay and max_delay."""
        delay = random.uniform(self.config.min_delay, self.config.max_delay)
        now = asyncio.get_running_loop().time()
        elapsed = now - self._last_request_time
        if elapsed < delay:
            await asyncio.sleep(delay - elapsed)
        self._last_request_time = asyncio.get_running_loop().time()

    async def wait_backoff(self, retry_count: int):
        """Exponential backoff with jitter."""
        base_delay = self.config.backoff_base ** retry_count
        jitter = random.uniform(0, base_delay * 0.5)
        delay = base_delay + jitter
        logger.warning("rate_limiter.backoff", retry=retry_count, delay=f"{delay:.1f}s")
        await asyncio.sleep(delay)

    async def __aenter__(self):
        await self._semaphore.acquire()
        await self.wait()
        return self

    async def __aexit__(self, *args):
        self._semaphore.release()

    def should_retry(self, retry_count: int) -> bool:
        return retry_count < self.config.max_retries
