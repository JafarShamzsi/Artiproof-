"""Tests for the request-id middleware.

Covers the contract:
  * Every response carries an X-Request-ID header.
  * An inbound X-Request-ID is honored (load balancers, Cloudflare, etc.).
  * Two requests with no header get different ids.
  * Log lines emitted during the request include the id.
"""

from __future__ import annotations

import logging
import re

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app, current_request_id


@pytest.mark.asyncio
async def test_response_has_request_id_header():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/health")
    assert r.status_code == 200
    rid = r.headers.get("X-Request-ID")
    assert rid is not None
    # UUIDv4 shape — 8-4-4-4-12 hex
    assert re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", rid)


@pytest.mark.asyncio
async def test_inbound_request_id_is_honored():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get(
            "/health", headers={"X-Request-ID": "trace-abc-123"}
        )
    assert r.headers["X-Request-ID"] == "trace-abc-123"


@pytest.mark.asyncio
async def test_oversized_inbound_id_is_replaced():
    """A pathologically long header should not leak into logs / Sentry —
    the middleware caps the inbound id and falls back to a fresh UUID."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get(
            "/health", headers={"X-Request-ID": "x" * 500}
        )
    returned = r.headers["X-Request-ID"]
    assert returned != "x" * 500
    assert len(returned) <= 64


@pytest.mark.asyncio
async def test_two_requests_get_distinct_ids():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r1 = await c.get("/health")
        r2 = await c.get("/health")
    assert r1.headers["X-Request-ID"] != r2.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_log_records_carry_request_id(caplog):
    """The middleware emits an INFO access log for non-health paths; the
    production stdout handler has the _RequestIdFilter attached, which
    stamps request_id onto each record before the formatter runs.

    pytest's caplog uses its own LogCaptureHandler which doesn't inherit
    that filter, so we install it here so the test mirrors what prod
    actually sees on stdout. Uses an unregistered path so the request
    404s but still trips the access-log branch — `/api/health` and
    `/health` are silenced in the middleware to keep prod logs readable.
    """
    from app.main import _RequestIdFilter  # private, but the contract is fixed

    caplog.handler.addFilter(_RequestIdFilter())
    transport = ASGITransport(app=app)
    try:
        with caplog.at_level(logging.INFO, logger="artiproof"):
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                r = await c.get(
                    "/__nonexistent_for_logging__",
                    headers={"X-Request-ID": "log-test-id"},
                )
    finally:
        caplog.handler.removeFilter(caplog.handler.filters[-1])

    assert r.headers["X-Request-ID"] == "log-test-id"
    access_logs = [rec for rec in caplog.records if rec.name == "artiproof"]
    assert access_logs, "expected an access log line from the middleware"
    assert any(getattr(rec, "request_id", None) == "log-test-id" for rec in access_logs)


def test_current_request_id_outside_request_returns_default():
    """The contextvar default keeps logs from blowing up when something
    logs at import time or in a background task with no request scope."""
    assert current_request_id() == "-"
