"""Retry decorator with exponential backoff for external API calls.

Each call site picks which exceptions to retry on, since httpx and
google-generativeai (google.api_core) raise different types.

Example:

    from app.utils.retry import with_retry, GEMINI_RETRY_EXCEPTIONS

    @with_retry(max_retries=3, exceptions=GEMINI_RETRY_EXCEPTIONS)
    async def call_gemini(...): ...
"""

from __future__ import annotations

import asyncio
import functools
import logging
import random
from typing import Awaitable, Callable, Tuple, Type

import httpx

logger = logging.getLogger(__name__)


HTTP_RETRY_EXCEPTIONS: Tuple[Type[BaseException], ...] = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.ReadError,
    httpx.RemoteProtocolError,
)


def _gemini_retry_exceptions() -> Tuple[Type[BaseException], ...]:
    """Build the Gemini retry tuple lazily — google.api_core is optional."""
    extras: list[Type[BaseException]] = []
    try:
        from google.api_core import exceptions as gax  # type: ignore
        extras.extend([
            gax.ResourceExhausted,    # 429
            gax.ServiceUnavailable,   # 503
            gax.DeadlineExceeded,     # timeout
            gax.InternalServerError,  # 500
            gax.GatewayTimeout,       # 504
        ])
    except ImportError:
        pass
    return HTTP_RETRY_EXCEPTIONS + tuple(extras)


GEMINI_RETRY_EXCEPTIONS = _gemini_retry_exceptions()


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: Tuple[Type[BaseException], ...] = HTTP_RETRY_EXCEPTIONS,
):
    """Retry an async function with exponential backoff + jitter.

    A 5xx HTTPStatusError or a 429 is also retried (handled inline below);
    other 4xx responses are not retried because they signal a client bug.
    """

    def decorator(func: Callable[..., Awaitable]):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exc: BaseException | None = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except httpx.HTTPStatusError as e:
                    code = e.response.status_code
                    retryable = code == 429 or 500 <= code < 600
                    if not retryable or attempt == max_retries:
                        raise
                    last_exc = e
                except exceptions as e:
                    if attempt == max_retries:
                        logger.error(
                            "%s exhausted after %d attempts: %s",
                            func.__name__, max_retries + 1, e,
                        )
                        raise
                    last_exc = e

                delay = min(base_delay * (2 ** attempt), max_delay)
                # Jitter so concurrent retries don't thunder against the upstream
                delay *= 0.5 + random.random()
                logger.warning(
                    "%s attempt %d failed (%s); retrying in %.1fs",
                    func.__name__, attempt + 1, type(last_exc).__name__, delay,
                )
                await asyncio.sleep(delay)

            assert last_exc is not None  # unreachable
            raise last_exc

        return wrapper

    return decorator
