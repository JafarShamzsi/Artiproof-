"""
Async rate limiter — shared across all scrapers to respect API limits.
"""

import asyncio
import time
from collections import defaultdict


class RateLimiter:
    """Simple per-source token-bucket rate limiter."""

    def __init__(self):
        self.limits = {
            "google_scholar": {"requests_per_second": 0.2},  # 1 req / 5s (gentle scraping)
            "semantic_scholar": {"requests_per_second": 10},  # 100 req/5min free tier
            "scopus": {"requests_per_second": 3},
            "crossref": {"requests_per_second": 5},
        }
        self._last_request: dict[str, float] = defaultdict(float)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def acquire(self, source: str):
        """Wait until we can make a request to this source."""
        async with self._locks[source]:
            limit = self.limits.get(source, {"requests_per_second": 1})
            min_interval = 1.0 / limit["requests_per_second"]
            elapsed = time.monotonic() - self._last_request[source]
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)
            self._last_request[source] = time.monotonic()


rate_limiter = RateLimiter()
