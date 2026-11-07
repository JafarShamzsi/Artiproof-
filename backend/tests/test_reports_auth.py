"""Reports router authorization — pins the fix that stopped GET /api/reports/{id}
and GET /api/reports/{id}/download from leaking any user's report.

These tests don't need a real DB: we override `get_db` and `get_current_user`
with stubs and build the response ourselves so the test focuses on the
ownership-check branches in the router.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app
from app.utils.auth import get_current_user


def _fake_user(user_id: str = "user-a"):
    return SimpleNamespace(id=user_id, email=f"{user_id}@test", role="researcher")


def _fake_report(*, report_id: str, owner_id: str):
    return SimpleNamespace(
        id=report_id,
        user_id=owner_id,
        source_check_id=None,
        researcher_profile_id=None,
        report_type="source_verification",
        title="Stub",
        summary="Stub summary",
        pdf_path=None,
        share_token="stub-token",
        deleted_at=None,
        created_at=datetime.now(timezone.utc),
    )


def _override_db(report):
    """Build a stub AsyncSession whose execute(...) returns the given report."""

    class _Result:
        def __init__(self, row):
            self._row = row

        def scalar_one_or_none(self):
            return self._row

    db = AsyncMock()
    db.execute.return_value = _Result(report)
    return db


@pytest.mark.asyncio
async def test_get_report_returns_owner_data():
    report = _fake_report(report_id="r1", owner_id="user-a")

    async def _db():
        yield _override_db(report)

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: _fake_user("user-a")

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/api/reports/r1")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == "r1"
        assert body["title"] == "Stub"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_report_403s_for_non_owner():
    report = _fake_report(report_id="r1", owner_id="user-a")

    async def _db():
        yield _override_db(report)

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: _fake_user("user-b")  # different

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/api/reports/r1")
        assert r.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_download_report_403s_for_non_owner():
    report = _fake_report(report_id="r1", owner_id="user-a")

    async def _db():
        yield _override_db(report)

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: _fake_user("user-b")

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/api/reports/r1/download")
        assert r.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_report_401_without_token():
    """No auth dep override -> the real get_current_user runs and rejects."""
    report = _fake_report(report_id="r1", owner_id="user-a")

    async def _db():
        yield _override_db(report)

    app.dependency_overrides[get_db] = _db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/api/reports/r1")
        assert r.status_code == 401
    finally:
        app.dependency_overrides.clear()
