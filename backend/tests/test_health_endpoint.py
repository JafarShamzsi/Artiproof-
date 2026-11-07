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


@pytest.mark.asyncio
async def test_detailed_health_with_stub_db():
    """`/api/health` reports services dict; DB stubbed via injection."""
    from app.main import detailed_health

    stub_session = AsyncMock()
    # `await session.execute(text("SELECT 1"))` should resolve to anything
    stub_session.execute.return_value = None

    out = await detailed_health(db=stub_session)

    assert "status" in out
    assert "services" in out
    assert out["services"]["database"] == "ok"
    # External-API keys are stripped by the autouse conftest fixture
    assert out["services"]["gemini"] == "missing"
    assert out["services"]["google_factcheck"] == "missing"
    # Redis is unlikely to be running in unit-test env — accept either result
    assert out["services"]["redis"] in {"ok"} or out["services"]["redis"].startswith("error")


@pytest.mark.asyncio
async def test_detailed_health_marks_degraded_on_db_failure():
    """If the DB SELECT raises, status flips to 'degraded' but call doesn't 500."""
    from app.main import detailed_health

    failing_session = AsyncMock()
    failing_session.execute.side_effect = RuntimeError("connection refused")

    out = await detailed_health(db=failing_session)
    assert out["status"] == "degraded"
    assert out["services"]["database"].startswith("error:")


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
