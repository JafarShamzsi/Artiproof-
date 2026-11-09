"""Deep readiness probe — ``/api/health/deep``.

Five probes (DB, Redis, Gemini, CrossRef, OpenAlex) run in parallel
behind a 2s timeout each. We don't reach the real external services in
unit tests; the contract being pinned is:

- Probe wrapper turns success into ``"ok"`` and exceptions into
  ``"error: <ExceptionName>"`` — never propagates.
- Aggregate ``ok`` flag flips False as soon as any probe is non-ok.
- Non-ok → response.status_code = 503 (so an external uptime monitor
  pages on the right level).
- All five probes run concurrently; one slow probe doesn't serialise
  the others.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.routers.health import (
    _PROBE_TIMEOUT_S,
    _probe,
    deep_health,
)


def _stub_response():
    return SimpleNamespace(status_code=200)


# ─── _probe wrapper contract ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_probe_returns_ok_when_inner_succeeds():
    async def ok():
        return None

    assert await _probe("x", ok) == ("x", "ok")


@pytest.mark.asyncio
async def test_probe_surfaces_exception_type_name():
    async def fail():
        raise ValueError("nope")

    name, status = await _probe("x", fail)
    assert name == "x"
    assert status == "error: ValueError"


@pytest.mark.asyncio
async def test_probe_handles_timeout():
    async def slow():
        await asyncio.sleep(_PROBE_TIMEOUT_S + 1.0)

    name, status = await _probe("x", slow)
    assert name == "x"
    assert status == "error: TimeoutError"


# ─── Aggregate route behaviour ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_deep_health_all_ok(monkeypatch):
    """When every probe succeeds, aggregate ok=True and status stays 200."""
    async def noop(*_a, **_kw):
        return None

    monkeypatch.setattr("app.routers.health._probe_redis", noop)
    monkeypatch.setattr("app.routers.health._probe_gemini", noop)
    monkeypatch.setattr("app.routers.health._probe_crossref", noop)
    monkeypatch.setattr("app.routers.health._probe_openalex", noop)

    stub_db = AsyncMock()
    stub_db.execute.return_value = None

    response = _stub_response()
    out = await deep_health(response=response, db=stub_db)

    assert out["ok"] is True
    assert response.status_code == 200
    assert set(out["services"]) == {
        "database", "redis", "gemini", "crossref", "openalex",
    }
    assert all(v == "ok" for v in out["services"].values())


@pytest.mark.asyncio
async def test_deep_health_one_failure_yields_503(monkeypatch):
    """Any non-ok probe trips the 503 — partial degradation pages oncall."""
    async def noop(*_a, **_kw):
        return None

    async def fail():
        raise RuntimeError("kaboom")

    monkeypatch.setattr("app.routers.health._probe_redis", noop)
    monkeypatch.setattr("app.routers.health._probe_gemini", fail)
    monkeypatch.setattr("app.routers.health._probe_crossref", noop)
    monkeypatch.setattr("app.routers.health._probe_openalex", noop)

    stub_db = AsyncMock()
    stub_db.execute.return_value = None

    response = _stub_response()
    out = await deep_health(response=response, db=stub_db)

    assert out["ok"] is False
    assert response.status_code == 503
    assert out["services"]["gemini"] == "error: RuntimeError"
    # The other probes still report ok so an operator can see the
    # blast radius at a glance instead of a single opaque "degraded".
    assert out["services"]["database"] == "ok"
    assert out["services"]["crossref"] == "ok"


@pytest.mark.asyncio
async def test_deep_health_db_failure_marks_503(monkeypatch):
    """DB is the cheapest probe; if even it's down, definitely 503."""
    async def noop(*_a, **_kw):
        return None

    monkeypatch.setattr("app.routers.health._probe_redis", noop)
    monkeypatch.setattr("app.routers.health._probe_gemini", noop)
    monkeypatch.setattr("app.routers.health._probe_crossref", noop)
    monkeypatch.setattr("app.routers.health._probe_openalex", noop)

    failing_db = AsyncMock()
    failing_db.execute.side_effect = RuntimeError("conn refused")

    response = _stub_response()
    out = await deep_health(response=response, db=failing_db)

    assert out["ok"] is False
    assert response.status_code == 503
    assert out["services"]["database"].startswith("error:")


@pytest.mark.asyncio
async def test_deep_health_probes_run_concurrently(monkeypatch):
    """Five probes × 1s sleep each should finish under ~1.5s if concurrent,
    over ~5s if serialised. Wall-clock isn't a great oracle for this but
    asyncio's primitives make the difference > 2x."""
    delay = 0.4

    async def slow_probe():
        await asyncio.sleep(delay)

    monkeypatch.setattr("app.routers.health._probe_redis", slow_probe)
    monkeypatch.setattr("app.routers.health._probe_gemini", slow_probe)
    monkeypatch.setattr("app.routers.health._probe_crossref", slow_probe)
    monkeypatch.setattr("app.routers.health._probe_openalex", slow_probe)

    # DB stub is instant
    stub_db = AsyncMock()
    stub_db.execute.return_value = None

    import time
    response = _stub_response()
    start = time.perf_counter()
    out = await deep_health(response=response, db=stub_db)
    elapsed = time.perf_counter() - start

    assert out["ok"] is True
    # Concurrent: ~delay; serialised would be ~4*delay. 2× headroom.
    assert elapsed < delay * 2.0, (
        f"probes appear serialised: {elapsed:.2f}s for 4 × {delay}s sleeps"
    )
