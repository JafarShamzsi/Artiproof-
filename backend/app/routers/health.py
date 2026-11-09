"""Public infrastructure readiness; external provider probes are disabled.

DB and Redis run concurrently under individual two-second deadlines. External
services are explicitly not tested, even when server credentials are configured.
An infrastructure-only ``ok`` is not a provider-availability assertion.
The shallow ``/api/health`` in ``main.py`` remains unchanged.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/health", tags=["Health"])


_PROBE_TIMEOUT_S = 2.0


async def _probe(
    name: str,
    coro_factory: Callable[[], Coroutine[Any, Any, Any]],
) -> tuple[str, str]:
    """Run a probe under the global timeout; return (name, status_string).

    A probe that raises (including asyncio.TimeoutError) yields a string
    like ``"error: TimeoutError"`` so the response stays JSON-serialisable
    no matter what blew up underneath.
    """
    try:
        await asyncio.wait_for(coro_factory(), timeout=_PROBE_TIMEOUT_S)
        return name, "ok"
    except asyncio.TimeoutError:
        return name, "error: TimeoutError"
    except Exception as e:  # broad on purpose — every fail mode reports out
        return name, f"error: {type(e).__name__}"


# ─── Individual probes ─────────────────────────────────────────────────────


async def _probe_db(db: AsyncSession) -> None:
    await db.execute(text("SELECT 1"))


async def _probe_redis() -> None:
    # Lazy import — redis is a runtime dep but not always imported on
    # boot if Celery is disabled.
    from redis.asyncio import from_url  # type: ignore

    r = from_url(settings.REDIS_URL, socket_connect_timeout=1)
    try:
        await r.ping()
    finally:
        await r.aclose()


# ─── Route ─────────────────────────────────────────────────────────────────


@router.get("/deep")
async def deep_health(response: Response, db: AsyncSession = Depends(get_db)) -> dict:
    """Return 503 for DB/Redis failure; providers remain disabled/not tested."""
    results = await asyncio.gather(
        _probe("database", lambda: _probe_db(db)),
        _probe("redis", _probe_redis),
        return_exceptions=False,  # _probe already swallows
    )
    services: dict[str, str] = dict(results)
    ok = all(status == "ok" for status in services.values())
    services.update({name: "disabled: not tested" for name in (
        "gemini", "crossref", "openalex",
    )})

    if not ok:
        response.status_code = 503
        # ERROR-level so Sentry picks the aggregate up; the per-probe
        # exception types are already in the body.
        logger.error("deep health failed: %s", services)

    return {
        "ok": ok,
        "services": services,
        "service": "artiproof-api",
    }
