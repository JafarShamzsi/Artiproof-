"""Opt-in PostgreSQL consent/isolation acceptance; never substitutes SQLite.

Run against an explicitly designated, migrated disposable database:
  pytest -m integration tests/test_team_consent_integration.py
Only UUID-owned fixture rows are removed; no shared-table truncation.
"""

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.models.organization import Organization
from app.models.organization_audit_log import OrganizationAuditLog
from app.models.organization_invite import OrganizationInvite
from app.models.organization_member import OrganizationMember
from app.models.report import Report
from app.models.researcher import ResearcherProfile
from app.models.source_check import SourceCheck
from app.models.user import User
from app.routers.analytics import get_team_activity
from app.routers.organizations import _usage_for_member
from app.services.team_invites import accept_invite, lock_org
from app.utils.auth import create_invite_token

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture
async def team_database():
    url = os.getenv("ARTIPROOF_INTEGRATION_DATABASE_URL")
    if not url:
        pytest.skip("Set ARTIPROOF_INTEGRATION_DATABASE_URL to a dedicated migrated PostgreSQL database")
    if not url.startswith("postgresql+asyncpg://"):
        pytest.fail("Consent tests require PostgreSQL via asyncpg; no SQLite substitution")
    engine = create_async_engine(url, poolclass=NullPool, isolation_level="READ COMMITTED")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    users = [str(uuid.uuid4()) for _ in range(4)]
    orgs = [str(uuid.uuid4()) for _ in range(2)]
    now = datetime.now(timezone.utc)
    try:
        async with sessions() as db:
            db.add_all([Organization(id=oid, name="Consent fixture", slug=f"consent-{oid}", seat_limit=2)
                        for oid in orgs])
            await db.flush()
            db.add_all([User(id=uid, email=f"consent-{uid}@integration.invalid", full_name="Consent fixture",
                             email_verified_at=now, organization_id=orgs[i] if i < 2 else None,
                             tier="team", share_activity_with_team=True) for i, uid in enumerate(users)])
            await db.flush()
            db.add_all([OrganizationMember(organization_id=oid, user_id=users[i], role="admin")
                        for i, oid in enumerate(orgs)])
            await db.commit()
        yield sessions, users, orgs
    finally:
        async with sessions() as db:
            for model in (Report, ResearcherProfile, SourceCheck):
                await db.execute(sa.delete(model).where(model.user_id.in_(users)))
            # Pointer FKs must be cleared before deleting the fixture organizations.
            await db.execute(sa.update(User).where(User.id.in_(users)).values(organization_id=None))
            await db.execute(sa.delete(Organization).where(Organization.id.in_(orgs)))
            await db.execute(sa.delete(User).where(User.id.in_(users)))
            await db.commit()
        await engine.dispose()


async def pending(sessions, users, orgs, *, user_index=2, org_index=0):
    token = create_invite_token(org_id=orgs[org_index], email=f"consent-{users[user_index]}@integration.invalid",
                                role="member", invited_by=users[org_index])
    invite_id = str(uuid.uuid4())
    async with sessions() as db:
        db.add(OrganizationInvite(id=invite_id, organization_id=orgs[org_index],
                                  email=f"consent-{users[user_index]}@integration.invalid", token=token,
                                  role="member", status="pending", invited_by=users[org_index],
                                  expires_at=datetime.now(timezone.utc) + timedelta(days=7)))
        await db.commit()
    return token, invite_id


async def attempt(sessions, user_id, org_id, token):
    async with sessions() as db:
        try:
            await accept_invite(db, user_id=user_id, org_id=org_id, token=token)
            await db.commit()
            return 200
        except HTTPException as error:
            await db.rollback()
            return error.status_code


async def wait_for_block(observer, task, waiter_pid, blocker_pid=None):
    """Bounded observation of actual database blocking, never a timing sleep."""
    async with asyncio.timeout(10):
        while True:
            blocking = await observer.scalar(sa.text(
                "SELECT cardinality(pg_blocking_pids(:waiter)) > 0" if blocker_pid is None
                else "SELECT :blocker = ANY(pg_blocking_pids(:waiter))"),
                {"waiter": waiter_pid, **({"blocker": blocker_pid} if blocker_pid is not None else {})})
            if blocking:
                return
            if task.done():
                pytest.fail("Operation completed without the expected PostgreSQL lock wait")


async def contended_accepts(sessions, locked_org_id, cases):
    tasks = []
    pids = asyncio.Queue()
    async def accept(user_id, org_id, token):
        async with sessions() as db:
            await pids.put(await db.scalar(sa.text("SELECT pg_backend_pid()")))
            try:
                await accept_invite(db, user_id=user_id, org_id=org_id, token=token)
                await db.commit()
                return 200
            except HTTPException as error:
                await db.rollback()
                return error.status_code
    try:
        async with sessions() as blocker, sessions() as observer:
            await lock_org(blocker, locked_org_id)
            for case in cases:
                task = asyncio.create_task(accept(*case))
                tasks.append(task)
                pid = await asyncio.wait_for(pids.get(), timeout=10)
                # In replay/competing-org cases, the second operation waits
                # on the first recipient lock, while the first waits on org.
                await wait_for_block(observer, task, pid)
            await blocker.commit()
            return await asyncio.wait_for(asyncio.gather(*tasks), timeout=10)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def test_concurrent_last_seat_is_never_oversubscribed(team_database):
    sessions, users, orgs = team_database
    # Simulate legacy oversubscribed pending invitations: only one real seat
    # remains. Both accepts start together on independent real connections.
    one, _ = await pending(sessions, users, orgs, user_index=2)
    two, _ = await pending(sessions, users, orgs, user_index=3)
    outcomes = await contended_accepts(sessions, orgs[0], [
        (users[2], orgs[0], one), (users[3], orgs[0], two)])
    assert sorted(outcomes) == [200, 409]
    async with sessions() as db:
        assert await db.scalar(sa.select(sa.func.count()).select_from(OrganizationMember).where(
            OrganizationMember.organization_id == orgs[0])) == 2
        assert await db.scalar(sa.select(sa.func.count()).select_from(OrganizationAuditLog).where(
            OrganizationAuditLog.organization_id == orgs[0], OrganizationAuditLog.action == "invite_accepted")) == 1


async def test_concurrent_replay_writes_one_membership_and_audit(team_database):
    sessions, users, orgs = team_database
    token, _ = await pending(sessions, users, orgs)
    assert await contended_accepts(sessions, orgs[0], [(users[2], orgs[0], token)] * 2) == [200, 200]
    async with sessions() as db:
        assert await db.scalar(sa.select(sa.func.count()).select_from(OrganizationMember).where(
            OrganizationMember.user_id == users[2])) == 1
        assert await db.scalar(sa.select(sa.func.count()).select_from(OrganizationAuditLog).where(
            OrganizationAuditLog.actor_user_id == users[2], OrganizationAuditLog.action == "invite_accepted")) == 1


async def test_concurrent_competing_orgs_serialize_on_recipient(team_database):
    sessions, users, orgs = team_database
    one, _ = await pending(sessions, users, orgs)
    two, _ = await pending(sessions, users, orgs, org_index=1)
    assert await contended_accepts(sessions, orgs[0], [
        (users[2], orgs[0], one), (users[2], orgs[1], two)]) == [200, 409]
    async with sessions() as db:
        member = (await db.execute(sa.select(OrganizationMember).where(
            OrganizationMember.user_id == users[2]))).scalar_one()
        assert (await db.get(User, users[2])).organization_id == member.organization_id


async def test_revocation_committed_before_accept_lock_prevents_join(team_database):
    sessions, users, orgs = team_database
    token, invite_id = await pending(sessions, users, orgs)
    async with sessions() as revoker:
        await lock_org(revoker, orgs[0])
        invite = await revoker.get(OrganizationInvite, invite_id, with_for_update=True)
        invite.status, invite.revoked_at = "revoked", datetime.now(timezone.utc)
        started = asyncio.Queue()
        async def blocked_accept():
            async with sessions() as db:
                await started.put(await db.scalar(sa.text("SELECT pg_backend_pid()")))
                try:
                    await accept_invite(db, user_id=users[2], org_id=orgs[0], token=token)
                    await db.commit()
                    return 200
                except HTTPException as error:
                    await db.rollback()
                    return error.status_code
        task = asyncio.create_task(blocked_accept())
        try:
            pid = await asyncio.wait_for(started.get(), timeout=10)
            async with sessions() as observer:
                await wait_for_block(observer, task, pid,
                                      await revoker.scalar(sa.text("SELECT pg_backend_pid()")))
            await revoker.commit()
            assert await asyncio.wait_for(task, timeout=10) == 400
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("defect", ["wrong_user", "wrong_org", "expired", "revoked", "missing", "role", "unverified", "other_org"])
async def test_invalid_invites_leave_no_membership_or_pointer(team_database, defect):
    sessions, users, orgs = team_database
    token, invite_id = await pending(sessions, users, orgs)
    uid, oid = users[2], orgs[0]
    async with sessions() as db:
        invite = await db.get(OrganizationInvite, invite_id)
        recipient = await db.get(User, uid)
        if defect == "wrong_user":
            uid = users[3]
        elif defect == "wrong_org":
            oid = orgs[1]
        elif defect == "expired":
            invite.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        elif defect == "revoked":
            invite.status = "revoked"
        elif defect == "missing":
            await db.delete(invite)
        elif defect == "role":
            invite.role = "admin"
        elif defect == "unverified":
            recipient.email_verified_at = None
        elif defect == "other_org":
            recipient.organization_id = orgs[1]
            db.add(OrganizationMember(organization_id=orgs[1], user_id=uid, role="member"))
        await db.commit()
    assert await attempt(sessions, uid, oid, token) in (400, 403, 409)
    async with sessions() as db:
        assert await db.get(OrganizationMember, (orgs[0], uid)) is None
        assert (await db.get(User, uid)).organization_id == (orgs[1] if defect == "other_org" else None)


async def test_activity_and_usage_exclude_personal_and_previous_org_rows(team_database):
    sessions, users, orgs = team_database
    token, _ = await pending(sessions, users, orgs)
    # All resource types exist in each ownership context before the user joins.
    now = datetime.now(timezone.utc)
    expected_ids = set()
    async with sessions() as db:
        for organization_id in (None, orgs[1], orgs[0]):
            for model, fields in ((SourceCheck, {"input_type": "text", "input_content": "Fixture"}),
                                  (ResearcherProfile, {"researcher_name": "Fixture"}),
                                  (Report, {"report_type": "source_check", "title": "Fixture"})):
                resource_id = str(uuid.uuid4())
                db.add(model(id=resource_id, user_id=users[2], organization_id=organization_id,
                             created_at=now, **fields))
                if organization_id == orgs[0]:
                    expected_ids.add(resource_id)
        await db.commit()
    assert await attempt(sessions, users[2], orgs[0], token) == 200
    async with sessions() as db:
        viewer = await db.get(User, users[0])
        viewer._org_role = "admin"
        activity = await get_team_activity(db=db, current_user=viewer)
        assert {item["id"] for item in activity["items"]} == expected_ids
        assert await _usage_for_member(db=db, user_id=users[2], org_id=orgs[0],
                                       month_start=now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)) == (1, 1, 1)
        recipient = await db.get(User, users[2])
        recipient.share_activity_with_team = False
        await db.commit()
        assert (await get_team_activity(db=db, current_user=viewer))["items"] == []


async def test_audit_failure_rolls_back_invite_membership_and_pointer(team_database, monkeypatch):
    sessions, users, orgs = team_database
    token, invite_id = await pending(sessions, users, orgs)
    async def fail_audit(**kwargs):
        raise RuntimeError("synthetic audit failure")
    monkeypatch.setattr("app.services.team_invites.record_org_action", fail_audit)
    async with sessions() as db:
        with pytest.raises(RuntimeError, match="synthetic audit failure"):
            await accept_invite(db, user_id=users[2], org_id=orgs[0], token=token)
        await db.rollback()
    async with sessions() as db:
        assert (await db.get(User, users[2])).organization_id is None
        assert (await db.get(OrganizationInvite, invite_id)).status == "pending"
        assert await db.get(OrganizationMember, (orgs[0], users[2])) is None


@pytest.fixture
def consent_http(team_database, monkeypatch):
    from fastapi import FastAPI
    from app.config import settings
    from app.database import get_db
    from app.routers import auth, organizations, researcher, source_check
    from app.tasks import celery_app
    from unittest.mock import AsyncMock, Mock

    sessions, _, _ = team_database
    monkeypatch.setattr(settings, "JWT_SECRET", "consent-isolated-integration-key")
    monkeypatch.setattr(organizations, "send_email", AsyncMock(return_value=True))
    monkeypatch.setattr(source_check, "put_pdf", Mock(return_value="fixture-artifact-reference"))
    if celery_app is not None:
        monkeypatch.setattr(celery_app, "send_task", Mock())
    app = FastAPI()
    for router in (auth.router, organizations.router, source_check.router, researcher.router):
        app.include_router(router)
    pids = asyncio.Queue()
    async def database():
        async with sessions() as db:
            # This queue lets race tests observe the actual HTTP transaction,
            # not assume that starting a task means it reached a lock.
            await pids.put(await db.scalar(sa.text("SELECT pg_backend_pid()")))
            yield db
    app.dependency_overrides[get_db] = database
    return app, pids


def bearer(user_id):
    from app.utils.auth import create_access_token
    return {"Authorization": "Bearer " + create_access_token(user_id, f"consent-{user_id}@integration.invalid")}


async def test_http_verified_recipient_accepts_and_accesses_team_with_same_bearer(team_database, consent_http):
    import httpx
    sessions, users, orgs = team_database
    app, _ = consent_http
    token, _ = await pending(sessions, users, orgs)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://consent-test") as client:
        headers = bearer(users[2])
        before = await client.get("/api/auth/me", headers=headers)
        assert before.status_code == 200
        assert before.json()["organization_id"] is None
        unauthenticated = await client.post(f"/api/organizations/{orgs[0]}/invites/accept", json={"token": token})
        assert unauthenticated.status_code in (401, 403)
        wrong_user = await client.post(f"/api/organizations/{orgs[0]}/invites/accept", json={"token": token}, headers=bearer(users[3]))
        assert wrong_user.status_code == 400
        accepted = await client.post(f"/api/organizations/{orgs[0]}/invites/accept", json={"token": token}, headers=headers)
        assert accepted.status_code == 200, accepted.text
        after = await client.get("/api/auth/me", headers=headers)
        assert after.status_code == 200
        assert after.json()["organization_id"] == orgs[0]
        assert after.json()["org_role"] == "member"
        team = await client.get(f"/api/organizations/{orgs[0]}", headers=headers)
        assert team.status_code == 200
        assert team.json()["current_user_role"] == "member"


@pytest.mark.parametrize("action", ["invite", "resend", "revoke", "role", "remove"])
@pytest.mark.parametrize("change", ["demoted", "removed"])
async def test_http_actor_reauthorized_after_observed_lock_wait(team_database, consent_http, action, change):
    """Real auth/dependency cache, real PostgreSQL lock, no sleeps as evidence."""
    import httpx
    from fastapi import Depends
    from app.database import get_db
    from app.deps.org import require_org_admin
    from app.models.user import User
    from app.utils.auth import get_current_user
    from app.routers import organizations

    sessions, users, orgs = team_database
    app, pids = consent_http
    _, invite_id = await pending(sessions, users, orgs)
    async with sessions() as db:
        # A second admin and a target member make demotion/removal legitimate.
        for index in (2, 3):
            (await db.get(User, users[index])).organization_id = orgs[0]
            db.add(OrganizationMember(organization_id=orgs[0], user_id=users[index],
                                      role="admin" if index == 3 else "member"))
        (await db.get(Organization, orgs[0])).seat_limit = 10
        await db.commit()
    authorized = asyncio.Event()
    async def early_dependency(org_id: str, current_user: User = Depends(get_current_user), db=Depends(get_db)):
        cached = await require_org_admin(org_id=org_id, current_user=current_user, db=db)
        authorized.set()
        return cached
    app.dependency_overrides[require_org_admin] = early_dependency
    paths = {
        "invite": ("POST", f"/api/organizations/{orgs[0]}/members/invite", {"email": "new@integration.invalid"}),
        "resend": ("POST", f"/api/organizations/{orgs[0]}/invites/{invite_id}/resend", None),
        "revoke": ("DELETE", f"/api/organizations/{orgs[0]}/invites/{invite_id}", None),
        "role": ("PATCH", f"/api/organizations/{orgs[0]}/members/{users[2]}", {"role": "admin"}),
        "remove": ("DELETE", f"/api/organizations/{orgs[0]}/members/{users[2]}", None),
    }
    method, path, body = paths[action]
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://consent-test") as client:
        async with sessions() as blocker:
            # Removal uses user -> org ordering in production; acquiring the
            # actor user first here respects that order too.
            await blocker.get(User, users[0], with_for_update=True)
            await lock_org(blocker, orgs[0])
            blocker_pid = await blocker.scalar(sa.text("SELECT pg_backend_pid()"))
            task = asyncio.create_task(client.request(method, path, json=body, headers=bearer(users[0])))
            try:
                async with asyncio.timeout(10):
                    await authorized.wait()  # real dependency passed as admin
                    request_pid = await pids.get()
                    async with sessions() as observer:
                        # Only proceed once PostgreSQL confirms THIS request
                        # is waiting on THIS blocker, not on elapsed wall time.
                        await wait_for_block(observer, task, request_pid, blocker_pid)
                    actor = await blocker.get(OrganizationMember, (orgs[0], users[0]))
                    if change == "demoted":
                        actor.role = "member"
                    else:
                        await blocker.delete(actor)
                        (await blocker.get(User, users[0])).organization_id = None
                    await blocker.commit()
                    response = await task
                assert response.status_code == 403, response.text
            finally:
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)
    async with sessions() as db:
        assert await db.scalar(sa.select(sa.func.count()).select_from(OrganizationInvite).where(
            OrganizationInvite.organization_id == orgs[0])) == 1
        assert (await db.get(OrganizationInvite, invite_id)).status == "pending"
        assert (await db.get(OrganizationMember, (orgs[0], users[2]))).role == "member"
        assert await db.scalar(sa.select(sa.func.count()).select_from(OrganizationAuditLog).where(
            OrganizationAuditLog.organization_id == orgs[0])) == 0
    organizations.send_email.assert_not_awaited()


@pytest.mark.parametrize("endpoint", ["source", "upload", "source_bulk", "rerun", "researcher", "researcher_bulk"])
@pytest.mark.parametrize("state", ["pointer_only", "mismatch", "active_member"])
async def test_http_creation_requires_matching_membership(team_database, consent_http, endpoint, state):
    import httpx
    sessions, users, orgs = team_database
    app, _ = consent_http
    original_id = str(uuid.uuid4())
    async with sessions() as db:
        (await db.get(User, users[2])).organization_id = orgs[0]
        if state != "pointer_only":
            db.add(OrganizationMember(user_id=users[2], organization_id=orgs[1] if state == "mismatch" else orgs[0], role="member"))
        db.add(SourceCheck(id=original_id, user_id=users[2], input_type="text", input_content="Original personal fixture"))
        await db.commit()
    calls = {
        "source": ("/api/source-check/", {"input_type": "text", "input_content": "New fixture content"}),
        "source_bulk": ("/api/source-check/bulk", {"items": [{"input_type": "text", "input_content": "New fixture content"}]}),
        "rerun": (f"/api/source-check/{original_id}/rerun", None),
        "researcher": ("/api/researcher/analyze", {"researcher_name": "Fixture"}),
        "researcher_bulk": ("/api/researcher/bulk", {"items": [{"researcher_name": "Fixture"}]}),
    }
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://consent-test") as client:
        if endpoint == "upload":
            response = await client.post("/api/source-check/upload", headers=bearer(users[2]),
                                          files={"file": ("fixture.pdf", b"%PDF-" + b"x" * 2048, "application/pdf")})
        else:
            path, payload = calls[endpoint]
            response = await client.post(path, headers=bearer(users[2]), json=payload)
    if state == "active_member":
        assert response.status_code == 201, response.text
        resource_id = response.json()["items"][0]["id"] if endpoint.endswith("bulk") else response.json()["id"]
        model = ResearcherProfile if endpoint.startswith("researcher") else SourceCheck
        async with sessions() as db:
            assert (await db.get(model, resource_id)).organization_id == orgs[0]
    else:
        assert response.status_code == 403, response.text
        async with sessions() as db:
            assert await db.scalar(sa.select(sa.func.count()).select_from(SourceCheck).where(SourceCheck.user_id == users[2])) == 1
            assert await db.scalar(sa.select(sa.func.count()).select_from(ResearcherProfile).where(ResearcherProfile.user_id == users[2])) == 0
            assert (await db.get(SourceCheck, original_id)).organization_id is None
