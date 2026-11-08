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


async def test_concurrent_last_seat_is_never_oversubscribed(team_database):
    sessions, users, orgs = team_database
    # Simulate legacy oversubscribed pending invitations: only one real seat
    # remains. Both accepts start together on independent real connections.
    one, _ = await pending(sessions, users, orgs, user_index=2)
    two, _ = await pending(sessions, users, orgs, user_index=3)
    outcomes = await asyncio.gather(attempt(sessions, users[2], orgs[0], one),
                                    attempt(sessions, users[3], orgs[0], two))
    assert sorted(outcomes) == [200, 409]
    async with sessions() as db:
        assert await db.scalar(sa.select(sa.func.count()).select_from(OrganizationMember).where(
            OrganizationMember.organization_id == orgs[0])) == 2
        assert await db.scalar(sa.select(sa.func.count()).select_from(OrganizationAuditLog).where(
            OrganizationAuditLog.organization_id == orgs[0], OrganizationAuditLog.action == "invite_accepted")) == 1


async def test_concurrent_replay_writes_one_membership_and_audit(team_database):
    sessions, users, orgs = team_database
    token, _ = await pending(sessions, users, orgs)
    assert await asyncio.gather(*[attempt(sessions, users[2], orgs[0], token) for _ in range(2)]) == [200, 200]
    async with sessions() as db:
        assert await db.scalar(sa.select(sa.func.count()).select_from(OrganizationMember).where(
            OrganizationMember.user_id == users[2])) == 1
        assert await db.scalar(sa.select(sa.func.count()).select_from(OrganizationAuditLog).where(
            OrganizationAuditLog.actor_user_id == users[2], OrganizationAuditLog.action == "invite_accepted")) == 1


async def test_concurrent_competing_orgs_serialize_on_recipient(team_database):
    sessions, users, orgs = team_database
    one, _ = await pending(sessions, users, orgs)
    two, _ = await pending(sessions, users, orgs, org_index=1)
    assert sorted(await asyncio.gather(attempt(sessions, users[2], orgs[0], one),
                                        attempt(sessions, users[2], orgs[1], two))) == [200, 409]
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
        started = asyncio.Event()
        async def blocked_accept():
            started.set()
            return await attempt(sessions, users[2], orgs[0], token)
        task = asyncio.create_task(blocked_accept())
        await started.wait()
        await revoker.commit()
        assert await task == 400


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
