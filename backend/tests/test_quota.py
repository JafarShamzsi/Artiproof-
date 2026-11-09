"""Tests for the tier quota enforcement.

Pure-function tests against `assert_quota` with stubbed DB execute — no
need for a real Postgres. Three angles:

1. Free tier is gated; over-limit raises 402.
2. Team tier is unlimited; no raise even at very high counts.
3. Bulk units consume against the same MTD count.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.utils.quota import assert_quota


def _user(tier: str = "free"):
    return SimpleNamespace(id="user-1", tier=tier)


def _db_with_mtd_count(count: int) -> AsyncMock:
    """Stub a db.execute that returns an object whose .scalar() yields count."""
    db = AsyncMock()
    db.execute = AsyncMock(
        return_value=SimpleNamespace(scalar=lambda: count)
    )
    return db


@pytest.mark.asyncio
async def test_free_tier_under_limit_passes():
    db = _db_with_mtd_count(9)  # used 9 of 10 free source_checks
    await assert_quota(db, _user("free"), "source_checks", units=1)


@pytest.mark.asyncio
async def test_free_tier_at_limit_raises():
    db = _db_with_mtd_count(10)  # already at 10
    with pytest.raises(HTTPException) as excinfo:
        await assert_quota(db, _user("free"), "source_checks", units=1)
    assert excinfo.value.status_code == 402
    detail = excinfo.value.detail
    assert detail["error"] == "quota_exceeded"
    assert detail["kind"] == "source_checks"
    assert detail["used"] == 10
    assert detail["limit"] == 10
    assert detail["tier"] == "free"
    assert detail["remaining"] == 0
    assert "/pricing" in detail["upgrade_url"]


@pytest.mark.asyncio
async def test_free_tier_bulk_over_limit_raises():
    """A 5-unit bulk request when 8 are already used → would push to 13/10."""
    db = _db_with_mtd_count(8)
    with pytest.raises(HTTPException) as excinfo:
        await assert_quota(db, _user("free"), "source_checks", units=5)
    assert excinfo.value.status_code == 402
    assert excinfo.value.detail["requested"] == 5


@pytest.mark.asyncio
async def test_pro_tier_higher_limit_passes():
    """Pro tier 100/mo — at 50 used a bulk of 30 still fits."""
    db = _db_with_mtd_count(50)
    await assert_quota(db, _user("pro"), "source_checks", units=30)


@pytest.mark.asyncio
async def test_team_tier_unlimited_no_db_call():
    """Team tier has limit=None → assert_quota short-circuits without counting."""
    db = AsyncMock()
    # db.execute is not configured — if it gets called, the test fails loud.
    await assert_quota(db, _user("team"), "source_checks", units=1000)
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_zero_units_short_circuits():
    db = AsyncMock()
    await assert_quota(db, _user("free"), "source_checks", units=0)
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_researcher_kind_uses_researcher_limit():
    """Free tier: 5 researcher_analyses_per_month, so 5 used + 1 = over."""
    db = _db_with_mtd_count(5)
    with pytest.raises(HTTPException) as excinfo:
        await assert_quota(db, _user("free"), "researcher_analyses", units=1)
    assert excinfo.value.detail["kind"] == "researcher_analyses"
    assert excinfo.value.detail["limit"] == 5


@pytest.mark.asyncio
async def test_reports_kind_uses_reports_limit():
    db = _db_with_mtd_count(4)
    await assert_quota(db, _user("free"), "reports", units=1)  # 4+1=5 OK
    db2 = _db_with_mtd_count(5)
    with pytest.raises(HTTPException):
        await assert_quota(db2, _user("free"), "reports", units=1)


@pytest.mark.asyncio
async def test_unknown_tier_falls_back_to_free():
    """A row with tier='enterprise' (unknown) shouldn't bypass the quota."""
    db = _db_with_mtd_count(10)
    with pytest.raises(HTTPException) as excinfo:
        await assert_quota(db, _user("enterprise-typo"), "source_checks", units=1)
    # Used 'free' limits because tier wasn't in TIER_LIMITS
    assert excinfo.value.detail["limit"] == 10
