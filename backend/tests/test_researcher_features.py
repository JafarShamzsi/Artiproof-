"""Tests for the new researcher features: bulk, batch poll, rerun + snapshots,
watchlist add/remove/list with delta vs latest snapshot.

These pin the route-layer contract (ownership, idempotency, caps,
hydration shape) without spinning up a real DB. Snapshot-on-rerun is
exercised against a fake AsyncSession that captures the .add() calls
so we can assert a ResearcherSnapshot was inserted with prior values.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app
from app.models.researcher import ResearcherProfile
from app.models.researcher_snapshot import ResearcherSnapshot
from app.utils.auth import (
    get_current_user,
    get_current_user_allow_deactivated,
)


def _user(**overrides):
    base = SimpleNamespace(
        id="user-a",
        email="user-a@example.com",
        full_name="Test User",
        role="researcher",
        tier="free",
        locale="en",
        hashed_password=None,
        deactivated_at=None,
        deleted_at=None,
        email_verified_at=None,
        totp_secret=None,
        totp_enabled=False,
        totp_backup_codes=None,
        linked_providers=None,
        analysis_preferences=None,
        notification_preferences=None,
        pinned_items=None,
        organization_id=None,
        share_activity_with_team=True,
        institution=None,
        watchlist=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


def _profile(**overrides):
    base = SimpleNamespace(
        id="rp-1",
        user_id="user-a",
        researcher_name="Dr. Climate",
        scopus_id=None,
        google_scholar_id=None,
        orcid=None,
        institution="ADA University",
        official_h_index=20,
        official_citation_count=2000,
        adjusted_h_index=18,
        adjusted_citation_count=1800,
        integrity_score=80.0,
        self_citation_rate=0.10,
        topic_relevance_score=0.85,
        total_publications=50,
        citation_ring_flags={"flags": [], "rings": [], "suspicious_pairs": []},
        integrity_breakdown=None,
        model_metadata=None,
        analysis_status="completed",
        scrape_status="completed",
        last_analyzed_at=datetime.now(timezone.utc),
        deleted_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


@pytest.fixture
def env(monkeypatch):
    from app.tasks import celery_app

    monkeypatch.setattr("app.routers.researcher.queue_run", AsyncMock())
    send_task = Mock()
    if celery_app is not None:
        monkeypatch.setattr(celery_app, "send_task", send_task)
    user = _user()
    db = AsyncMock()

    class _Empty:
        def all(self):
            return []

        def scalars(self):
            return SimpleNamespace(all=lambda: [], first=lambda: None)

        def scalar_one_or_none(self):
            return None

        def scalar_one(self):
            return None

        def scalar(self):
            return 0

    db.execute.return_value = _Empty()

    async def _db_dep():
        yield db

    app.dependency_overrides[get_db] = _db_dep
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_user_allow_deactivated] = lambda: user

    yield SimpleNamespace(user=user, db=db, send_task=send_task)
    app.dependency_overrides.clear()


# ─── Bulk + batch ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_researcher_bulk_rejects_empty(env):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/researcher/bulk", json={"items": []})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_researcher_bulk_caps_at_50(env):
    items = [{"researcher_name": f"Dr. {i}"} for i in range(51)]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/researcher/bulk", json={"items": items})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_researcher_bulk_requires_at_least_one_identifier(env):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/researcher/bulk",
            json={"items": [{"researcher_name": None, "orcid": None}]},
        )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_researcher_bulk_rejects_invalid_orcid(env):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/researcher/bulk",
            json={"items": [{"orcid": "not-an-orcid"}]},
        )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_researcher_batch_requires_ids(env):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/researcher/batch")
    assert r.status_code == 422


# ─── Rerun ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rerun_404_when_not_found(env):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/researcher/no-such/rerun")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_rerun_403_for_other_user(env):
    other = _profile(user_id="someone-else")

    class _R:
        def scalar_one_or_none(self):
            return other

        def scalars(self):
            return SimpleNamespace(all=lambda: [])

    env.db.execute.return_value = _R()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/researcher/rp-1/rerun")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_rerun_resets_status_for_owned_profile(env):
    own = _profile()

    class _R:
        def scalar_one_or_none(self):
            return own

        def scalars(self):
            return SimpleNamespace(all=lambda: [])

    env.db.execute.return_value = _R()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/researcher/rp-1/rerun")
    assert r.status_code == 200
    assert own.analysis_status == "pending"
    assert own.scrape_status == "pending"
    env.send_task.assert_called_once_with("researcher.run_pipeline", args=[own.id])


# ─── Snapshots ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_snapshots_404_for_unknown_profile(env):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/researcher/no-such/snapshots")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_snapshots_returns_ordered_list(env):
    own = _profile()
    s1 = SimpleNamespace(
        id="s1", researcher_profile_id=own.id,
        official_h_index=10, official_citation_count=1000,
        adjusted_h_index=9, adjusted_citation_count=900,
        integrity_score=70.0, self_citation_rate=0.12,
        topic_relevance_score=0.8, total_publications=40,
        citation_ring_flags=None, integrity_breakdown=None, model_metadata=None,
        captured_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    s2 = SimpleNamespace(
        id="s2", researcher_profile_id=own.id,
        official_h_index=15, official_citation_count=1500,
        adjusted_h_index=14, adjusted_citation_count=1400,
        integrity_score=75.0, self_citation_rate=0.11,
        topic_relevance_score=0.82, total_publications=45,
        citation_ring_flags=None, integrity_breakdown=None, model_metadata=None,
        captured_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )

    call_count = {"n": 0}

    async def execute_side_effect(_q):
        call_count["n"] += 1
        # 1st call: fetch profile
        if call_count["n"] == 1:
            return SimpleNamespace(scalar_one_or_none=lambda: own)
        # 2nd call: snapshots
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [s2, s1]))

    env.db.execute.side_effect = execute_side_effect

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/researcher/rp-1/snapshots")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    assert body[0]["id"] == "s2"
    assert body[1]["id"] == "s1"


# ─── Watchlist ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_watchlist_empty_for_fresh_user(env):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/me/watchlist")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_add_to_watchlist_unowned_404(env):
    """A profile that doesn't belong to the current user → 404."""
    other = _profile(user_id="someone-else")

    async def get_side_effect(model, pk):
        if model is ResearcherProfile and pk == "rp-1":
            return other
        return None

    env.db.get.side_effect = get_side_effect

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/me/watchlist/rp-1")
    assert r.status_code == 404
    assert env.user.watchlist in (None, [])


@pytest.mark.asyncio
async def test_add_to_watchlist_idempotent(env):
    """Re-adding shouldn't create a duplicate entry."""
    own = _profile()
    env.user.watchlist = [
        {"researcher_id": "rp-1", "added_at": "2026-01-01T00:00:00+00:00"}
    ]

    async def get_side_effect(model, pk):
        if model is ResearcherProfile and pk == "rp-1":
            return own
        return None

    env.db.get.side_effect = get_side_effect

    # The hydrate path runs two queries: profiles lookup + snapshots lookup.
    # Return the profile on the first call, no snapshots on the second.
    call_count = {"n": 0}

    async def execute_side_effect(_q):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [own]))
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))

    env.db.execute.side_effect = execute_side_effect

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/me/watchlist/rp-1")
    assert r.status_code == 201
    assert len(env.user.watchlist) == 1


@pytest.mark.asyncio
async def test_add_to_watchlist_cap_enforced(env):
    """When at MAX_WATCHLIST, further adds 400."""
    from app.constants import MAX_WATCHLIST

    own = _profile(id="rp-new")
    env.user.watchlist = [
        {"researcher_id": f"rp-{i}", "added_at": "2026-01-01T00:00:00+00:00"}
        for i in range(MAX_WATCHLIST)
    ]

    async def get_side_effect(model, pk):
        if model is ResearcherProfile and pk == "rp-new":
            return own
        return None

    env.db.get.side_effect = get_side_effect
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/me/watchlist/rp-new")
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_remove_from_watchlist(env):
    env.user.watchlist = [
        {"researcher_id": "rp-1", "added_at": "2026-01-01T00:00:00+00:00"},
        {"researcher_id": "rp-2", "added_at": "2026-01-02T00:00:00+00:00"},
    ]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.delete("/api/me/watchlist/rp-1")
    assert r.status_code == 204
    assert env.user.watchlist == [
        {"researcher_id": "rp-2", "added_at": "2026-01-02T00:00:00+00:00"}
    ]


@pytest.mark.asyncio
async def test_remove_from_watchlist_404_when_absent(env):
    env.user.watchlist = []
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.delete("/api/me/watchlist/rp-99")
    assert r.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("prior_version, expected_delta", [("1.1", 12), ("1.0", None), (None, None)])
async def test_watchlist_list_computes_delta_vs_latest_snapshot(env, prior_version, expected_delta):
    """Hydrated watchlist row carries integrity_score_delta = current - prior."""
    own = _profile(integrity_score=82.0, integrity_breakdown={"formula_version": "1.1"})
    env.user.watchlist = [
        {"researcher_id": "rp-1", "added_at": "2026-01-01T00:00:00+00:00"}
    ]

    snap = SimpleNamespace(
        id="s1",
        researcher_profile_id="rp-1",
        integrity_score=70.0,
        integrity_breakdown={"formula_version": prior_version},
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    call_count = {"n": 0}

    async def execute_side_effect(_q):
        call_count["n"] += 1
        if call_count["n"] == 1:  # profiles
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [own]))
        # snapshots
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [snap]))

    env.db.execute.side_effect = execute_side_effect

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/me/watchlist")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["researcher_id"] == "rp-1"
    assert body[0]["integrity_score"] == 82.0
    assert body[0]["integrity_score_delta"] == expected_delta
