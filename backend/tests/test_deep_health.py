"""Public deep health checks infrastructure, never external providers."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from app.routers import health
from fastapi import FastAPI, Response
from google import genai


@pytest.mark.asyncio
async def test_probe_returns_ok_when_inner_succeeds():
    assert await health._probe("x", AsyncMock()) == ("x", "ok")


@pytest.mark.asyncio
async def test_probe_surfaces_only_exception_type():
    probe = AsyncMock(side_effect=ValueError("synthetic private detail"))
    assert await health._probe("x", probe) == ("x", "error: ValueError")


@pytest.mark.asyncio
async def test_probe_handles_timeout(monkeypatch):
    monkeypatch.setattr(health, "_PROBE_TIMEOUT_S", 0.01)

    async def slow():
        await asyncio.sleep(1)

    assert await health._probe("x", slow) == ("x", "error: TimeoutError")


@pytest.mark.asyncio
@pytest.mark.parametrize("configured", [False, True])
@pytest.mark.parametrize("failure", [None, "database", "redis"])
async def test_public_deep_health_never_constructs_or_calls_providers(
    monkeypatch, configured, failure,
):
    # Keep the real HTTP test client before trapping external client constructors.
    test_client = httpx.AsyncClient
    provider = Mock(side_effect=AssertionError("external provider constructed"))
    monkeypatch.setattr(genai, "Client", provider)
    monkeypatch.setattr(httpx, "AsyncClient", provider)
    monkeypatch.setattr(httpx, "Client", provider)
    monkeypatch.setattr(
        health.settings, "GEMINI_API_KEY", "synthetic-key-not-real" if configured else "",
    )
    db = AsyncMock()
    redis = AsyncMock()
    if failure == "database":
        db.execute.side_effect = RuntimeError("synthetic private detail")
    elif failure == "redis":
        redis.side_effect = RuntimeError("synthetic private detail")
    monkeypatch.setattr(health, "_probe_redis", redis)
    app = FastAPI()
    app.include_router(health.router)
    app.dependency_overrides[health.get_db] = lambda: db
    async with test_client(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
    ) as client:
        response = await client.get("/api/health/deep")  # no authentication
    assert provider.call_count == 0
    assert response.status_code == (503 if failure else 200)
    body = response.json()
    assert body["ok"] is (failure is None)
    assert body["service"] == "artiproof-api"
    assert body["services"] == {
        "database": "error: RuntimeError" if failure == "database" else "ok",
        "redis": "error: RuntimeError" if failure == "redis" else "ok",
        "gemini": "disabled: not tested",
        "crossref": "disabled: not tested",
        "openalex": "disabled: not tested",
    }
    db.execute.assert_awaited_once()
    redis.assert_awaited_once()


@pytest.mark.asyncio
async def test_infrastructure_probes_run_concurrently(monkeypatch):
    started = set()
    both_started = asyncio.Event()

    async def probe(name):
        started.add(name)
        if len(started) == 2:
            both_started.set()
        await asyncio.wait_for(both_started.wait(), timeout=0.2)

    monkeypatch.setattr(health, "_probe_db", lambda _db: probe("database"))
    monkeypatch.setattr(health, "_probe_redis", lambda: probe("redis"))
    result = await health.deep_health(response=Response(), db=AsyncMock())
    assert result["ok"] is True
    assert started == {"database", "redis"}
