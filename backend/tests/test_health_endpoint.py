"""Health endpoint sanity tests.

The simple ``/health`` route doesn't need a DB or lifespan — call the
handler directly. ``/api/health`` *does* touch the DB and Redis; for that
we override ``get_db`` with a stub session and gracefully accept the Redis
check failing (no real Redis in unit-test env).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_simple_health_returns_ok():
    """`/health` is a static dict — no deps. Just confirm the shape."""
    from app.main import health_check

    out = await health_check()
    assert out["status"] == "healthy"
    assert out["service"] == "artiproof-api"
    assert out["version"]


def _stub_response():
    """Cheap stand-in for fastapi.Response — only ``status_code`` is read
    by ``detailed_health``."""
    from types import SimpleNamespace

    return SimpleNamespace(status_code=200)


@pytest.mark.asyncio
async def test_detailed_health_with_stub_db():
    """`/api/health` reports services dict; DB stubbed via injection."""
    from app.main import detailed_health

    stub_session = AsyncMock()
    # `await session.execute(text("SELECT 1"))` should resolve to anything
    stub_session.execute.return_value = None

    response = _stub_response()
    out = await detailed_health(response=response, db=stub_session)

    assert "status" in out
    assert "services" in out
    assert out["services"]["database"] == "ok"
    # Per-integration configuration state is intentionally NOT in the public
    # response anymore (information disclosure). Only DB + Redis show.
    assert "gemini" not in out["services"]
    assert "google_factcheck" not in out["services"]
    # Redis is unlikely to be running in unit-test env — accept either result
    assert out["services"]["redis"] in {"ok"} or out["services"]["redis"].startswith("error")


@pytest.mark.asyncio
async def test_detailed_health_marks_degraded_on_db_failure():
    """If the DB SELECT raises, status flips to 'degraded' AND we set a 503
    so monitoring tools (and Railway's optional readiness gate) see it."""
    from app.main import detailed_health

    failing_session = AsyncMock()
    failing_session.execute.side_effect = RuntimeError("connection refused")

    response = _stub_response()
    out = await detailed_health(response=response, db=failing_session)
    assert out["status"] == "degraded"
    assert out["services"]["database"].startswith("error:")
    # Critical regression check from the audit — endpoint must surface
    # 503 when a hard dependency is down, not silently 200.
    assert response.status_code == 503


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_via_testclient():
    """Full ASGI smoke test — opt in with `pytest -m integration` and a real
    Postgres + Redis available. Skipped by default because we don't ship
    fixtures for spinning those up.
    """
    from httpx import ASGITransport, AsyncClient
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"
