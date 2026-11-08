"""Security regressions. Stubs verify route decisions/SQL, not PostgreSQL locks."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.deps.org import require_org_admin
from app.main import app
from app.models.organization_member import OrganizationMember
from app.routers import analytics, organizations
from app.utils.auth import create_invite_token, get_current_user


def result(value=None, rows=()):
    return SimpleNamespace(
        scalar=lambda: value, scalar_one_or_none=lambda: value,
        scalars=lambda: SimpleNamespace(all=lambda: list(rows), first=lambda: rows[0] if rows else None),
        all=lambda: list(rows),
    )


@pytest.fixture
def scenario(monkeypatch):
    now = datetime.now(timezone.utc)
    user = SimpleNamespace(id="recipient", email="recipient@example.com", organization_id=None,
                           email_verified_at=now, deleted_at=None, deactivated_at=None, tier="free", full_name="Recipient")
    org = SimpleNamespace(id="org", name="Lab", seat_limit=10)
    token = create_invite_token(org_id=org.id, email=user.email, role="member", invited_by="admin")
    invite = SimpleNamespace(id="invite", organization_id=org.id, email=user.email, role="member",
                             invited_by="admin", token=token, status="pending", expires_at=now + timedelta(days=7),
                             revoked_at=None, accepted_at=None)
    db = SimpleNamespace(execute=AsyncMock(), get=AsyncMock(return_value=org), add=Mock(),
                         flush=AsyncMock(), commit=AsyncMock(), refresh=AsyncMock(), rollback=AsyncMock())
    async def dependency():
        yield db
    app.dependency_overrides[get_db] = dependency
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_org_admin] = lambda: SimpleNamespace(user_id="admin", role="admin")
    monkeypatch.setattr(organizations, "send_email", AsyncMock(return_value=True))
    yield SimpleNamespace(user=user, org=org, invite=invite, token=token, db=db)
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_inviting_existing_account_never_attaches_or_discloses_existence(scenario):
    s = scenario
    # Existing-user query on the vulnerable path MUST return a real recipient.
    async def execute(q):
        sql = str(q)
        if "count(" in sql:
            return result(0)
        if q.column_descriptions[0]["entity"] is OrganizationMember:
            return result(SimpleNamespace(user_id="admin", organization_id="org", role="admin"))
        if "FROM users" in sql:
            return result(s.user)
        if "FROM organizations" in sql:
            return result(s.org)
        if "count(" in sql:
            return result(0)
        return result()
    s.db.execute.side_effect = execute
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/organizations/org/members/invite", json={"email": s.user.email})
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "invited"
    assert s.user.organization_id is None
    assert not any(isinstance(call.args[0], OrganizationMember) for call in s.db.add.call_args_list)


@pytest.mark.asyncio
async def test_activity_queries_require_resource_org(scenario):
    s = scenario
    s.user.tier, s.user.organization_id, s.user._org_role = "team", "org", "member"
    s.db.execute.side_effect = [result(rows=[(s.user.id, "Recipient", s.user.email)]), result(), result(), result()]
    await analytics.get_team_activity(db=s.db, current_user=s.user)
    queries = [str(call.args[0]) for call in s.db.execute.call_args_list]
    for table in ("source_checks", "researcher_profiles", "reports"):
        query = next(q for q in queries if f"FROM {table}" in q)
        assert f"{table}.organization_id =" in query


@pytest.mark.asyncio
async def test_member_usage_requires_resource_org(scenario):
    s = scenario
    s.db.execute.return_value = result(0)
    # Inspect the public roster path so the organization must be passed through.
    member = SimpleNamespace(role="member", joined_at=datetime.now(timezone.utc), invited_by="admin")
    s.user.full_name = "Recipient"
    s.db.execute.side_effect = [result(rows=[(member, s.user)]), result(0), result(0), result(0)]
    await organizations.list_org_members(org_id="org", db=s.db, _=member)
    for call in s.db.execute.call_args_list[1:]:
        sql = str(call.args[0])
        assert ".organization_id =" in sql


@pytest.mark.asyncio
async def test_authenticated_recipient_can_explicitly_accept(scenario):
    s = scenario
    s.db.execute.side_effect = [result(s.user), result(s.org), result(s.invite), result(rows=[]), result(0)]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/organizations/org/invites/accept", json={"token": s.token})
    assert response.status_code == 200, response.text
    assert s.user.organization_id == "org"
    assert s.invite.status == "accepted"
    assert sum(isinstance(c.args[0], OrganizationMember) for c in s.db.add.call_args_list) == 1


@pytest.mark.asyncio
async def test_get_invitation_is_never_acceptance(scenario):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/organizations/org/invites/accept", params={"token": scenario.token})
    assert response.status_code in (404, 405)
    scenario.db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_registration_rejects_invite_without_persistent_row_before_creating_user(scenario):
    s = scenario
    s.db.execute.return_value = result()
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test") as client:
        response = await client.post("/api/auth/register", json={
            "email": s.user.email, "password": "regression-password", "full_name": "Recipient",
            "invite_token": s.token,
        })
    assert response.status_code == 400, response.text
    s.db.add.assert_not_called()
    s.db.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("change,status", [
    ("wrong_email", 400), ("wrong_org", 400), ("revoked", 400), ("expired", 400),
    ("missing", 400), ("different_token", 400), ("invalid_role", 400), ("role_mismatch", 400),
    ("unverified", 403), ("inactive", 403), ("other_org", 409), ("other_membership", 409),
    ("full", 409), ("accepted_without_membership", 400),
])
async def test_acceptance_rejects_without_mutation(scenario, change, status):
    from app.services.team_invites import accept_invite
    s = scenario
    memberships, seats = [], 0
    if change == "wrong_email":
        s.user.email = "other@example.com"
    elif change == "wrong_org":
        s.invite.organization_id = "different"
    elif change == "revoked":
        s.invite.status, s.invite.revoked_at = "revoked", datetime.now(timezone.utc)
    elif change == "expired":
        s.invite.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    elif change == "different_token":
        s.invite.token = "other-token"
    elif change == "invalid_role":
        s.invite.role = "superadmin"
    elif change == "role_mismatch":
        s.invite.role = "admin"
    elif change == "unverified":
        s.user.email_verified_at = None
    elif change == "inactive":
        s.user.deactivated_at = datetime.now(timezone.utc)
    elif change == "other_org":
        s.user.organization_id = "other"
    elif change == "other_membership":
        memberships = [SimpleNamespace(organization_id="other")]
    elif change == "full":
        seats = s.org.seat_limit
    elif change == "accepted_without_membership":
        s.invite.status = "accepted"
    previous_org = s.user.organization_id
    s.db.execute.side_effect = [result(s.user), result(s.org), result(None if change == "missing" else s.invite),
                                result(rows=memberships), result(seats if change != "accepted_without_membership" else None)]
    with pytest.raises(HTTPException) as error:
        await accept_invite(s.db, user_id=s.user.id, org_id="org", token=s.token)
    assert error.value.status_code == status
    assert s.user.organization_id == previous_org
    s.db.add.assert_not_called()
    s.db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_replay_acknowledges_only_original_account_and_never_restores_role(scenario):
    from app.services.team_invites import accept_invite
    s = scenario
    s.user.organization_id, s.invite.status = "org", "accepted"
    member = SimpleNamespace(organization_id="org", role="member")
    s.db.execute.side_effect = [result(s.user), result(s.org), result(s.invite), result(rows=[member]), result(object())]
    await accept_invite(s.db, user_id=s.user.id, org_id="org", token=s.token)
    s.db.add.assert_not_called()
    assert member.role == "member"


@pytest.mark.asyncio
async def test_invitation_preview_is_authenticated_read_only(scenario):
    s = scenario
    s.db.execute.side_effect = [result(s.org), result(s.invite)]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/organizations/invites/preview", json={"token": s.token})
    assert response.status_code == 200, response.text
    assert response.json() == {"organization_id": "org", "name": "Lab", "role": "member"}
    s.db.add.assert_not_called()
    s.db.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("has_invite", [False, True])
async def test_legitimate_registration_creates_account_but_never_joins(scenario, monkeypatch, has_invite):
    from app.routers import auth
    s = scenario
    s.db.execute.side_effect = [result(), result(s.invite)] if has_invite else [result()]
    # Session/SMTP/password implementations are outside this route decision
    # test. Full signup + verification + browser acceptance remains an E2E gate.
    monkeypatch.setattr(auth.bcrypt, "hash", lambda password: "fixture-hash")
    monkeypatch.setattr(auth, "issue_login_token", AsyncMock(return_value=("fixture-access-token", None)))
    monkeypatch.setattr(auth, "_send_initial_verification_email", AsyncMock())
    monkeypatch.setattr(auth, "_user_to_response", lambda user: {
        "id": user.id, "email": user.email, "full_name": user.full_name, "role": user.role,
        "created_at": datetime.now(timezone.utc),
    })
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/auth/register", json={
            "email": s.user.email, "password": "registration-password", "full_name": "Recipient",
            **({"invite_token": s.token} if has_invite else {}),
        })
    assert response.status_code == 201, response.text
    assert response.json()["user"]["organization_id"] is None
    assert s.invite.status == "pending"
    assert not any(isinstance(c.args[0], OrganizationMember) for c in s.db.add.call_args_list)
    auth._send_initial_verification_email.assert_awaited_once()


@pytest.mark.asyncio
async def test_acceptance_requires_authentication(scenario):
    app.dependency_overrides.pop(get_current_user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/organizations/org/invites/accept", json={"token": scenario.token})
    assert response.status_code in (401, 403)
    scenario.db.add.assert_not_called()


@pytest.mark.asyncio
async def test_replay_with_a_different_account_audit_is_rejected(scenario):
    from app.services.team_invites import accept_invite
    s = scenario
    s.user.organization_id, s.invite.status = "org", "accepted"
    s.db.execute.side_effect = [result(s.user), result(s.org), result(s.invite),
                                result(rows=[SimpleNamespace(organization_id="org")]), result()]
    with pytest.raises(HTTPException) as error:
        await accept_invite(s.db, user_id=s.user.id, org_id="org", token=s.token)
    assert error.value.status_code == 400
    s.db.add.assert_not_called()
