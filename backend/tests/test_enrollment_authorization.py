"""Regression decisions with stubs; PostgreSQL tests separately prove locking."""

import io
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException, UploadFile
from starlette.requests import Request

from app.models.organization import Organization
from app.models.organization_invite import OrganizationInvite
from app.models.organization_member import OrganizationMember
from app.models.source_check import SourceCheck
from app.models.user import User
from app.routers import organizations, researcher, source_check
from app.schemas.org_member import OrgMemberInvite, OrgMemberRoleUpdate
from app.schemas.researcher import BulkResearcherCreate, ResearcherAnalyzeRequest
from app.schemas.source_check import BulkSourceCheckCreate, SourceCheckCreate


def rows(items=(), value=None):
    return SimpleNamespace(scalar=lambda: value, scalar_one_or_none=lambda: value,
                           scalar_one=lambda: value, scalars=lambda: SimpleNamespace(all=lambda: list(items)))


@pytest.fixture
def enrollment(monkeypatch):
    now = datetime.now(timezone.utc)
    user = SimpleNamespace(id="recipient", organization_id="org", deleted_at=None, deactivated_at=None,
                           _org_role="admin", tier="team", email="recipient@example.com", full_name="Recipient")
    member = SimpleNamespace(organization_id="org", user_id=user.id, role="member")
    org = SimpleNamespace(id="org", name="Lab", seat_limit=10)
    existing = SimpleNamespace(id="old", user_id=user.id, input_type="text", input_content="fixture",
                               original_pdf_path=None, deleted_at=None, input_title="Fixture", status="pending",
                               overall_credibility_score=None, ai_content_percentage=None,
                               misinfo_claims_found=None, created_at=now)
    db = SimpleNamespace(add=Mock(), execute=AsyncMock(), get=AsyncMock(return_value=user),
                         commit=AsyncMock(), refresh=AsyncMock(), delete=AsyncMock())
    def stamp(obj):
        obj.created_at = now
    db.add.side_effect = stamp
    state = SimpleNamespace(user=user, org=org, memberships=[member], db=db)
    async def execute(query):
        entity = query.column_descriptions[0]["entity"]
        if entity is User:
            return rows(value=user)
        if entity is Organization:
            return rows(value=org)
        if entity is OrganizationMember:
            return rows(state.memberships, state.memberships[0] if state.memberships else None)
        return rows(value=existing)
    db.execute.side_effect = execute
    orchestrator = SimpleNamespace(create_check=AsyncMock(return_value="created"))
    state.orchestrator = orchestrator
    monkeypatch.setattr(source_check, "SourceVerificationOrchestrator", lambda db: orchestrator)
    monkeypatch.setattr(source_check, "_check_to_response", lambda check: check)
    monkeypatch.setattr(source_check, "put_pdf", Mock(return_value="fixture-pdf"))
    monkeypatch.setattr(source_check, "assert_quota", AsyncMock())
    monkeypatch.setattr(researcher, "assert_quota", AsyncMock())
    monkeypatch.setattr(researcher, "queue_run", AsyncMock())
    monkeypatch.setattr(researcher, "_profile_to_response", lambda profile: profile)
    from app.tasks import celery_app
    if celery_app is not None:
        monkeypatch.setattr(celery_app, "send_task", Mock())
    return state


async def create(state, endpoint):
    args = {"request": Request({"type": "http", "headers": [], "client": ("127.0.0.1", 1)}),
            "db": state.db, "current_user": state.user}
    if endpoint == "source":
        return await source_check.create_source_check.__wrapped__(**args, data=SourceCheckCreate(input_type="text", input_content="Fixture content"))
    if endpoint == "upload":
        return await source_check.upload_pdf_source_check.__wrapped__(**args, file=UploadFile(filename="fixture.pdf", file=io.BytesIO(b"%PDF-" + b"x" * 2048)))
    if endpoint == "source_bulk":
        return await source_check.create_bulk_source_checks.__wrapped__(**args, data=BulkSourceCheckCreate(items=[{"input_type": "text", "input_content": "Fixture content"}]))
    if endpoint == "rerun":
        return await source_check.rerun_source_check.__wrapped__(**args, check_id="old")
    if endpoint == "researcher":
        return await researcher.analyze_researcher.__wrapped__(**args, data=ResearcherAnalyzeRequest(researcher_name="Fixture"))
    return await researcher.create_bulk_researcher_analyses.__wrapped__(**args, data=BulkResearcherCreate(items=[{"researcher_name": "Fixture"}]))


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["source", "upload", "source_bulk", "rerun", "researcher", "researcher_bulk"])
@pytest.mark.parametrize("defect", ["pointer_only", "mismatch", "membership_without_pointer", "inactive"])
async def test_creation_rejects_unauthorized_scope_before_writing(enrollment, endpoint, defect):
    s = enrollment
    if defect == "pointer_only":
        s.memberships = []
    elif defect == "mismatch":
        s.memberships[0].organization_id = "other-org"
    elif defect == "membership_without_pointer":
        s.user.organization_id = None
    else:
        s.user.deactivated_at = datetime.now(timezone.utc)
    with pytest.raises(HTTPException) as error:
        await create(s, endpoint)
    assert error.value.status_code == 403
    s.db.add.assert_not_called()
    s.orchestrator.create_check.assert_not_awaited()
    s.db.commit.assert_not_awaited()
    source_check.put_pdf.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["source", "upload", "source_bulk", "rerun", "researcher", "researcher_bulk"])
@pytest.mark.parametrize("scope", ["personal", "member"])
async def test_creation_accepts_personal_or_valid_active_membership(enrollment, endpoint, scope):
    s = enrollment
    if scope == "personal":
        s.user.organization_id, s.memberships = None, []
    await create(s, endpoint)
    expected = None if scope == "personal" else "org"
    if endpoint in ("researcher", "researcher_bulk"):
        assert s.db.add.call_args.args[0].organization_id == expected
    else:
        assert s.orchestrator.create_check.call_args.kwargs["organization_id"] == expected
    assert s.user._org_role == (None if scope == "personal" else "member")


@pytest.mark.asyncio
async def test_creation_never_silently_falls_back_to_personal_after_concurrent_removal(enrollment):
    s = enrollment
    original_execute = s.db.execute.side_effect
    async def concurrent_removal(query):
        if query.column_descriptions[0]["entity"] is User:
            # populate_existing updates the very same ORM identity loaded by
            # authentication, as a real post-lock refresh would.
            s.user.organization_id, s.memberships = None, []
        return await original_execute(query)
    s.db.execute.side_effect = concurrent_removal
    with pytest.raises(HTTPException) as error:
        await create(s, "source")
    assert error.value.status_code == 403
    s.orchestrator.create_check.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["invite", "resend", "revoke", "role", "remove"])
@pytest.mark.parametrize("change", ["removed", "demoted"])
async def test_stale_admin_dependency_is_reauthorized_after_org_lock(enrollment, monkeypatch, action, change):
    s = enrollment
    cached_admin = SimpleNamespace(user_id="admin", organization_id="org", role="admin")
    target = SimpleNamespace(user_id="target", organization_id="org", role="member",
                             joined_at=datetime.now(timezone.utc), invited_by=None)
    invite = SimpleNamespace(id="invite", organization_id="org", email="new@example.com", token="token",
                             status="pending", revoked_at=None, expires_at=datetime.now(timezone.utc) + timedelta(days=7))
    async def execute(query):
        sql = str(query)
        params = query.compile().params
        if "count(" in sql:
            return rows(value=0)
        entity = query.column_descriptions[0]["entity"]
        if entity is Organization:
            return rows(value=s.org)
        if entity is User:
            return rows(value=s.user)
        if entity is OrganizationMember:
            # The early dependency already authorized cached_admin. A fresh
            # lookup must see that actor was removed, not use the cached row.
            if "admin" in params.values():
                assert query.get_execution_options()["populate_existing"] is True
                return rows(value=None if change == "removed" else SimpleNamespace(user_id="admin", role="member"))
            return rows(value=target)
        return rows()
    s.db.execute.side_effect = execute
    async def get(model, pk, **kwargs):
        if model is OrganizationInvite:
            return invite
        return s.org if model is Organization else s.user
    s.db.get.side_effect = get
    monkeypatch.setattr(organizations, "send_email", AsyncMock(return_value=True))
    kwargs = {"org_id": "org", "db": s.db, "admin_membership": cached_admin}
    request = Request({"type": "http", "headers": [], "client": ("127.0.0.1", 1)})
    with pytest.raises(HTTPException) as error:
        if action == "invite":
            await organizations.invite_org_member.__wrapped__(request=request, data=OrgMemberInvite(email="new@example.com"), **kwargs)
        elif action == "resend":
            await organizations.resend_org_invite.__wrapped__(request=request, invite_id="invite", **kwargs)
        elif action == "revoke":
            await organizations.revoke_org_invite(invite_id="invite", **kwargs)
        elif action == "role":
            await organizations.update_org_member_role(user_id="target", data=OrgMemberRoleUpdate(role="admin"), **kwargs)
        else:
            await organizations.remove_org_member(user_id="target", **kwargs)
    assert error.value.status_code == 403
    s.db.add.assert_not_called()
    s.db.commit.assert_not_awaited()
    s.db.delete.assert_not_awaited()
    organizations.send_email.assert_not_awaited()
