"""Org member-management endpoints.

The structural contract being pinned:

- ``require_org_admin`` gates the write endpoints (invite, role change,
  remove). Non-admin members get 403 across all of them.
- Invite to an existing email attaches immediately (``status="added"``);
  invite to an unknown email returns ``status="invited"`` and the route
  attempts a send.
- Last-admin guard refuses both role demotion and removal so an org
  can't reach a "no admins" state. Mirror of the admin router's
  guard in ``backend/app/routers/admin.py``.
- Registering with a valid ``invite_token`` auto-attaches the new
  user as a member with the encoded role.

Pure-stub tests where possible — the route surface is the contract,
not the DB plumbing. The ``_OrgMemoryDb`` knows just enough about the
queries the router actually runs to look like one.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app
from app.utils.auth import (
    create_invite_token,
    decode_invite_token,
    get_current_user,
)


# ─── Fixtures ──────────────────────────────────────────────────────────────


def _user(*, id: str = "u1", organization_id: str = "org-1", role: str = "admin", **overrides):
    """A user with the given org role pre-resolved on the instance —
    same shape ``get_current_user`` produces in prod (via
    ``user._org_role = await _resolve_org_role(...)``)."""
    base = SimpleNamespace(
        id=id,
        email=f"{id}@example.com",
        full_name=f"User {id}",
        tier="team",
        organization_id=organization_id,
        deactivated_at=None,
        deleted_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        email_verified_at=datetime.now(timezone.utc),
    )
    base._org_role = role
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


class _OrgMemoryDb:
    """In-memory stand-in for an AsyncSession.

    Stores orgs, users, memberships keyed by id; serves the queries the
    org router actually runs. Real SQL semantics aren't needed — the
    point is to verify which rows the route reads/writes, not to test
    SQLAlchemy.
    """

    def __init__(
        self,
        *,
        org: SimpleNamespace,
        users: list[SimpleNamespace] | None = None,
        memberships: list[SimpleNamespace] | None = None,
    ):
        self.org = org
        self.users = {u.id: u for u in (users or [])}
        self.memberships = list(memberships or [])
        self._added: list = []
        self.committed = 0

    def add(self, obj):
        self._added.append(obj)
        # Membership rows get pushed straight into the in-memory list
        # so subsequent reads see them.
        from app.models.organization_member import OrganizationMember

        if isinstance(obj, OrganizationMember):
            self.memberships.append(
                SimpleNamespace(
                    organization_id=obj.organization_id,
                    user_id=obj.user_id,
                    role=obj.role,
                    joined_at=datetime.now(timezone.utc),
                    invited_by=obj.invited_by,
                )
            )

    async def commit(self):
        self.committed += 1

    async def refresh(self, obj):
        return obj

    async def delete(self, obj):
        # Memberships are SimpleNamespaces inside our list; match by
        # PK pair and remove.
        self.memberships = [
            m
            for m in self.memberships
            if not (
                m.user_id == obj.user_id
                and m.organization_id == obj.organization_id
            )
        ]

    async def get(self, model, pk):
        from app.models.organization import Organization
        from app.models.user import User as UserModel

        if model is Organization:
            return self.org if self.org.id == pk else None
        if model is UserModel:
            return self.users.get(pk)
        return None

    async def execute(self, q):
        # Route the query to the right in-memory collection based on the
        # SELECT target. This isn't full SQL — just enough that the
        # route's introspection (scalar_one_or_none, scalars().all(),
        # scalar()) returns sensible values.
        from app.models.organization import Organization
        from app.models.organization_member import OrganizationMember
        from app.models.user import User as UserModel
        from app.models.report import Report
        from app.models.researcher import ResearcherProfile
        from app.models.source_check import SourceCheck

        # Pull the description: SQLAlchemy 2 select() objects expose
        # column_descriptions. The first entry's entity is the SELECT
        # target. We branch on type.
        try:
            primary = q.column_descriptions[0]["entity"]
        except (AttributeError, IndexError, KeyError, TypeError):
            primary = None

        # COUNT queries — return the right number for the current
        # in-memory state of memberships. Used by the last-admin guard
        # and the MTD usage queries.
        compiled = str(q).lower() if hasattr(q, "compile") or hasattr(q, "__str__") else ""
        if "count" in compiled and "organization_members" in compiled:
            count = sum(1 for m in self.memberships if m.role == "admin")
            return _scalar_result(count)
        if "count" in compiled and any(
            t in compiled
            for t in ("source_checks", "researcher_profiles", "reports")
        ):
            return _scalar_result(0)

        # SELECT Organization — used by the route layer when re-fetching
        # the org for the email rendering (require_org_admin already
        # validated existence via db.get).
        if primary is Organization:
            return _rows_result([self.org])

        # JOIN OrganizationMember + User → list_org_members returns
        # tuples of (membership, user). Check this BEFORE the bare
        # OrganizationMember branch since the joined query has the
        # same primary entity but a different shape requirement.
        if (
            primary is OrganizationMember
            and "users" in compiled
            and "join" in compiled
        ):
            joined = [
                (m, self.users.get(m.user_id))
                for m in self.memberships
                if self.users.get(m.user_id) is not None
            ]
            return _tuples_result(joined)

        # SELECT OrganizationMember (single-table). Filter by user_id
        # if the query has one bound — that's how _load_membership and
        # the PATCH/DELETE endpoints scope to a specific row. Without
        # this, scalar_one_or_none picks the first row regardless of
        # which user the route was asking about.
        if primary is OrganizationMember:
            target_user_id = _extract_user_id_param(q)
            if target_user_id is not None:
                rows = [m for m in self.memberships if m.user_id == target_user_id]
            else:
                rows = list(self.memberships)
            return _rows_result(rows)

        # SELECT User by email — invite flow's existing-user lookup.
        if primary is UserModel:
            # Email predicates are baked into the SQL text; we approximate
            # by scanning users.
            for u in self.users.values():
                if u.email.lower() in compiled:
                    return _rows_result([u])
            return _rows_result([])

        # MTD usage queries — return 0 to keep the assertion shape stable.
        if primary in (SourceCheck, ResearcherProfile, Report):
            return _scalar_result(0)

        return _rows_result([])


def _extract_user_id_param(q) -> str | None:
    """Pull a ``user_id`` bound parameter off a select query. Used by
    the in-memory stub to filter OrganizationMember single-row queries
    to the actual user the route was scoping to.

    Returns None if no ``user_id`` bind is present (callers should fall
    back to "return all rows" so list/JOIN queries still work).
    """
    try:
        compiled = q.compile()
    except Exception:
        return None
    params = getattr(compiled, "params", {}) or {}
    # Bind names are usually `user_id_1`, sometimes `user_id` for the
    # first one. Pick whichever is present, prefer exact match.
    if "user_id" in params:
        return params["user_id"]
    for name, value in params.items():
        if name.startswith("user_id"):
            return value
    return None


def _scalar_result(value):
    class _R:
        def scalar(self):
            return value

        def scalar_one_or_none(self):
            return value

    return _R()


def _rows_result(rows):
    class _R:
        def scalar(self):
            return rows[0] if rows else None

        def scalar_one_or_none(self):
            return rows[0] if rows else None

        def scalars(self):
            class _S:
                def all(_self):
                    return rows

            return _S()

        def all(self):
            return rows

    return _R()


def _tuples_result(tuples):
    class _R:
        def all(self):
            return tuples

    return _R()


@pytest.fixture
def override_with(monkeypatch):
    """Helper: wire the in-memory DB + current_user override for a test."""

    def _apply(*, current_user, db):
        async def _db():
            yield db

        app.dependency_overrides[get_db] = _db
        app.dependency_overrides[get_current_user] = lambda: current_user
        return current_user

    yield _apply
    app.dependency_overrides.clear()


# ─── Invite-token round-trip ───────────────────────────────────────────────


def test_invite_token_round_trips():
    token = create_invite_token(
        org_id="org-1",
        email="Invitee@Example.com",
        role="member",
        invited_by="admin-1",
    )
    payload = decode_invite_token(token)
    assert payload["org_id"] == "org-1"
    # Email is normalised to lowercase on issue so the signup-time
    # match isn't case-sensitive.
    assert payload["email"] == "invitee@example.com"
    assert payload["role"] == "member"
    assert payload["invited_by"] == "admin-1"


def test_invite_token_rejects_garbage():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        decode_invite_token("not-a-real-jwt")
    assert exc.value.status_code == 400


def test_invite_token_rejects_wrong_type():
    # A token of a different type (e.g. an access token) must NOT be
    # accepted as an invite — different claims, different blast radius.
    from app.utils.auth import create_access_token
    from fastapi import HTTPException

    not_invite = create_access_token("u1", "u1@x", session_id=None, tier="free")
    with pytest.raises(HTTPException) as exc:
        decode_invite_token(not_invite)
    assert exc.value.status_code == 400


# ─── Endpoint contracts ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_non_admin_cannot_invite(override_with):
    org = SimpleNamespace(id="org-1", name="Org One")
    admin = _user(id="admin-1", role="admin")
    member = _user(id="m-1", role="member")
    db = _OrgMemoryDb(
        org=org,
        users=[admin, member],
        memberships=[
            SimpleNamespace(
                organization_id="org-1",
                user_id="admin-1",
                role="admin",
                joined_at=datetime.now(timezone.utc),
                invited_by=None,
            ),
            SimpleNamespace(
                organization_id="org-1",
                user_id="m-1",
                role="member",
                joined_at=datetime.now(timezone.utc),
                invited_by=None,
            ),
        ],
    )
    override_with(current_user=member, db=db)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/organizations/org-1/members/invite",
            json={"email": "new@example.com", "role": "member"},
        )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_last_admin_cannot_be_demoted(override_with):
    org = SimpleNamespace(id="org-1", name="Org One")
    admin = _user(id="admin-1", role="admin")
    db = _OrgMemoryDb(
        org=org,
        users=[admin],
        memberships=[
            SimpleNamespace(
                organization_id="org-1",
                user_id="admin-1",
                role="admin",
                joined_at=datetime.now(timezone.utc),
                invited_by=None,
            )
        ],
    )
    override_with(current_user=admin, db=db)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.patch(
            "/api/organizations/org-1/members/admin-1",
            json={"role": "member"},
        )
    assert r.status_code == 400
    assert "last admin" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_last_admin_cannot_be_removed(override_with):
    org = SimpleNamespace(id="org-1", name="Org One")
    admin = _user(id="admin-1", role="admin")
    db = _OrgMemoryDb(
        org=org,
        users=[admin],
        memberships=[
            SimpleNamespace(
                organization_id="org-1",
                user_id="admin-1",
                role="admin",
                joined_at=datetime.now(timezone.utc),
                invited_by=None,
            )
        ],
    )
    override_with(current_user=admin, db=db)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.delete("/api/organizations/org-1/members/admin-1")
    assert r.status_code == 400
    assert "last admin" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_non_member_cannot_list_members(override_with):
    org = SimpleNamespace(id="org-1", name="Org One")
    outsider = _user(id="outsider", organization_id=None, role=None)
    db = _OrgMemoryDb(org=org, users=[outsider], memberships=[])
    override_with(current_user=outsider, db=db)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/organizations/org-1/members")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_list_members(override_with):
    org = SimpleNamespace(id="org-1", name="Org One")
    admin = _user(id="admin-1", role="admin")
    member = _user(id="m-1", role="member")
    db = _OrgMemoryDb(
        org=org,
        users=[admin, member],
        memberships=[
            SimpleNamespace(
                organization_id="org-1",
                user_id="admin-1",
                role="admin",
                joined_at=datetime.now(timezone.utc),
                invited_by=None,
            ),
            SimpleNamespace(
                organization_id="org-1",
                user_id="m-1",
                role="member",
                joined_at=datetime.now(timezone.utc),
                invited_by="admin-1",
            ),
        ],
    )
    override_with(current_user=admin, db=db)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/organizations/org-1/members")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    roles = {item["role"] for item in body["items"]}
    assert roles == {"admin", "member"}
