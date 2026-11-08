"""Shared pytest fixtures.

Note: this codebase's schema uses Postgres-only features (custom enum types,
``ALTER COLUMN ... USING`` in migration 0002, JSON columns, the Prisma-created
``UserRole`` enum). SQLite-backed tests would either fail on those or silently
diverge from prod behavior, so we don't use the SQLite fixture pattern at all.

Most tests in this repo are pure-function tests (scoring math, regex, parsers,
threshold logic) and don't need a database. The few that exercise endpoints
override ``get_db`` with a stub, or are marked ``@pytest.mark.integration``
and run against a real Postgres in CI.
"""

from __future__ import annotations

import os
import ipaddress
import socket
import threading

import pytest


@pytest.fixture(autouse=True)
def _showcase_network_boundary(monkeypatch, request):
    """Unit tests never connect; integration tests only use disposable loopback services."""
    original = socket.socket.connect
    original_pair = socket.socketpair
    constructing_pair = threading.local()
    integration = request.node.get_closest_marker("integration") is not None

    def guarded_connect(sock, address):
        host = address[0] if isinstance(address, tuple) else ""
        try:
            local = host == "localhost" or ipaddress.ip_address(host).is_loopback
        except ValueError:
            local = False
        # Windows implements socketpair using a temporary loopback connection;
        # asyncio needs this private self-pipe even in network-denied unit tests.
        internal_pair = getattr(constructing_pair, "active", False) and local
        if not internal_pair and (not integration or not local):
            raise RuntimeError("Showcase tests forbid network access outside isolated integration services")
        return original(sock, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)

    def guarded_pair(*args, **kwargs):
        constructing_pair.active = True
        try:
            return original_pair(*args, **kwargs)
        finally:
            constructing_pair.active = False

    monkeypatch.setattr(socket, "socketpair", guarded_pair)


# Ensure the backend tests don't accidentally hit a real Gemini / FactCheck
# endpoint via leftover env vars. Each test that needs a key explicitly sets
# it via monkeypatch.
@pytest.fixture(autouse=True)
def _strip_external_api_keys(monkeypatch):
    for key in (
        "GEMINI_API_KEY",
        "GOOGLE_FACTCHECK_API_KEY",
        "SCOPUS_API_KEY",
        "SEMANTIC_SCHOLAR_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    # Ensure dev/staging behavior so JWT_SECRET-empty paths don't raise
    monkeypatch.setenv("ENVIRONMENT", "test")
    yield


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Wipe slowapi's in-memory limit counters between tests.

    Without this every test that hits a decorated endpoint inherits the
    previous test's bucket usage, and the second/third test in a file
    sporadically 429s once the anonymous cap (1/minute) is exhausted.
    The fixture is autouse so individual suites don't have to remember.
    """
    from app.utils.rate_limit import limiter

    limiter.reset()
    yield
    limiter.reset()
