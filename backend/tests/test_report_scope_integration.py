"""Opt-in real PostgreSQL + bearer HTTP acceptance on disposable audit rows.

Only ARTIPROOF_INTEGRATION_DATABASE_URL is used, never app DATABASE_URL or
SQLite. Missing service configuration is an explicit skip, not DB evidence.
"""

import os
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

import pytest
import sqlalchemy as sa
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.database import get_db
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.report import Report
from app.models.report_schedule import ReportSchedule
from app.models.researcher import ResearcherProfile
from app.models.session import Session
from app.models.source_check import SourceCheck
from app.models.user import User
from app.routers import reports
from app.schemas.report import ReportGenerateRequest
from app.tasks.scheduled_reports import run_due_schedules
from app.utils.auth import create_access_token
from app.utils.rate_limit import limiter
from tests.test_report_scope_security import (
    assert_no_derivation_work,
    rendering_stubs,  # noqa: F401
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def fixture_user(uid, organization_id):
    return User(id=uid, email=f"report-scope-{uid}@integration.invalid",
                full_name="Report scope fixture", tier="team",
                email_verified_at=datetime.now(UTC), organization_id=organization_id)


def prior_admin(uid):
    return f"{uid}-prior-admin"


def new_admin(uid):
    return f"{uid}-new-admin"


def bearer(uid):
    return {"Authorization": "Bearer " + create_access_token(
        uid, f"report-scope-{uid}@integration.invalid",
        session_id=f"report-scope-session-{uid}", tier="team")}


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
    users = [uid, prior_admin(uid), new_admin(uid)]
    try:
        async with sessions() as db:
            db.add_all([Organization(id=oid, name="Report scope fixture", slug=f"report-scope-{oid}")
                        for oid in (org_a, org_b)])
            await db.flush()
            db.add_all([fixture_user(user_id, org) for user_id, org in
                        zip(users, [None, org_a, org_b], strict=True)])
            await db.flush()
            db.add_all([OrganizationMember(user_id=user_id, organization_id=org, role="admin")
                        for user_id, org in [(users[1], org_a), (users[2], org_b)]])
            db.add_all([Session(id=f"report-scope-session-{user_id}", user_id=user_id)
                        for user_id in users])
            await db.commit()
        yield sessions, uid, org_a, org_b
    finally:
        async with sessions() as db:
            for model in (Report, ReportSchedule, ResearcherProfile, SourceCheck,
                          Session, OrganizationMember):
                await db.execute(sa.delete(model).where(model.user_id.in_(users)))
            await db.execute(sa.delete(User).where(User.id.in_(users)))
            await db.execute(sa.delete(Organization).where(Organization.id.in_([org_a, org_b])))
            await db.commit()
        await engine.dispose()


@pytest.fixture
async def report_http(report_database, request, monkeypatch):
    request.getfixturevalue("rendering_stubs")
    sessions, _, _, _ = report_database
    # Test-only key, never a credential read. Real auth/session/membership deps
    # run unchanged. This small app has no lifespan, broker or provider startup.
    monkeypatch.setattr(settings, "JWT_SECRET", "report-scope-isolated-audit-test-key")
    monkeypatch.setattr(reports, "read_pdf", Mock(return_value=b"fixture"))
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(reports.router)

    async def database():
        async with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = database
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://report-scope-test") as client:
        yield client


def input_model(kind):
    return SourceCheck if kind in ("source", "executive_summary", "comparison") else ResearcherProfile


def payload(kind, ids):
    return {
        "source": {"source_check_id": ids[0]},
        "executive_summary": {"source_check_id": ids[0], "template": "executive_summary"},
        "researcher": {"researcher_profile_id": ids[0]},
        "comparison": {"source_check_ids": ids, "template": "comparison"},
        "institutional_audit": {"researcher_profile_ids": ids, "template": "institutional_audit"},
    }[kind]


async def seed_inputs(database, kind, scopes):
    sessions, uid, _, _ = database
    ids = [str(uuid.uuid4()) for _ in scopes]
    model = input_model(kind)
    async with sessions() as db:
        for rid, scope in zip(ids, scopes, strict=True):
            fields = {"input_type": "text", "input_content": "Audit fixture"} if model is SourceCheck else {"researcher_name": "Audit fixture"}
            db.add(model(id=rid, user_id=uid, organization_id=scope, **fields))
        await db.commit()
    return ids


async def original_membership(database, personal):
    sessions, uid, org_a, _ = database
    if not personal:
        async with sessions() as db:
            (await db.get(User, uid)).organization_id = org_a
            db.add(OrganizationMember(user_id=uid, organization_id=org_a, role="member"))
            await db.commit()


async def join_new_org(database):
    """Fixture transition in PostgreSQL, not a claim to test the consent UI."""
    sessions, uid, org_a, org_b = database
    async with sessions() as db:
        await db.execute(sa.delete(OrganizationMember).where(
            OrganizationMember.user_id == uid, OrganizationMember.organization_id == org_a))
        (await db.get(User, uid)).organization_id = org_b
        db.add(OrganizationMember(user_id=uid, organization_id=org_b, role="member"))
        await db.commit()
    async with sessions() as db:
        assert (await db.get(User, uid)).organization_id == org_b
        assert await db.get(OrganizationMember, (org_a, uid)) is None
        assert (await db.get(OrganizationMember, (org_b, uid))).role == "member"


@pytest.mark.parametrize("personal", [True, False])
@pytest.mark.parametrize("kind", ["source", "researcher", "executive_summary", "comparison", "institutional_audit"])
async def test_persisted_report_does_not_transfer_to_new_org(report_database, report_http, personal, kind):
    sessions, uid, org_a, _ = report_database
    scope = None if personal else org_a
    await original_membership(report_database, personal)
    ids = await seed_inputs(report_database, kind, [scope, scope])
    # Issue the real persisted session's token before the membership transition.
    owner_headers = bearer(uid)
    await join_new_org(report_database)
    created = await report_http.post("/api/reports/generate", headers=owner_headers, json=payload(kind, ids))
    assert created.status_code == 201, created.text
    rid = created.json()["id"]
    async with sessions() as db:
        stored = await db.get(Report, rid)
        assert stored.organization_id == scope
        assert stored.user_id == uid
    for suffix in ("", "/download"):
        path = f"/api/reports/{rid}{suffix}"
        assert (await report_http.get(path)).status_code == 401
        denied = await report_http.get(path, headers=bearer(new_admin(uid)))
        assert denied.status_code == 403, denied.text
        owner = await report_http.get(path, headers=owner_headers)
        assert owner.status_code == 200, owner.text
        prior = await report_http.get(path, headers=bearer(prior_admin(uid)))
        assert prior.status_code == (403 if personal else 200), prior.text


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
@pytest.mark.usefixtures("rendering_stubs")
async def test_mixed_scope_cannot_persist_report(report_database, personal, kind):
    sessions, uid, org_a, org_b = report_database
    await original_membership(report_database, personal)
    ids = await seed_inputs(report_database, kind, [None if personal else org_a, org_b])
    await join_new_org(report_database)
    async with sessions() as db:
        # Real persisted owner. No synthetic _org_role assignment is needed.
        owner = await db.get(User, uid)
        # Spies wrap the real transaction to detect even attempted side effects.
        with (patch.object(db, "add", wraps=db.add), patch.object(db, "add_all", wraps=db.add_all),
              patch.object(db, "flush", wraps=db.flush), patch.object(db, "commit", wraps=db.commit)):
            with pytest.raises(HTTPException) as denied:
                await reports.generate_report.__wrapped__(request=None,
                    data=ReportGenerateRequest(**payload(kind, ids)), db=db, current_user=owner)
            assert denied.value.status_code == 400
            assert_no_derivation_work(db)  # before rollback, not just no committed row
        await db.rollback()
    async with sessions() as db:
        assert await db.scalar(sa.select(sa.func.count(Report.id)).where(Report.user_id == uid)) == 0


@pytest.mark.parametrize("kind", ["source", "researcher", "executive_summary", "comparison", "institutional_audit"])
@pytest.mark.parametrize("defect", ["unchanged", "drift", "missing", "soft_deleted", "hard_deleted"])
@pytest.mark.parametrize("public", [False, True])
async def test_http_cache_miss_refuses_changed_or_missing_inputs(report_database, report_http,
                                                               monkeypatch, kind, defect, public):
    sessions, uid, org_a, org_b = report_database
    await original_membership(report_database, personal=False)
    ids = await seed_inputs(report_database, kind, [org_a, org_a])
    await join_new_org(report_database)
    created = await report_http.post("/api/reports/generate", headers=bearer(uid), json=payload(kind, ids))
    assert created.status_code == 201, created.text
    rid, token = created.json()["id"], created.json()["share_token"]
    model = input_model(kind)
    # Commit the mutation on a different connection. HTTP must reload persisted
    # state, and hard deletion must exercise the real FK's SET NULL behavior.
    async with sessions() as db:
        stored = await db.get(Report, rid)
        stored.pdf_path = "fixture-missing-cache.pdf"
        source = await db.get(model, ids[0])
        if defect == "unchanged":
            pass
        elif defect == "drift":
            source.organization_id = org_b
        elif defect == "soft_deleted":
            source.deleted_at = datetime.now(UTC)
        elif defect == "hard_deleted":
            await db.delete(source)
        elif kind in ("comparison", "institutional_audit"):
            # JSON multi-input references can point to missing IDs, unlike FKs.
            attribute = "source_check_ids" if kind == "comparison" else "researcher_profile_ids"
            setattr(stored, attribute, [str(uuid.uuid4()), ids[1]])
        else:
            # A missing single-input relation is represented by NULL, including
            # after SET NULL; never disable FK enforcement to fabricate a row.
            attribute = "source_check_id" if model is SourceCheck else "researcher_profile_id"
            setattr(stored, attribute, None)
        await db.commit()
    async with sessions() as db:
        if defect == "hard_deleted" and kind not in ("comparison", "institutional_audit"):
            stored = await db.get(Report, rid)
            assert getattr(stored, "source_check_id" if model is SourceCheck else "researcher_profile_id") is None
        stored = await db.get(Report, rid)
        assert stored.organization_id == org_a
    monkeypatch.setattr(reports, "read_pdf", Mock(side_effect=FileNotFoundError("audit cache miss")))
    # Reset generation's test-double calls, so denial must do no new data load,
    # narrative, rendering, conversion or artifact write.
    for name in ("_load_check_data", "_load_researcher_data", "_load_check_summaries_batched",
                 "_researcher_summaries", "generate_source_check_narrative", "generate_researcher_narrative",
                 "render_source_check_report", "render_researcher_report", "render_comparison_report",
                 "render_institutional_audit_report", "render_executive_summary_report", "html_to_pdf", "save_pdf"):
        getattr(reports, name).reset_mock()
    path = f"/api/reports/shared/{token}/download" if public else f"/api/reports/{rid}/download"
    response = await report_http.get(path, headers={} if public else bearer(uid))
    if defect == "unchanged":
        assert response.status_code == 200, response.text
        assert response.content == b"fixture"
        reports.html_to_pdf.assert_called_once()
        reports.save_pdf.assert_called_once_with(b"fixture")
        async with sessions() as db:
            assert (await db.get(Report, rid)).pdf_path == "fixture.pdf"
        return
    assert response.status_code == 410, response.text
    for name in ("_load_check_data", "_load_researcher_data", "_load_check_summaries_batched",
                 "_researcher_summaries", "generate_source_check_narrative", "generate_researcher_narrative",
                 "render_source_check_report", "render_researcher_report", "render_comparison_report",
                 "render_institutional_audit_report", "render_executive_summary_report", "html_to_pdf", "save_pdf"):
        getattr(reports, name).assert_not_called()
    async with sessions() as db:
        assert (await db.get(Report, rid)).pdf_path == "fixture-missing-cache.pdf"
