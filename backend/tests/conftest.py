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

import pytest


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
