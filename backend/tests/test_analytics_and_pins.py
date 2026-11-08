"""Tests for the dashboard analytics + pins endpoints.

Pins exercise SQLAlchemy queries against owned rows, so these tests use
a real-ish in-memory fake AsyncSession that responds to the specific
queries the routes issue. Score distribution + top issues tests stub the
underlying aggregates; team activity gates on tier/org so we test the 403
and 404 paths there.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app
from app.models.report import Report
from app.models.researcher import ResearcherProfile
from app.models.source_check import SourceCheck
from app.utils.auth import (
    get_current_user,
    get_current_user_allow_deactivated,
)


def _user(**overrides):
    base = SimpleNamespace(
        id="user-a",
        email="user-a@example.com",
        full_name="Test User",
        institution=None,
        role="researcher",
        tier="free",
        locale="en",
        hashed_password=None,
        notification_preferences=None,
        deactivated_at=None,
        deleted_at=None,
        email_verified_at=None,
        totp_secret=None,
        totp_enabled=False,
        totp_backup_codes=None,
        linked_providers=None,
        analysis_preferences=None,
        pinned_items=None,
        organization_id=None,
        share_activity_with_team=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


@pytest.fixture
def with_user():
    """Wires get_db with an AsyncMock and get_current_user with a stub user.

    Each test mutates `env.user` to set up scenario state, and inspects
    `env.user` after the call to assert side-effects. The DB execute mock
    returns empty result sets — tests that need richer query results
    override `env.db.execute.return_value` per call."""

    def _apply(**user_overrides):
        user = _user(**user_overrides)
        db = AsyncMock()
        # Default: all queries return empty.
        empty = SimpleNamespace(
            all=lambda: [],
            scalars=lambda: SimpleNamespace(all=lambda: []),
            scalar_one_or_none=lambda: None,
            one=lambda: SimpleNamespace(
                ai_content_checks=0,
                low_credibility_checks=0,
                retracted=0,
                broken=0,
            ),
        )
        db.execute.return_value = empty

        async def _db_dep():
            yield db

        app.dependency_overrides[get_db] = _db_dep
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_current_user_allow_deactivated] = lambda: user
        return SimpleNamespace(user=user, db=db)

    yield _apply
    app.dependency_overrides.clear()


# ─── Score distribution ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_score_distribution_zero_when_no_checks(with_user):
    with_user()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/dashboard/score-distribution")
    assert r.status_code == 200
    assert r.json() == {"high": 0, "medium": 0, "low": 0, "total": 0}


@pytest.mark.asyncio
async def test_score_distribution_buckets_count(with_user):
    env = with_user()
    # Stub the aggregate query to return {high: 5, low: 2}
    env.db.execute.return_value = SimpleNamespace(
        all=lambda: [("high", 5), ("low", 2)],
        scalars=lambda: SimpleNamespace(all=lambda: []),
        scalar_one_or_none=lambda: None,
        one=lambda: None,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/dashboard/score-distribution")
    assert r.status_code == 200
    body = r.json()
    assert body["high"] == 5
    assert body["medium"] == 0
    assert body["low"] == 2
    assert body["total"] == 7


# ─── Top issues ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_top_issues_zero_for_fresh_account(with_user):
    with_user()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/dashboard/top-issues")
    assert r.status_code == 200
    body = r.json()
    assert body["ai_content_checks"] == 0
    assert body["low_credibility_checks"] == 0
    assert body["retracted_citations"] == 0
    assert body["broken_citations"] == 0
    assert body["citation_rings_flagged"] == 0


@pytest.mark.asyncio
async def test_top_issues_counts_citation_rings(with_user):
    env = with_user()
    # Two researcher rows: one with rings, one without
    rp_with_rings = ({"rings": [{"members": [], "total_mutual_citations": 8}], "flags": []},)
    rp_no_rings = ({"rings": [], "flags": ["self-cite high"]},)
    rp_no_flags_at_all = (None,)

    call_count = {"n": 0}

    async def execute_side_effect(_q):
        call_count["n"] += 1
        # 1st call: source-check aggregates (sc_aggregates)
        # 2nd call: citation aggregates
        # 3rd call: researcher profile flags column
        if call_count["n"] == 1:
            return SimpleNamespace(
                one=lambda: SimpleNamespace(ai_content_checks=0, low_credibility_checks=0)
            )
        if call_count["n"] == 2:
            return SimpleNamespace(one=lambda: SimpleNamespace(retracted=0, broken=0))
        # Researcher rows
        return SimpleNamespace(
            all=lambda: [rp_with_rings, rp_no_rings, rp_no_flags_at_all]
        )

    env.db.execute.side_effect = execute_side_effect

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/dashboard/top-issues")
    assert r.status_code == 200
    body = r.json()
    assert body["citation_rings_flagged"] == 1


# ─── Pins ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pin_rejects_unowned_item(with_user):
    env = with_user()

    # The route calls db.get(SourceCheck, id). Return an SC owned by someone else.
    other_sc = SimpleNamespace(
        id="sc-other", user_id="someone-else", deleted_at=None
    )

    async def get_side_effect(model, pk):
        if model is SourceCheck and pk == "sc-other":
            return other_sc
        return None

    env.db.get.side_effect = get_side_effect

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/auth/me/pins", json={"kind": "source_check", "id": "sc-other"}
        )
    assert r.status_code == 404
    # User's pinned_items unchanged
    assert env.user.pinned_items in (None, [])


@pytest.mark.asyncio
async def test_pin_owned_item_succeeds(with_user):
    env = with_user()
    own_sc = SimpleNamespace(
        id="sc-mine",
        user_id=env.user.id,
        input_title="My check",
        input_type="url",
        overall_credibility_score=82.0,
        created_at=datetime.now(timezone.utc),
        deleted_at=None,
    )

    async def get_side_effect(model, pk):
        if model is SourceCheck and pk == "sc-mine":
            return own_sc
        return None

    env.db.get.side_effect = get_side_effect

    # The hydrate step calls db.execute(...) with a `select` for the
    # source_check table. Return the same own_sc from scalars().
    class _R:
        def scalars(self):
            return SimpleNamespace(all=lambda: [own_sc])

        def all(self):
            return []

    env.db.execute.return_value = _R()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/auth/me/pins", json={"kind": "source_check", "id": "sc-mine"}
        )
    assert r.status_code == 201
    body = r.json()
    assert len(body) == 1
    assert body[0]["kind"] == "source_check"
    assert body[0]["id"] == "sc-mine"
    # User row updated
    pins = env.user.pinned_items
    assert isinstance(pins, list) and len(pins) == 1
    assert pins[0]["kind"] == "source_check"
    assert pins[0]["id"] == "sc-mine"


@pytest.mark.asyncio
async def test_pin_cap_enforced(with_user):
    from app.constants import MAX_PINNED_ITEMS

    # Pre-populate the user with a full pin list
    pins = [
        {"kind": "source_check", "id": f"sc-{i}", "pinned_at": "2026-01-01T00:00:00+00:00"}
        for i in range(MAX_PINNED_ITEMS)
    ]
    env = with_user(pinned_items=pins)
    new_sc = SimpleNamespace(
        id="sc-new", user_id=env.user.id, deleted_at=None
    )

    async def get_side_effect(model, pk):
        if model is SourceCheck and pk == "sc-new":
            return new_sc
        return None

    env.db.get.side_effect = get_side_effect

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/auth/me/pins", json={"kind": "source_check", "id": "sc-new"}
        )
    assert r.status_code == 400
    assert "at most" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_remove_pin_succeeds(with_user):
    env = with_user(pinned_items=[
        {"kind": "source_check", "id": "sc-1", "pinned_at": "2026-01-01T00:00:00+00:00"},
        {"kind": "researcher", "id": "rp-1", "pinned_at": "2026-01-02T00:00:00+00:00"},
    ])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.delete("/api/auth/me/pins/source_check/sc-1")
    assert r.status_code == 204
    assert env.user.pinned_items == [
        {"kind": "researcher", "id": "rp-1", "pinned_at": "2026-01-02T00:00:00+00:00"},
    ]


@pytest.mark.asyncio
async def test_remove_pin_404_when_not_present(with_user):
    env = with_user(pinned_items=[])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.delete("/api/auth/me/pins/source_check/no-such-id")
    assert r.status_code == 404


# ─── Team activity gating ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_team_activity_403_for_free_tier(with_user):
    with_user(tier="free")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/dashboard/team-activity")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_team_activity_404_for_team_tier_without_org(with_user):
    with_user(tier="team", organization_id=None)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/dashboard/team-activity")
    assert r.status_code == 404


# ─── Share activity toggle ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_share_activity_toggle_persists(with_user):
    env = with_user(share_activity_with_team=True)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.put(
            "/api/auth/me/share-activity-with-team", json={"share": False}
        )
    assert r.status_code == 200
    assert env.user.share_activity_with_team is False


# ─── Global search ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_requires_q(with_user):
    with_user()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/dashboard/search")
    # Missing required `q` param → FastAPI 422
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_search_returns_empty_when_no_matches(with_user):
    """All three sub-queries return empty result sets."""
    env = with_user()

    class _Empty:
        def all(self):
            return []

    env.db.execute.return_value = _Empty()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/dashboard/search?q=nothing")
    assert r.status_code == 200
    assert r.json() == {"q": "nothing", "items": []}


@pytest.mark.asyncio
async def test_search_groups_results_across_kinds_and_sorts_by_recency(with_user):
    """Each of the three subqueries returns one row; route should merge,
    sort by created_at desc, and uniformly shape every item."""
    env = with_user()

    older = datetime(2026, 1, 1, tzinfo=timezone.utc)
    newer = datetime(2026, 5, 1, tzinfo=timezone.utc)
    middle = datetime(2026, 3, 1, tzinfo=timezone.utc)

    sc_row = SimpleNamespace(
        id="sc-1",
        input_title="Climate study",
        input_type="url",
        overall_credibility_score=88.0,
        created_at=older,
    )
    rp_row = SimpleNamespace(
        id="rp-1",
        researcher_name="Dr. Climate",
        institution="ADA University",
        integrity_score=92.0,
        created_at=newer,
    )
    rpt_row = SimpleNamespace(
        id="rpt-1",
        title="Climate report",
        report_type="source_verification",
        created_at=middle,
    )

    call_count = {"n": 0}

    async def execute_side_effect(_q):
        call_count["n"] += 1
        rows = [[sc_row], [rp_row], [rpt_row]][call_count["n"] - 1]
        return SimpleNamespace(all=lambda r=rows: r)

    env.db.execute.side_effect = execute_side_effect

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/dashboard/search?q=climate")
    assert r.status_code == 200
    body = r.json()
    assert body["q"] == "climate"
    assert len(body["items"]) == 3
    # newer > middle > older
    assert body["items"][0]["kind"] == "researcher"
    assert body["items"][1]["kind"] == "report"
    assert body["items"][2]["kind"] == "source_check"


@pytest.mark.asyncio
async def test_search_caps_at_limit(with_user):
    """When all three subqueries return rows that sum > limit, the total
    must be capped to the user-requested limit."""
    env = with_user()

    def make_rows(prefix: str, n: int):
        return [
            SimpleNamespace(
                id=f"{prefix}-{i}",
                input_title=f"{prefix}-{i}",
                input_type="url",
                overall_credibility_score=None,
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                researcher_name=f"{prefix}-{i}",
                institution=None,
                integrity_score=None,
                title=f"{prefix}-{i}",
                report_type="source_verification",
            )
            for i in range(n)
        ]

    call_count = {"n": 0}

    async def execute_side_effect(_q):
        call_count["n"] += 1
        prefix = ["sc", "rp", "rpt"][call_count["n"] - 1]
        rows = make_rows(prefix, 3)
        return SimpleNamespace(all=lambda r=rows: r)

    env.db.execute.side_effect = execute_side_effect

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/dashboard/search?q=foo&limit=5")
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 5
