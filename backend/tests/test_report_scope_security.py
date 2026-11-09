"""Audit-only report scope regressions. No database or provider calls."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from app.routers import report_schedules, reports
from app.schemas.report import (
    ReportGenerateRequest,
    ReportScheduleCreate,
    ReportScheduleUpdate,
)
from app.tasks import scheduled_reports


def actor(uid="owner", org="org-b", role=None):
    return SimpleNamespace(id=uid, organization_id=org, _org_role=role, tier="free")


def row(uid="owner", org=None, rid="input-1"):
    return SimpleNamespace(id=rid, user_id=uid, organization_id=org,
                           input_title="Audit fixture", researcher_name="Audit fixture",
                           deleted_at=None)


def result(rows):
    return SimpleNamespace(scalar_one_or_none=lambda: rows[0] if rows else None,
                           scalars=lambda: SimpleNamespace(all=lambda: rows))


DERIVATION_WORK = (
    "_branding_for_user", "_load_check_data", "_load_researcher_data",
    "_load_check_summaries_batched", "_researcher_summaries",
    "generate_source_check_narrative", "generate_researcher_narrative",
    "render_source_check_report", "render_researcher_report",
    "render_comparison_report", "render_institutional_audit_report",
    "render_executive_summary_report", "html_to_pdf", "save_pdf",
)


def assert_no_derivation_work(db):
    """Call before any rollback can erase evidence of an attempted write."""
    for name in DERIVATION_WORK:
        getattr(reports, name).assert_not_called()
    for name in ("add", "add_all", "flush", "commit"):
        getattr(db, name).assert_not_called()


@pytest.fixture
def rendering_stubs(monkeypatch):
    monkeypatch.setattr(reports, "_branding_for_user", AsyncMock(return_value=None))
    for name in ("_load_check_data", "_load_researcher_data"):
        monkeypatch.setattr(reports, name, AsyncMock(return_value={}))
    monkeypatch.setattr(reports, "_load_check_summaries_batched", AsyncMock(return_value=[{}, {}]))
    monkeypatch.setattr(reports, "_researcher_summaries", Mock(return_value=[{}, {}]))
    for name in ("generate_source_check_narrative", "generate_researcher_narrative"):
        monkeypatch.setattr(reports, name, AsyncMock(return_value="Audit narrative"))
    for name in ("render_source_check_report", "render_researcher_report",
                 "render_comparison_report", "render_institutional_audit_report",
                 "render_executive_summary_report"):
        monkeypatch.setattr(reports, name, Mock(return_value="fixture html"))
    monkeypatch.setattr(reports, "html_to_pdf", Mock(return_value=(b"fixture", "test")))
    monkeypatch.setattr(reports, "save_pdf", Mock(return_value="fixture.pdf"))


@pytest.fixture
def rendering(rendering_stubs, monkeypatch):
    monkeypatch.setattr(reports, "_report_response", lambda report: report)


async def generate(inputs, kind, user=None, db=None):
    db = db if db is not None else AsyncMock()
    db.add = Mock()
    db.execute.return_value = result(inputs)
    fields = {
        "source": {"source_check_id": inputs[0].id},
        "researcher": {"researcher_profile_id": inputs[0].id},
        "executive_summary": {"source_check_id": inputs[0].id, "template": "executive_summary"},
        "comparison": {"source_check_ids": [r.id for r in inputs], "template": "comparison"},
        "institutional_audit": {"researcher_profile_ids": [r.id for r in inputs], "template": "institutional_audit"},
    }
    report = await reports.generate_report.__wrapped__(
        request=None, data=ReportGenerateRequest(**fields[kind]), db=db,
        current_user=user or actor())
    return report, db


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", [None, "org-a"])
@pytest.mark.parametrize("kind", ["source", "researcher", "executive_summary", "comparison", "institutional_audit"])
async def test_report_preserves_input_scope_after_join_or_switch(rendering, scope, kind):
    inputs = [row(org=scope), row(org=scope, rid="input-2")]
    report, db = await generate(inputs, kind)
    assert report.organization_id == scope
    db.add.assert_called_once_with(report)
    # New org's admin must not gain JSON or cached PDF access.
    db.execute.return_value = result([report])
    for reader in (reports.get_report, reports.download_report):
        with pytest.raises(HTTPException) as denied:
            await reader(report_id="report", db=db, current_user=actor("new-admin", role="admin"))
        assert denied.value.status_code == 403
    assert await reports.get_report(report_id="report", db=db, current_user=actor()) is report
    if scope:
        assert await reports.get_report(report_id="report", db=db,
                                        current_user=actor("old-admin", scope, "admin")) is report


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["comparison", "institutional_audit"])
@pytest.mark.parametrize("scopes", [(None, "org-b"), ("org-a", "org-b")])
async def test_mixed_scope_reports_rejected_before_rendering(rendering, kind, scopes):
    db = AsyncMock()
    with pytest.raises(HTTPException) as denied:
        await generate([row(org=scopes[0]), row(org=scopes[1], rid="input-2")], kind, db=db)
    assert denied.value.status_code == 400
    assert_no_derivation_work(db)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["source", "researcher", "comparison", "institutional_audit"])
async def test_input_authorization_still_required(rendering, kind):
    with pytest.raises(HTTPException) as denied:
        await generate([row(uid="other", org="org-a"), row(rid="input-2")], kind)
    assert denied.value.status_code == 403
    reports.html_to_pdf.assert_not_called()


@pytest.mark.asyncio
async def test_schedule_creation_explicitly_unavailable(monkeypatch):
    monkeypatch.setattr(report_schedules, "_response", lambda schedule: schedule)
    db = AsyncMock()
    db.execute.return_value = result([])
    with pytest.raises(HTTPException) as disabled:
        await report_schedules.create_schedule(ReportScheduleCreate(frequency="weekly"), db, actor())
    assert disabled.value.status_code == 503
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_legacy_schedule_cannot_be_reactivated(monkeypatch):
    monkeypatch.setattr(report_schedules, "_response", lambda schedule: schedule)
    schedule = SimpleNamespace(user_id="owner", active=False)
    db = AsyncMock()
    db.execute.return_value = result([schedule])
    with pytest.raises(HTTPException) as disabled:
        await report_schedules.update_schedule("schedule", ReportScheduleUpdate(active=True), db, actor())
    assert disabled.value.status_code == 503
    assert schedule.active is False
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_legacy_schedule_execution_fails_closed_without_reading_history():
    db = AsyncMock()
    db.execute.return_value = result([])
    # A disabled sweep must not even query mutable user pointers or history.
    with pytest.raises(RuntimeError, match="(?i)disabled"):
        await scheduled_reports.run_due_schedules(db)
    db.execute.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["source", "researcher", "comparison", "institutional_audit"])
async def test_current_org_admin_can_derive_only_same_scope_inputs(rendering, kind):
    report, _ = await generate([row(uid="member", org="org-b"),
                                row(uid="member", org="org-b", rid="input-2")],
                               kind, actor("admin", "org-b", "admin"))
    assert report.organization_id == "org-b"
    assert report.user_id == "admin"


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["source", "researcher", "comparison", "institutional_audit"])
async def test_regeneration_cannot_import_changed_scope_inputs(rendering, kind):
    report, db = await generate([row(org=None), row(org=None, rid="input-2")], kind)
    changed = [row(org="org-b"), row(org="org-b", rid="input-2")]
    # Owner lookup followed by underlying-record lookup, as in real regen.
    db.execute.side_effect = [result([actor()]), result(changed)]
    reports.html_to_pdf.reset_mock()
    with pytest.raises(HTTPException) as denied:
        await reports._regenerate_report_pdf(report, db)
    assert denied.value.status_code == 410
    reports.html_to_pdf.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["comparison", "institutional_audit"])
async def test_regeneration_rejects_partially_missing_inputs(rendering, kind):
    report, db = await generate([row(), row(rid="input-2")], kind)
    db.execute.side_effect = [result([actor()]), result([row()])]
    with pytest.raises(HTTPException) as denied:
        await reports._regenerate_report_pdf(report, db)
    assert denied.value.status_code == 410


def test_disabled_beat_keeps_unrelated_tasks():
    celery = SimpleNamespace(conf=SimpleNamespace(beat_schedule={
        "artiproof-scheduled-reports-daily": {"task": "scheduled_reports.run_due"},
        "unrelated": {"task": "cleanup"},
    }))
    scheduled_reports.schedule_beat(celery)
    assert celery.conf.beat_schedule == {"unrelated": {"task": "cleanup"}}


def test_previously_queued_task_reports_disabled_not_sent():
    # Direct invocation only; no publish, broker, DB session or delivery.
    outcome = scheduled_reports.run_due_scheduled_reports_task.run()
    assert outcome["status"] == "disabled"
    assert outcome["generated"] == outcome["sent"] == 0


@pytest.mark.asyncio
async def test_schedule_pause_remains_available(monkeypatch):
    monkeypatch.setattr(report_schedules, "_response", lambda schedule: schedule)
    schedule = SimpleNamespace(user_id="owner", active=True)
    db = AsyncMock()
    db.execute.return_value = result([schedule])
    updated = await report_schedules.update_schedule("schedule", ReportScheduleUpdate(active=False), db, actor())
    assert updated.active is False
    db.commit.assert_awaited_once()


def test_postgresql_user_fixture_includes_required_name():
    from tests.test_report_scope_integration import fixture_user

    user = fixture_user("audit-user", None)
    assert user.full_name == "Report scope fixture"


@pytest.mark.asyncio
@pytest.mark.parametrize("report_type", ["source_verification", "researcher_integrity"])
@pytest.mark.parametrize("template", ["full", "executive_summary"])
async def test_recognized_single_input_report_with_null_fk_is_gone(rendering, report_type, template):
    from app.models.report import Report

    report = Report(user_id="owner", organization_id=None, report_type=report_type,
                    template=template, title="Audit fixture", source_check_id=None,
                    researcher_profile_id=None)
    db = AsyncMock()
    db.execute.return_value = result([actor()])
    with pytest.raises(HTTPException) as gone:
        await reports._regenerate_report_pdf(report, db)
    assert gone.value.status_code == 410
    reports.html_to_pdf.assert_not_called()


@pytest.mark.asyncio
async def test_unknown_inputless_report_keeps_internal_error(rendering):
    from app.models.report import Report

    report = Report(user_id="owner", organization_id=None, report_type="unknown",
                    template="full", title="Audit fixture", source_check_id=None,
                    researcher_profile_id=None)
    db = AsyncMock()
    db.execute.return_value = result([actor()])
    with pytest.raises(HTTPException) as invalid:
        await reports._regenerate_report_pdf(report, db)
    assert invalid.value.status_code == 500
