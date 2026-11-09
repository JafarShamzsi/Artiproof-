"""Deep readiness probes — opt-in route for an external uptime monitor.

``/api/health`` (in ``main.py``) stays shallow: DB + Redis only, because
Railway's readiness gate fires it on every restart and a single slow
Gemini blip shouldn't flap the API into restart loops.

``/api/health/deep`` is the **opt-in** probe. It hits every external
dependency in parallel with a tight 2-second timeout each — DB, Redis,
Gemini, CrossRef, OpenAlex — and surfaces ``503`` if any one fails.
Used by an external uptime monitor / on-call dashboard. Not in the
Railway probe path.

Each probe is wrapped to convert the result into one of:
  - ``"ok"`` — succeeded under timeout.
  - ``"error: <ExceptionName>"`` — failed (timeout, 4xx, network).

The wrapper keeps individual probe failures from poisoning the
``asyncio.gather`` (we use ``return_exceptions=True``) so the response
shape stays predictable even when half of the dependencies are down.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine

import httpx
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


async def _probe_gemini() -> None:
    # Verify the key is set AND a cheap Gemini call succeeds. ``models.list``
    # is the lightest call the SDK supports — no token cost, no quota burn.
    # If the key is empty we report "skipped" via the wrapper's exception
    # path rather than passing silently.
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set")
    try:
        from google import genai  # type: ignore

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        # The SDK's list endpoint is sync-only; offload to thread.
        await asyncio.to_thread(lambda: list(client.models.list()))
    except ImportError as e:
        raise RuntimeError(f"google-genai not installed: {e}") from e


async def _probe_crossref() -> None:
    async with httpx.AsyncClient(timeout=_PROBE_TIMEOUT_S) as client:
        resp = await client.get(
            "https://api.crossref.org/works",
            params={"rows": 1},
            headers={"User-Agent": "ArtiProof Health/1.0"},
        )
        resp.raise_for_status()


async def _probe_openalex() -> None:
    async with httpx.AsyncClient(timeout=_PROBE_TIMEOUT_S) as client:
        resp = await client.get(
            "https://api.openalex.org/works",
            params={"per_page": 1},
            headers={"User-Agent": "ArtiProof Health/1.0"},
        )
        resp.raise_for_status()


# ─── Route ─────────────────────────────────────────────────────────────────


@router.get("/deep")
async def deep_health(response: Response, db: AsyncSession = Depends(get_db)) -> dict:
    """Run every external probe in parallel; return 503 if any fails.

    Probes run with ``return_exceptions=True`` so a single timeout doesn't
    short-circuit the whole gather; each probe's status is surfaced in
    ``services``. The aggregate ``ok`` flag flips to False as soon as any
    probe reports a non-``"ok"`` string.
    """
    results = await asyncio.gather(
        _probe("database", lambda: _probe_db(db)),
        _probe("redis", _probe_redis),
        _probe("gemini", _probe_gemini),
        _probe("crossref", _probe_crossref),
        _probe("openalex", _probe_openalex),
        return_exceptions=False,  # _probe already swallows
    )
    services: dict[str, str] = dict(results)
    ok = all(status == "ok" for status in services.values())

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
