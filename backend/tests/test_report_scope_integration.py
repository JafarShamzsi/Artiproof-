"""Real PostgreSQL persistence/isolation tests on opt-in disposable fixtures.

Requires a dedicated migrated ARTIPROOF_INTEGRATION_DATABASE_URL. Never falls
back to app DATABASE_URL, SQLite, customer records, or live providers.
"""

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.models.organization import Organization
from app.models.report import Report
from app.models.report_schedule import ReportSchedule
from app.models.researcher import ResearcherProfile
from app.models.source_check import SourceCheck
from app.models.user import User
from app.routers import reports
from app.schemas.report import ReportGenerateRequest
from app.tasks.scheduled_reports import run_due_schedules
from tests.test_report_scope_security import actor, rendering  # noqa: F401

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture
async def report_database():
    url = os.getenv("ARTIPROOF_INTEGRATION_DATABASE_URL")
    if not url:
        pytest.skip("No dedicated migrated ARTIPROOF_INTEGRATION_DATABASE_URL; PostgreSQL isolation unverified")
    if not url.startswith("postgresql+asyncpg://"):
        pytest.fail("Requires dedicated PostgreSQL via asyncpg, never SQLite")
    engine = create_async_engine(url, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    uid, org_a, org_b = [str(uuid.uuid4()) for _ in range(3)]
    try:
        async with sessions() as db:
            db.add_all([Organization(id=oid, name="Report scope fixture", slug=f"report-scope-{oid}")
                        for oid in (org_a, org_b)])
            await db.flush()
            db.add(User(id=uid, email=f"report-scope-{uid}@integration.invalid", tier="free",
                        organization_id=org_b))
            await db.commit()
        yield sessions, uid, org_a, org_b
    finally:
        async with sessions() as db:
            for model in (Report, ReportSchedule, ResearcherProfile, SourceCheck):
                await db.execute(sa.delete(model).where(model.user_id == uid))
            await db.execute(sa.delete(User).where(User.id == uid))
            await db.execute(sa.delete(Organization).where(Organization.id.in_([org_a, org_b])))
            await db.commit()
        await engine.dispose()


@pytest.mark.parametrize("personal", [True, False])
@pytest.mark.parametrize("kind", ["source", "researcher", "comparison", "institutional_audit"])
@pytest.mark.usefixtures("rendering")
async def test_persisted_report_does_not_transfer_to_new_org(report_database, personal, kind):
    sessions, uid, org_a, org_b = report_database
    scope = None if personal else org_a
    model = SourceCheck if kind in ("source", "comparison") else ResearcherProfile
    ids = [str(uuid.uuid4()) for _ in range(2)]
    async with sessions() as db:
        for rid in ids:
            values = {"input_type": "text", "input_content": "Audit fixture"} if model is SourceCheck else {"researcher_name": "Audit fixture"}
            db.add(model(id=rid, user_id=uid, organization_id=scope, **values))
        await db.commit()
        fields = {"source": {"source_check_id": ids[0]},
                  "researcher": {"researcher_profile_id": ids[0]},
                  "comparison": {"source_check_ids": ids, "template": "comparison"},
                  "institutional_audit": {"researcher_profile_ids": ids, "template": "institutional_audit"}}
        report = await reports.generate_report.__wrapped__(request=None,
            data=ReportGenerateRequest(**fields[kind]), db=db, current_user=actor(uid, org_b))
        rid = report.id
    # Independent connection/identity map, not a mocked persistence assertion.
    async with sessions() as db:
        stored = await db.get(Report, rid)
        assert stored.organization_id == scope
        assert stored.user_id == uid
        with pytest.raises(HTTPException) as denied:
            await reports.get_report(rid, db, actor("new-admin", org_b, "admin"))
        assert denied.value.status_code == 403
        assert (await reports.get_report(rid, db, actor(uid, org_b))).id == rid
        if scope:
            assert (await reports.get_report(rid, db, actor("prior-admin", org_a, "admin"))).id == rid


async def test_legacy_schedule_produces_no_database_report(report_database):
    sessions, uid, _, _ = report_database
    async with sessions() as db:
        schedule = ReportSchedule(user_id=uid, frequency="weekly", active=True,
                                  next_run_at=datetime.now(UTC) - timedelta(days=1))
        db.add(schedule)
        await db.commit()
        sid = schedule.id
        with pytest.raises(RuntimeError, match="(?i)disabled"):
            await run_due_schedules(db)
    async with sessions() as db:
        assert await db.scalar(sa.select(sa.func.count(Report.id)).where(Report.user_id == uid)) == 0
        assert (await db.get(ReportSchedule, sid)).last_run_at is None


@pytest.mark.parametrize("personal", [True, False])
@pytest.mark.parametrize("kind", ["comparison", "institutional_audit"])
@pytest.mark.usefixtures("rendering")
async def test_mixed_scope_cannot_persist_report(report_database, personal, kind):
    sessions, uid, org_a, org_b = report_database
    ids = [str(uuid.uuid4()) for _ in range(2)]
    model = SourceCheck if kind == "comparison" else ResearcherProfile
    async with sessions() as db:
        for rid, scope in zip(ids, [None if personal else org_a, org_b], strict=True):
            values = {"input_type": "text", "input_content": "Audit fixture"} if model is SourceCheck else {"researcher_name": "Audit fixture"}
            db.add(model(id=rid, user_id=uid, organization_id=scope, **values))
        await db.commit()
        fields = {"source_check_ids": ids} if kind == "comparison" else {"researcher_profile_ids": ids}
        with pytest.raises(HTTPException) as denied:
            await reports.generate_report.__wrapped__(request=None,
                data=ReportGenerateRequest(template=kind, **fields), db=db, current_user=actor(uid, org_b))
        assert denied.value.status_code == 400
        await db.rollback()
    async with sessions() as db:
        assert await db.scalar(sa.select(sa.func.count(Report.id)).where(Report.user_id == uid)) == 0
