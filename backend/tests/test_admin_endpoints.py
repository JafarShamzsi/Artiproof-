"""Tests for the admin operational endpoints.

The role gate is the highest-leverage assertion — confirm a non-admin
hits 403 across every route. The mutation tests then verify the
last-admin guard and the no-op PATCH contract."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app
from app.utils.auth import get_current_user


def _user(*, role: str = "researcher", **overrides):
    base = SimpleNamespace(
        id="user-z",
        email="z@example.com",
        full_name="Z",
        role=role,
        tier="free",
        organization_id=None,
        deactivated_at=None,
        deleted_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        email_verified_at=None,
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


class _AdminMemoryDb:
    """Minimal fake — supports the queries the admin router actually runs.

    For list/stats endpoints, ``execute(...)`` returns a result whose
    ``scalar()`` yields 0 by default and ``scalars().all()`` returns []
    so the routes don't crash. Tests that exercise non-empty paths swap
    in ``db.execute.side_effect``."""

    def __init__(self):
        self.users: dict[str, SimpleNamespace] = {}
        self.commit = AsyncMock()
        self.refresh = AsyncMock(side_effect=self._refresh)

    async def _refresh(self, obj):
        return obj

    def add(self, _obj):
        return None

    async def get(self, model, pk):
        from app.models.user import User as UserModel

        if model is UserModel:
            return self.users.get(pk)
        return None

    async def execute(self, _q):
        class _R:
            def scalar(self):
                return 0
            def scalar_one_or_none(self):
                return None
            def all(self):
                return []
            def scalars(self):
                class _S:
                    def all(self):
                        return []
                return _S()
        return _R()


@pytest.fixture
def env_admin():
    db = _AdminMemoryDb()
    admin = _user(role="admin", id="admin-1", email="admin@x.example")
    db.users[admin.id] = admin

    async def _db_dep():
        yield db

    app.dependency_overrides[get_db] = _db_dep
    app.dependency_overrides[get_current_user] = lambda: admin
    yield SimpleNamespace(db=db, admin=admin)
    app.dependency_overrides.clear()


@pytest.fixture
def env_non_admin():
    """Non-admin user — verifies the role gate fires."""
    db = _AdminMemoryDb()
    user = _user(role="researcher")

    async def _db_dep():
        yield db

    app.dependency_overrides[get_db] = _db_dep
    app.dependency_overrides[get_current_user] = lambda: user
    yield SimpleNamespace(db=db, user=user)
    app.dependency_overrides.clear()


# ─── Role gate ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/admin/users"),
        ("GET", "/api/admin/pipelines/failed"),
        ("GET", "/api/admin/stats"),
        ("PATCH", "/api/admin/users/some-id"),
    ],
)
@pytest.mark.asyncio
async def test_non_admin_gets_403(env_non_admin, method, path):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.request(method, path, json={} if method == "PATCH" else None)
    assert r.status_code == 403
    assert "Admin role required" in r.text


# ─── User list ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_user_list_returns_paged_response(env_admin):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/admin/users")
    assert r.status_code == 200
    body = r.json()
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert body["total"] == 0
    assert body["items"] == []


# ─── User update ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("old_org,new_org", [(None, "org-new"), ("org-old", "org-new"), ("org-old", "")])
async def test_admin_patch_cannot_reassign_org_or_apply_partial_mutations(env_admin, old_org, new_org):
    target = _user(id="recipient", organization_id=old_org, full_name="Recipient")
    env_admin.db.users[target.id] = target
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch(f"/api/admin/users/{target.id}",
                                      json={"organization_id": new_org, "tier": "pro"})
    assert response.status_code == 400, response.text
    assert target.organization_id == old_org
    assert target.tier == "free"
    env_admin.db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_patch_user_changes_tier(env_admin):
    target = _user(id="t1", tier="free", role="researcher")
    env_admin.db.users["t1"] = target
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.patch("/api/admin/users/t1", json={"tier": "pro"})
    assert r.status_code == 200
    assert r.json()["tier"] == "pro"
    assert target.tier == "pro"


@pytest.mark.asyncio
async def test_patch_user_404_for_unknown(env_admin):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.patch("/api/admin/users/missing", json={"tier": "pro"})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_patch_user_noop_returns_row(env_admin):
    """Empty PATCH still returns the canonical row, doesn't bump updated_at."""
    target = _user(id="t2", tier="pro")
    env_admin.db.users["t2"] = target
    prev = target.updated_at
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.patch("/api/admin/users/t2", json={})
    assert r.status_code == 200
    assert target.updated_at == prev  # no mutation, no bump


@pytest.mark.asyncio
async def test_patch_user_restore_clears_deleted_at(env_admin):
    deleted = _user(id="t3", deleted_at=datetime.now(timezone.utc))
    env_admin.db.users["t3"] = deleted
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.patch("/api/admin/users/t3", json={"restore": True})
    assert r.status_code == 200
    assert deleted.deleted_at is None


@pytest.mark.asyncio
async def test_last_admin_cannot_be_demoted(env_admin):
    """When count of remaining admins after demotion would be 0, refuse 400."""
    # The fake's `execute` always returns scalar=0, simulating "no other admins".
    target = _user(id="lone-admin", role="admin")
    env_admin.db.users["lone-admin"] = target
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.patch(
            "/api/admin/users/lone-admin", json={"role": "researcher"}
        )
    assert r.status_code == 400
    assert "last remaining admin" in r.text
    assert target.role == "admin"  # unchanged


# ─── Stats endpoint ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stats_returns_zero_when_db_empty(env_admin):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/admin/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["users_total"] == 0
    assert body["users_by_tier"] == {"free": 0, "pro": 0, "team": 0}
    assert body["source_check_failures_last_24h"] == 0


# ─── Failed-pipelines endpoint ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_failed_pipelines_returns_empty_list_default(env_admin):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/admin/pipelines/failed")
    assert r.status_code == 200
    assert r.json() == []


# ─── Deactivate / Delete / Force sign-out ──────────────────────────────────


@pytest.mark.asyncio
async def test_patch_user_deactivate_sets_timestamp(env_admin):
    target = _user(id="td1", role="researcher")
    env_admin.db.users["td1"] = target
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.patch("/api/admin/users/td1", json={"deactivate": True})
    assert r.status_code == 200
    assert target.deactivated_at is not None


@pytest.mark.asyncio
async def test_patch_user_reactivate_clears_timestamp(env_admin):
    target = _user(
        id="td2",
        role="researcher",
        deactivated_at=datetime.now(timezone.utc),
    )
    env_admin.db.users["td2"] = target
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.patch("/api/admin/users/td2", json={"reactivate": True})
    assert r.status_code == 200
    assert target.deactivated_at is None


@pytest.mark.asyncio
async def test_last_admin_cannot_be_deactivated(env_admin):
    """Same guard pattern as last-admin demote — refuse 400."""
    target = _user(id="lone-2", role="admin")
    env_admin.db.users["lone-2"] = target
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.patch(
            "/api/admin/users/lone-2", json={"deactivate": True}
        )
    assert r.status_code == 400
    assert "last remaining admin" in r.text
    assert target.deactivated_at is None


@pytest.mark.asyncio
async def test_patch_user_delete_sets_deleted_at(env_admin):
    target = _user(id="td3", role="researcher")
    env_admin.db.users["td3"] = target
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.patch("/api/admin/users/td3", json={"delete": True})
    assert r.status_code == 200
    assert target.deleted_at is not None


@pytest.mark.asyncio
async def test_last_admin_cannot_be_deleted(env_admin):
    target = _user(id="lone-3", role="admin")
    env_admin.db.users["lone-3"] = target
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.patch("/api/admin/users/lone-3", json={"delete": True})
    assert r.status_code == 400
    assert "last remaining admin" in r.text
    assert target.deleted_at is None


@pytest.mark.asyncio
async def test_patch_user_force_signout_returns_200(env_admin):
    """Force-signout always returns 200 — the helper's DELETE statements
    are executed via the in-memory fake's no-op execute(), so rowcount
    is None and we just verify the route accepts the flag without 500ing."""
    target = _user(id="td4", role="researcher")
    env_admin.db.users["td4"] = target
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.patch(
            "/api/admin/users/td4", json={"force_signout": True}
        )
    assert r.status_code == 200


# ─── LLM provider status (Phase 9) ────────────────────────────────────────


@pytest.mark.asyncio
async def test_llm_providers_status_returns_all_three(env_admin):
    """GET /api/admin/llm/providers lists every registered provider
    with its primary/fallback/degraded state."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/admin/llm/providers")
    assert r.status_code == 200
    body = r.json()
    assert "primary" in body
    assert "fallback" in body
    assert "providers" in body
    names = sorted(p["name"] for p in body["providers"])
    assert names == ["anthropic", "gemini", "openai"]
    # One of them is the primary
    primaries = [p for p in body["providers"] if p["is_primary"]]
    assert len(primaries) == 1
    assert primaries[0]["name"] == body["primary"]


@pytest.mark.asyncio
async def test_llm_providers_status_requires_admin(env_non_admin):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/admin/llm/providers")
    assert r.status_code == 403
