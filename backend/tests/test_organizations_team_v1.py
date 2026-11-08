"""Team-plan v1 contracts for the Organizations router.

Three things the new code adds that need pinning:

1. Self-serve trial creation: POST /api/organizations creates an Org,
   promotes the caller to ``tier="team"`` + ``org_role="admin"``, stamps
   a trial expiry, and refuses if the user is already in an org.

2. Pending invites: GET lists pending, POST resend re-mails without
   re-issuing the token, DELETE revokes (idempotent for non-pending).

3. Audit log: GET /api/organizations/{id}/audit-log is admin-only and
   pages the ``organization_audit_logs`` rows the other endpoints write.

The tests use a focused in-memory ``_TeamDb`` rather than extending the
older ``_OrgMemoryDb`` in ``test_org_members.py`` because the new
endpoints touch two extra tables (invites + audit log) and dragging
those into the legacy stub would risk regressing existing tests.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Optional
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app
from app.utils.auth import get_current_user


def _user(
    *,
    id: str = "u1",
    organization_id: Optional[str] = None,
    org_role: Optional[str] = None,
    tier: str = "free",
    **overrides,
):
    base = SimpleNamespace(
        id=id,
        email=f"{id}@example.com",
        full_name=f"User {id}",
        tier=tier,
        organization_id=organization_id,
        deactivated_at=None,
        deleted_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        email_verified_at=datetime.now(timezone.utc),
    )
    # The auth dep resolves this onto the user instance in prod; the
    # require_org_* deps read it for the role gate.
    base._org_role = org_role
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


def _membership(*, org_id: str, user_id: str, role: str = "member"):
    return SimpleNamespace(
        organization_id=org_id,
        user_id=user_id,
        role=role,
        joined_at=datetime.now(timezone.utc),
        invited_by=None,
    )


def _invite(*, org_id: str, email: str, status: str = "pending"):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=f"inv-{email}",
        organization_id=org_id,
        email=email,
        role="member",
        token="signed-token-" + email,
        status=status,
        invited_by="admin-1",
        created_at=now,
        expires_at=now + timedelta(days=7),
        accepted_at=None,
        revoked_at=None,
    )


def _audit_row(*, org_id: str, action: str, idx: int, actor_id: Optional[str] = None):
    return SimpleNamespace(
        id=f"aud-{idx}",
        organization_id=org_id,
        actor_user_id=actor_id,
        action=action,
        target_user_id=None,
        payload={},
        created_at=datetime.now(timezone.utc) - timedelta(seconds=idx),
    )


class _TeamDb:
    """Focused in-memory db for the team-v1 endpoint tests.

    Routes queries by the SELECT entity to in-memory collections.
    Tracks `added` and `committed` so tests can assert "the route wrote
    an Organization + a Member + an audit row before commit".
    """

    def __init__(
        self,
        *,
        orgs: Optional[list[SimpleNamespace]] = None,
        users: Optional[list[SimpleNamespace]] = None,
        memberships: Optional[list[SimpleNamespace]] = None,
        invites: Optional[list[SimpleNamespace]] = None,
        audit_rows: Optional[list[SimpleNamespace]] = None,
    ):
        self.orgs = {o.id: o for o in (orgs or [])}
        self.users = {u.id: u for u in (users or [])}
        self.memberships = list(memberships or [])
        self.invites = list(invites or [])
        self.audit_rows = list(audit_rows or [])
        self.added: list = []
        self.committed = 0

    # SQLAlchemy session-like surface
    def add(self, obj):
        self.added.append(obj)
        from app.models.organization import Organization
        from app.models.organization_audit_log import OrganizationAuditLog
        from app.models.organization_invite import OrganizationInvite
        from app.models.organization_member import OrganizationMember

        if isinstance(obj, Organization):
            self.orgs[obj.id] = obj
        elif isinstance(obj, OrganizationMember):
            self.memberships.append(
                SimpleNamespace(
                    organization_id=obj.organization_id,
                    user_id=obj.user_id,
                    role=obj.role,
                    joined_at=datetime.now(timezone.utc),
                    invited_by=obj.invited_by,
                )
            )
        elif isinstance(obj, OrganizationInvite):
            self.invites.append(
                SimpleNamespace(
                    id=obj.id,
                    organization_id=obj.organization_id,
                    email=obj.email,
                    role=obj.role,
                    token=obj.token,
                    status=obj.status,
                    invited_by=obj.invited_by,
                    created_at=obj.created_at,
                    expires_at=obj.expires_at,
                    accepted_at=None,
                    revoked_at=None,
                )
            )
        elif isinstance(obj, OrganizationAuditLog):
            self.audit_rows.append(
                SimpleNamespace(
                    id=obj.id,
                    organization_id=obj.organization_id,
                    actor_user_id=obj.actor_user_id,
                    action=obj.action,
                    target_user_id=obj.target_user_id,
                    payload=obj.payload,
                    created_at=datetime.now(timezone.utc),
                )
            )

    async def flush(self):
        return None

    async def commit(self):
        self.committed += 1

    async def refresh(self, obj):
        return obj

    async def delete(self, obj):
        # Remove invite row by id.
        from app.models.organization_invite import OrganizationInvite
        from app.models.organization_member import OrganizationMember

        if isinstance(obj, OrganizationMember):
            self.memberships = [
                m
                for m in self.memberships
                if not (
                    m.organization_id == obj.organization_id
                    and m.user_id == obj.user_id
                )
            ]
        elif isinstance(obj, OrganizationInvite):
            self.invites = [i for i in self.invites if i.id != obj.id]

    async def get(self, model, pk, **kwargs):
        from app.models.organization import Organization
        from app.models.organization_invite import OrganizationInvite
        from app.models.user import User as UserModel

        if model is Organization:
            return self.orgs.get(pk)
        if model is OrganizationInvite:
            for inv in self.invites:
                if inv.id == pk:
                    return inv
            return None
        if model is UserModel:
            return self.users.get(pk)
        return None

    async def execute(self, q):
        from app.models.organization import Organization
        from app.models.organization_audit_log import OrganizationAuditLog
        from app.models.organization_invite import OrganizationInvite
        from app.models.organization_member import OrganizationMember
        from app.models.report import Report
        from app.models.researcher import ResearcherProfile
        from app.models.source_check import SourceCheck
        from app.models.user import User as UserModel

        compiled = str(q).lower()

        try:
            primary = q.column_descriptions[0]["entity"]
        except Exception:
            primary = None

        # COUNT — discriminate by table referenced.
        if "count" in compiled:
            if "organization_invites" in compiled:
                pending = sum(1 for i in self.invites if i.status == "pending")
                return _scalar_result(pending)
            if "organization_members" in compiled:
                if "role" in compiled and "admin" in compiled:
                    return _scalar_result(
                        sum(1 for m in self.memberships if m.role == "admin")
                    )
                return _scalar_result(len(self.memberships))
            if "organization_audit_logs" in compiled:
                return _scalar_result(len(self.audit_rows))
            if any(
                t in compiled
                for t in ("source_checks", "researcher_profiles", "reports")
            ):
                return _scalar_result(0)
            return _scalar_result(0)

        if primary is Organization:
            return _rows_result(list(self.orgs.values()))
        if primary is OrganizationInvite:
            # Pending-list endpoint filters on status == "pending"; return
            # only those when the SQL mentions it.
            if "status" in compiled and "pending" in compiled and "expires_at" not in compiled:
                return _rows_result(
                    [i for i in self.invites if i.status == "pending"]
                )
            if "expires_at" in compiled:
                # Expire-sweep query in list endpoint.
                now = datetime.now(timezone.utc)
                return _rows_result(
                    [
                        i
                        for i in self.invites
                        if i.status == "pending" and i.expires_at < now
                    ]
                )
            return _rows_result(list(self.invites))
        if primary is OrganizationMember:
            target_user_id = _bind_param(q, "user_id")
            if target_user_id is not None:
                return _rows_result(
                    [m for m in self.memberships if m.user_id == target_user_id]
                )
            if "users" in compiled and "join" in compiled:
                return _tuples_result(
                    [
                        (m, self.users.get(m.user_id))
                        for m in self.memberships
                        if self.users.get(m.user_id) is not None
                    ]
                )
            return _rows_result(list(self.memberships))
        if primary is OrganizationAuditLog:
            return _tuples_result(
                [(r, None, None) for r in self.audit_rows]
            )
        if primary is UserModel:
            user_id = _bind_param(q, "id")
            if user_id is not None:
                user = self.users.get(user_id)
                return _rows_result([user] if user else [])
            for u in self.users.values():
                if u.email.lower() in compiled or u.id in compiled:
                    return _rows_result([u])
            return _rows_result([])
        if primary in (SourceCheck, ResearcherProfile, Report):
            return _scalar_result(0)
        return _rows_result([])


def _bind_param(q, name: str) -> Optional[str]:
    try:
        compiled = q.compile()
    except Exception:
        return None
    params = getattr(compiled, "params", {}) or {}
    if name in params:
        return params[name]
    for k, v in params.items():
        if k.startswith(name + "_"):
            return v
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

                def first(_self):
                    return rows[0] if rows else None

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
def override_with():
    def _apply(*, current_user, db):
        async def _db():
            yield db

        app.dependency_overrides[get_db] = _db
        app.dependency_overrides[get_current_user] = lambda: current_user
        return current_user

    yield _apply
    app.dependency_overrides.clear()


# ─── POST /api/organizations — self-serve trial ───────────────────────────


@pytest.mark.asyncio
async def test_self_serve_create_org_promotes_user_and_returns_detail(
    override_with, monkeypatch
):
    """Happy path: a free-tier user with no org creates one, gets
    bumped to ``tier="team"``, becomes admin, and the response carries
    the trial flag + seat counts."""
    # Stub out send_email so the email-rendering branch never runs in
    # the create path (it doesn't, but the global side effect should
    # stay clean).
    user = _user(id="u-creator", organization_id=None, tier="free")
    db = _TeamDb(users=[user])
    override_with(current_user=user, db=db)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/organizations",
            json={"name": "My Research Lab"},
        )

    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "My Research Lab"
    assert body["is_trial"] is True
    assert body["trial_ends_at"] is not None
    assert body["seat_limit"] == 10
    assert body["seat_used"] == 1  # the creator
    assert body["seat_remaining"] == 9
    assert body["current_user_role"] == "admin"
    # User was promoted in-place.
    assert user.tier == "team"
    assert user.organization_id == body["id"]
    # Audit row was written.
    actions = [r.action for r in db.audit_rows]
    assert "org_created" in actions


@pytest.mark.asyncio
async def test_self_serve_refuses_if_already_in_org(override_with):
    user = _user(id="u-existing", organization_id="org-1", tier="team")
    db = _TeamDb(users=[user])
    override_with(current_user=user, db=db)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/organizations", json={"name": "Second Org"})
    assert r.status_code == 409
    assert "already belong" in r.json()["detail"].lower()


# ─── GET /api/organizations/{id} ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_org_returns_seat_usage(override_with):
    org = SimpleNamespace(
        id="org-1",
        name="Org",
        slug="org",
        contact_email=None,
        seat_limit=10,
        is_trial=False,
        trial_ends_at=None,
        created_at=datetime.now(timezone.utc),
        logo_url=None,
        primary_color=None,
        secondary_color=None,
        updated_at=datetime.now(timezone.utc),
    )
    admin = _user(id="admin-1", organization_id="org-1", tier="team", org_role="admin")
    member = _user(id="m-1", organization_id="org-1", tier="team", org_role="member")
    db = _TeamDb(
        orgs=[org],
        users=[admin, member],
        memberships=[
            _membership(org_id="org-1", user_id="admin-1", role="admin"),
            _membership(org_id="org-1", user_id="m-1", role="member"),
        ],
    )
    override_with(current_user=admin, db=db)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/organizations/org-1")
    assert r.status_code == 200
    body = r.json()
    assert body["seat_used"] == 2
    assert body["seat_remaining"] == 8
    assert body["current_user_role"] == "admin"


# ─── PATCH /api/organizations/{id} ───────────────────────────────────────


@pytest.mark.asyncio
async def test_patch_org_settings_writes_audit_and_returns_detail(override_with):
    org = SimpleNamespace(
        id="org-1",
        name="Old Name",
        slug="org",
        contact_email=None,
        seat_limit=10,
        is_trial=False,
        trial_ends_at=None,
        created_at=datetime.now(timezone.utc),
        logo_url=None,
        primary_color=None,
        secondary_color=None,
        updated_at=datetime.now(timezone.utc),
    )
    admin = _user(id="admin-1", organization_id="org-1", tier="team", org_role="admin")
    db = _TeamDb(
        orgs=[org],
        users=[admin],
        memberships=[_membership(org_id="org-1", user_id="admin-1", role="admin")],
    )
    override_with(current_user=admin, db=db)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.patch(
            "/api/organizations/org-1",
            json={"name": "New Name", "contact_email": "ops@example.com"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "New Name"
    assert body["contact_email"] == "ops@example.com"
    actions = [r.action for r in db.audit_rows]
    assert "org_settings_changed" in actions


# ─── Pending invites: list / resend / revoke ─────────────────────────────


@pytest.mark.asyncio
async def test_list_invites_admin_only(override_with):
    org = SimpleNamespace(
        id="org-1", name="Org", slug="org",
        contact_email=None, seat_limit=10, is_trial=False,
        trial_ends_at=None, created_at=datetime.now(timezone.utc),
        logo_url=None, primary_color=None, secondary_color=None,
        updated_at=datetime.now(timezone.utc),
    )
    admin = _user(id="admin-1", organization_id="org-1", tier="team", org_role="admin")
    member = _user(id="m-1", organization_id="org-1", tier="team", org_role="member")
    db = _TeamDb(
        orgs=[org],
        users=[admin, member],
        memberships=[
            _membership(org_id="org-1", user_id="admin-1", role="admin"),
            _membership(org_id="org-1", user_id="m-1", role="member"),
        ],
        invites=[
            _invite(org_id="org-1", email="pending1@example.com"),
            _invite(org_id="org-1", email="pending2@example.com"),
        ],
    )

    # Non-admin denied
    override_with(current_user=member, db=db)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/organizations/org-1/invites")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_revoke_invite_flips_status_and_audits(override_with):
    org = SimpleNamespace(
        id="org-1", name="Org", slug="org",
        contact_email=None, seat_limit=10, is_trial=False,
        trial_ends_at=None, created_at=datetime.now(timezone.utc),
        logo_url=None, primary_color=None, secondary_color=None,
        updated_at=datetime.now(timezone.utc),
    )
    admin = _user(id="admin-1", organization_id="org-1", tier="team", org_role="admin")
    pending = _invite(org_id="org-1", email="ghost@example.com")
    db = _TeamDb(
        orgs=[org],
        users=[admin],
        memberships=[_membership(org_id="org-1", user_id="admin-1", role="admin")],
        invites=[pending],
    )
    override_with(current_user=admin, db=db)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.delete(f"/api/organizations/org-1/invites/{pending.id}")
    assert r.status_code == 204
    assert pending.status == "revoked"
    assert pending.revoked_at is not None
    assert any(r.action == "invite_revoked" for r in db.audit_rows)


@pytest.mark.asyncio
async def test_revoke_already_revoked_is_idempotent(override_with):
    org = SimpleNamespace(
        id="org-1", name="Org", slug="org",
        contact_email=None, seat_limit=10, is_trial=False,
        trial_ends_at=None, created_at=datetime.now(timezone.utc),
        logo_url=None, primary_color=None, secondary_color=None,
        updated_at=datetime.now(timezone.utc),
    )
    admin = _user(id="admin-1", organization_id="org-1", tier="team", org_role="admin")
    revoked = _invite(org_id="org-1", email="ghost@example.com", status="revoked")
    db = _TeamDb(
        orgs=[org],
        users=[admin],
        memberships=[_membership(org_id="org-1", user_id="admin-1", role="admin")],
        invites=[revoked],
    )
    override_with(current_user=admin, db=db)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.delete(f"/api/organizations/org-1/invites/{revoked.id}")
    assert r.status_code == 204  # idempotent — no error


# ─── Audit log ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_audit_log_admin_only(override_with):
    org = SimpleNamespace(
        id="org-1", name="Org", slug="org",
        contact_email=None, seat_limit=10, is_trial=False,
        trial_ends_at=None, created_at=datetime.now(timezone.utc),
        logo_url=None, primary_color=None, secondary_color=None,
        updated_at=datetime.now(timezone.utc),
    )
    member = _user(id="m-1", organization_id="org-1", tier="team", org_role="member")
    db = _TeamDb(
        orgs=[org],
        users=[member],
        memberships=[_membership(org_id="org-1", user_id="m-1", role="member")],
    )
    override_with(current_user=member, db=db)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/organizations/org-1/audit-log")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_audit_log_returns_paged_response(override_with):
    org = SimpleNamespace(
        id="org-1", name="Org", slug="org",
        contact_email=None, seat_limit=10, is_trial=False,
        trial_ends_at=None, created_at=datetime.now(timezone.utc),
        logo_url=None, primary_color=None, secondary_color=None,
        updated_at=datetime.now(timezone.utc),
    )
    admin = _user(id="admin-1", organization_id="org-1", tier="team", org_role="admin")
    db = _TeamDb(
        orgs=[org],
        users=[admin],
        memberships=[_membership(org_id="org-1", user_id="admin-1", role="admin")],
        audit_rows=[
            _audit_row(org_id="org-1", action="invite_sent", idx=1),
            _audit_row(org_id="org-1", action="member_added", idx=2),
        ],
    )
    override_with(current_user=admin, db=db)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/organizations/org-1/audit-log")
    assert r.status_code == 200
    body = r.json()
    assert body["page"] == 1
    assert body["page_size"] == 50
    assert body["total"] == 2
    actions = {item["action"] for item in body["items"]}
    assert actions == {"invite_sent", "member_added"}


# ─── Audit service unit test ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_record_org_action_writes_row_and_does_not_commit():
    """The chokepoint adds a row but never commits — caller's job."""
    from app.services.org_audit import record_org_action

    db = _TeamDb()
    await record_org_action(
        db=db,
        org_id="org-1",
        actor_user_id="admin-1",
        action="invite_sent",
        target_user_id=None,
        payload={"email": "x@y.com", "role": "member"},
    )
    assert db.committed == 0  # service does not commit
    assert len(db.audit_rows) == 1
    assert db.audit_rows[0].action == "invite_sent"
    assert db.audit_rows[0].payload == {"email": "x@y.com", "role": "member"}
