"""Tests for the new report-features batch:
- Template renderers (smoke).
- POST /api/reports/generate validation for new templates + multi-input.
- PUT /api/reports/{id}/annotations.
- /api/me/report-schedules CRUD basics.
- /api/organizations/{id}/branding tier gating.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app
from app.services.report_engine.html_template import (
    render_comparison_report,
    render_executive_summary_report,
    render_institutional_audit_report,
    render_researcher_report,
    render_source_check_report,
)
from app.utils.auth import get_current_user


def _user(**overrides):
    base = SimpleNamespace(
        id="user-a",
        email="user-a@example.com",
        full_name="Test User",
        role="researcher",
        tier="free",
        organization_id=None,
        deactivated_at=None,
        deleted_at=None,
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


def _stub_db_with(rows: list | None = None, scalar=None):
    """Build an AsyncMock session whose execute(...) returns a result with
    the given rows (or scalar). Tests that need richer behavior override
    db.execute.return_value per-call.

    ``scalar()`` (no args) returns 0 by default — quota-enforcement code
    calls it to count MTD usage; returning 0 keeps tests below the limit
    so the quota dependency doesn't trip on unrelated test paths.
    """
    db = AsyncMock()
    result = SimpleNamespace(
        scalars=lambda: SimpleNamespace(all=lambda: rows or []),
        scalar_one_or_none=lambda: scalar,
        scalar=lambda: 0,
        all=lambda: [],
    )
    db.execute.return_value = result
    return db


# ─── Renderer smoke tests ─────────────────────────────────────────────────


def test_executive_summary_renders():
    check_data = {
        "input_title": "Test article",
        "overall_credibility_score": 75.0,
        "ai_content_percentage": 30.0,
        "misinfo_claims_found": 2,
        "claims": [{"verdict": "false"}, {"verdict": "true"}],
        "citations": [{"is_retracted": False, "is_accessible": True}],
    }
    html = render_executive_summary_report(check_data, "Brief narrative for test.")
    assert "Executive Summary" in html
    assert "Test article" in html
    assert "ArtiProof" in html  # default branding fallback
    assert "75" in html


def test_renderer_escapes_user_html_in_claims_citations_branding():
    """Regression: the PDF renderer must escape user-controlled fields so
    a hostile claim/citation/branding/annotation can't inject script tags
    visible to anyone who downloads the PDF or opens the share link."""
    payload = "<script>alert(1)</script>"
    check_data = {
        "input_title": payload,
        "overall_credibility_score": 50,
        "ai_content_percentage": 0,
        "misinfo_claims_found": 0,
        "claims": [
            {
                "claim_text": payload,
                "verdict": "false",
                "confidence": 0.9,
                "explanation": payload,
                "true_version": payload,
            }
        ],
        "citations": [{"original_citation": payload, "is_retracted": False, "is_accessible": True, "credibility_score": 50}],
    }
    html = render_source_check_report(
        check_data,
        f"Narrative line.\n\n{payload}",
        branding={"name": payload, "logo_url": None, "primary_color": "#003366", "tagline": payload},
        annotations=[{"text": payload, "author_name": payload, "created_at": "2026-05-09"}],
    )
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_renderer_escapes_user_html_in_researcher_and_audit():
    payload = "<img src=x onerror=alert(1)>"
    profile = {
        "researcher_name": payload,
        "institution": payload,
        "integrity_score": 50,
        "publications": [{"title": payload, "journal": payload, "year": 2024, "citation_count": 5}],
        "citation_ring_flags": {"flags": [payload]},
    }
    html = render_researcher_report(profile, payload)
    assert "<img src=x onerror=alert(1)>" not in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html

    audit = render_institutional_audit_report(
        [{"researcher_name": payload, "institution": payload, "integrity_score": 50}]
    )
    assert "<img src=x onerror=alert(1)>" not in audit


def test_branding_schema_rejects_ssrf_logo_urls():
    """SSRF defense: schema must reject cloud-metadata + loopback + private
    + non-HTTPS URLs before the renderer ever sees them."""
    from pydantic import ValidationError

    from app.schemas.report import OrganizationBranding

    bad = [
        "http://169.254.169.254/latest/meta-data/",  # AWS/GCP metadata
        "https://169.254.169.254/computeMetadata/",
        "https://localhost/logo.png",
        "https://127.0.0.1/logo.png",
        "https://10.0.0.5/logo.png",
        "https://[::1]/logo.png",
        "http://example.com/logo.png",                # plain http
        "file:///etc/passwd",
        "javascript:alert(1)",
        "https://metadata.google.internal/computeMetadata/v1/",
        "https://0.0.0.0/logo.png",
    ]
    for url in bad:
        try:
            OrganizationBranding(logo_url=url)
        except ValidationError:
            continue
        raise AssertionError(f"expected SSRF rejection for {url!r}")


def test_branding_schema_accepts_external_https_logo():
    from app.schemas.report import OrganizationBranding

    b = OrganizationBranding(logo_url="https://cdn.example.com/logo.png")
    assert b.logo_url == "https://cdn.example.com/logo.png"


def test_renderer_safe_color_falls_back_on_bad_value():
    """Defense in depth — if a bad color slips past the schema validator
    (legacy row, future bug), the renderer must fall back to the default
    rather than interpolating arbitrary CSS."""
    html = render_executive_summary_report(
        {
            "input_title": "X",
            "overall_credibility_score": 60,
            "ai_content_percentage": 0,
            "misinfo_claims_found": 0,
            "claims": [],
            "citations": [],
        },
        "n",
        branding={"name": "Acme", "primary_color": "red; }body{background:url(/*x*/)"},
    )
    assert "}body{background" not in html


def test_executive_summary_with_branding():
    html = render_executive_summary_report(
        {
            "input_title": "X",
            "overall_credibility_score": 60,
            "ai_content_percentage": 0,
            "misinfo_claims_found": 0,
            "claims": [],
            "citations": [],
        },
        "n",
        branding={
            "name": "Acme University",
            "logo_url": None,
            "primary_color": "#003366",
        },
    )
    assert "Acme University" in html
    assert "#003366" in html


def test_executive_summary_with_annotations():
    html = render_executive_summary_report(
        {
            "input_title": "X",
            "overall_credibility_score": 60,
            "ai_content_percentage": 0,
            "misinfo_claims_found": 0,
            "claims": [],
            "citations": [],
        },
        "n",
        annotations=[
            {"text": "Reviewed by lab.", "author_name": "Lab Lead", "created_at": "2026-05-09"}
        ],
    )
    assert "Reviewed by lab." in html
    assert "Lab Lead" in html


def test_comparison_renders_each_source():
    items = [
        {
            "input_title": "Source 1",
            "overall_credibility_score": 80,
            "ai_content_percentage": 10,
            "misinfo_claims_found": 0,
            "citations": [],
        },
        {
            "input_title": "Source 2",
            "overall_credibility_score": 50,
            "ai_content_percentage": 70,
            "misinfo_claims_found": 5,
            "citations": [{"is_retracted": True}],
        },
    ]
    html = render_comparison_report(items)
    assert "Source 1" in html
    assert "Source 2" in html
    assert "Comparison" in html or "comparing" in html.lower()


def test_full_source_check_passes_branding():
    """Regression: legacy `full` template must apply branding when supplied
    (advisor caught: previously rendered with default ArtiProof header)."""
    html = render_source_check_report(
        {
            "input_title": "Test",
            "overall_credibility_score": 50,
            "ai_content_percentage": 0,
            "misinfo_claims_found": 0,
            "claims": [],
            "citations": [],
        },
        "narrative",
        branding={"name": "Acme U", "primary_color": "#003366"},
        annotations=[{"text": "Reviewed.", "author_name": "Lab", "created_at": "2026-05-09"}],
    )
    assert "Acme U" in html
    assert "#003366" in html
    assert "Reviewed." in html


def test_full_researcher_passes_branding():
    html = render_researcher_report(
        {
            "researcher_name": "Dr. X",
            "institution": "U",
            "integrity_score": 50,
        },
        "narrative",
        branding={"name": "Acme U", "primary_color": "#003366"},
        annotations=[{"text": "On file.", "author_name": "Lab", "created_at": "2026-05-09"}],
    )
    assert "Acme U" in html
    assert "On file." in html


def test_institutional_audit_renders_each_researcher():
    items = [
        {
            "researcher_name": "Dr. Alpha",
            "institution": "U1",
            "official_h_index": 30,
            "adjusted_h_index": 28,
            "integrity_score": 75,
            "self_citation_rate": 0.1,
            "citation_ring_flags": {"flags": []},
        },
        {
            "researcher_name": "Dr. Beta",
            "institution": "U2",
            "integrity_score": 40,
            "self_citation_rate": 0.5,
            "citation_ring_flags": {"flags": ["mutual_citation_cluster"]},
        },
    ]
    html = render_institutional_audit_report(items)
    assert "Dr. Alpha" in html
    assert "Dr. Beta" in html
    assert "Audit" in html or "audit" in html


# ─── /generate validation ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_comparison_requires_two_ids():
    async def _db():
        yield _stub_db_with()

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: _user()

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post(
                "/api/reports/generate",
                json={"template": "comparison", "source_check_ids": ["s1"]},
            )
        assert r.status_code == 400
        assert "comparison" in r.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_audit_requires_two_ids():
    async def _db():
        yield _stub_db_with()

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: _user()

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post(
                "/api/reports/generate",
                json={
                    "template": "institutional_audit",
                    "researcher_profile_ids": ["r1"],
                },
            )
        assert r.status_code == 400
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_full_requires_input():
    async def _db():
        yield _stub_db_with()

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: _user()

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post("/api/reports/generate", json={"template": "full"})
        assert r.status_code == 400
    finally:
        app.dependency_overrides.clear()


# ─── Annotations ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_annotations_owner_check():
    """Owner mismatch returns 403, not 200."""
    report = SimpleNamespace(
        id="r1",
        user_id="user-other",
        deleted_at=None,
        annotations=None,
        pdf_path=None,
    )

    async def _db():
        yield _stub_db_with(scalar=report)

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: _user(id="user-a")

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.put(
                "/api/reports/r1/annotations",
                json={"annotations": [{"text": "note"}]},
            )
        assert r.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_annotations_too_many():
    """50-item cap rejected at the schema layer."""
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_current_user] = lambda: _user()

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.put(
                "/api/reports/r1/annotations",
                json={
                    "annotations": [{"text": f"n{i}"} for i in range(60)],
                },
            )
        assert r.status_code in (400, 422)
    finally:
        app.dependency_overrides.clear()


# ─── Schedules ────────────────────────────────────────────────────────────


def test_next_run_aligns_to_09_utc_weekly():
    """Regression: _next_run was previously just `base + 7 days`. It must
    now snap to 09:00 UTC on the target day so deliveries arrive at the
    documented time, not whenever the user happened to create the schedule."""
    from app.routers.report_schedules import _next_run

    # Created at 14:00 UTC Mon → next run shouldn't be Mon next week 14:00,
    # it should be the earliest 09:00 UTC after Mon next week 14:00, i.e.
    # Tue 09:00.
    base = datetime(2026, 5, 11, 14, 0, tzinfo=timezone.utc)
    nxt = _next_run("weekly", base=base)
    assert nxt.hour == 9 and nxt.minute == 0
    assert nxt > base + timedelta(days=7) - timedelta(seconds=1)


def test_next_run_aligns_to_09_utc_when_created_in_morning():
    """Created at 06:00 UTC → +7 days lands at 06:00 UTC, but we still want
    09:00 UTC delivery on that same day (since 09:00 is *after* 06:00)."""
    from app.routers.report_schedules import _next_run

    base = datetime(2026, 5, 11, 6, 0, tzinfo=timezone.utc)
    nxt = _next_run("weekly", base=base)
    assert nxt.hour == 9
    assert nxt.date() == (base + timedelta(days=7)).date()


def test_next_run_monthly_also_snaps():
    from app.routers.report_schedules import _next_run

    base = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    nxt = _next_run("monthly", base=base)
    assert nxt.hour == 9
    # 30 days later is 2026-06-10; 09:00 on that day is < 12:00 30-days-later,
    # so we expect the bump to 2026-06-11.
    assert nxt.date() == (base + timedelta(days=31)).date()


def test_next_run_after_matches_router_helper():
    """The Celery sweep's _next_run_after must use the same alignment as
    the router's _next_run — duplicated logic was the bug."""
    from app.routers.report_schedules import _next_run
    from app.tasks.scheduled_reports import _next_run_after

    base = datetime(2026, 5, 11, 14, 0, tzinfo=timezone.utc)
    assert _next_run_after("weekly", base) == _next_run("weekly", base)
    assert _next_run_after("monthly", base) == _next_run("monthly", base)


@pytest.mark.asyncio
async def test_schedule_rejects_multi_record_template():
    async def _db():
        yield _stub_db_with()

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: _user()

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post(
                "/api/me/report-schedules/",
                json={"frequency": "weekly", "template": "comparison"},
            )
        assert r.status_code == 400
        assert "Multi-record" in r.json()["detail"] or "multi" in r.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


# ─── Branding ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_branding_requires_admin_role():
    """Phase C: PUT branding now requires the org-admin role (was: any
    team-tier member). A user with no membership row hits the
    ``require_org_admin`` dep and gets a 403.
    """
    # Stub serves the org row for the dep's existence check, then nothing
    # for the membership query — so the dep sees "org exists but no
    # membership" → 403 "Org admin required".
    org = SimpleNamespace(
        id="org-1",
        name="Acme University",
        logo_url=None,
        primary_color=None,
        secondary_color=None,
    )
    db = AsyncMock()
    db.execute.side_effect = [
        SimpleNamespace(scalar_one_or_none=lambda: org),  # Organization
        SimpleNamespace(scalar_one_or_none=lambda: None),  # membership
    ]

    async def _db():
        yield db

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: _user(
        tier="free", organization_id="org-1"
    )

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.put(
                "/api/organizations/org-1/branding",
                json={"primary_color": "#003366"},
            )
        assert r.status_code == 403
        assert "admin" in r.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_branding_requires_org_membership():
    """User belonging to a different org → can't write the target's
    branding. require_org_admin still 403s because the membership query
    finds nothing for them in the URL org."""
    org = SimpleNamespace(
        id="org-OTHER",
        name="Other University",
        logo_url=None,
        primary_color=None,
        secondary_color=None,
    )
    db = AsyncMock()
    db.execute.side_effect = [
        SimpleNamespace(scalar_one_or_none=lambda: org),  # Organization
        SimpleNamespace(scalar_one_or_none=lambda: None),  # no membership
    ]

    async def _db():
        yield db

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: _user(
        tier="team", organization_id="org-1"
    )

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.put(
                "/api/organizations/org-OTHER/branding",
                json={"primary_color": "#003366"},
            )
        assert r.status_code == 403
    finally:
        app.dependency_overrides.clear()


# ─── Happy-path tests for the new endpoints ──────────────────────────────


def _stamp_timestamps(obj):
    """db.refresh is an AsyncMock no-op in tests; populate the timestamps +
    id (column-level defaults only fire on session flush) by hand so the
    response Pydantic model accepts the row."""
    import uuid

    now = datetime.now(timezone.utc)
    if getattr(obj, "id", None) is None:
        obj.id = str(uuid.uuid4())
    if getattr(obj, "created_at", None) is None:
        obj.created_at = now
    if getattr(obj, "updated_at", None) is None:
        obj.updated_at = now


@pytest.mark.asyncio
async def test_create_schedule_happy_path():
    """POST /api/me/report-schedules/ — success returns 201 + the persisted row."""
    db = AsyncMock()

    # Count check: empty list → user is below the 5-schedule cap.
    db.execute.return_value = SimpleNamespace(
        scalars=lambda: SimpleNamespace(all=lambda: [])
    )

    async def _refresh(obj):
        _stamp_timestamps(obj)

    db.refresh.side_effect = _refresh

    async def _db():
        yield db

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: _user()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post(
                "/api/me/report-schedules/",
                json={"frequency": "weekly", "template": "executive_summary"},
            )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["frequency"] == "weekly"
        assert body["template"] == "executive_summary"
        assert body["active"] is True
        assert body["user_id"] == "user-a"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_update_schedule_happy_path():
    """PATCH toggles active + recomputes next_run when frequency changes."""
    schedule = SimpleNamespace(
        id="s-1",
        user_id="user-a",
        frequency="weekly",
        template="executive_summary",
        active=True,
        last_run_at=None,
        next_run_at=datetime.now(timezone.utc) + timedelta(days=7),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db = AsyncMock()
    db.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: schedule)
    db.refresh.side_effect = lambda obj: None

    async def _db():
        yield db

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: _user()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.patch(
                "/api/me/report-schedules/s-1",
                json={"active": False, "frequency": "monthly"},
            )
        assert r.status_code == 200, r.text
        assert r.json()["frequency"] == "monthly"
        assert r.json()["active"] is False
        assert schedule.active is False
        assert schedule.frequency == "monthly"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_schedule_happy_path():
    schedule = SimpleNamespace(id="s-1", user_id="user-a")
    db = AsyncMock()
    db.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: schedule)

    async def _db():
        yield db

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: _user()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.delete("/api/me/report-schedules/s-1")
        assert r.status_code == 204
        db.delete.assert_called_once_with(schedule)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_schedules_returns_owned_only():
    own = SimpleNamespace(
        id="s-1",
        user_id="user-a",
        frequency="weekly",
        template="executive_summary",
        active=True,
        last_run_at=None,
        next_run_at=datetime.now(timezone.utc) + timedelta(days=7),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db = AsyncMock()
    db.execute.return_value = SimpleNamespace(
        scalars=lambda: SimpleNamespace(all=lambda: [own])
    )

    async def _db():
        yield db

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: _user()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/api/me/report-schedules/")
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 1
        assert body[0]["id"] == "s-1"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_branding_put_happy_path():
    """Org admin updating their own org's branding succeeds (Phase C).

    The dep stack now resolves:
      1. require_org_admin → loads Organization (must exist)
      2. require_org_admin → loads OrganizationMember (must be admin)
      3. handler → loads Organization again via db.get for the update
    The execute side_effect serves both query results in order.
    """
    org = SimpleNamespace(
        id="org-1",
        name="Acme University",
        logo_url=None,
        primary_color=None,
        secondary_color=None,
    )
    admin_membership = SimpleNamespace(
        organization_id="org-1",
        user_id="user-a",
        role="admin",
        joined_at=datetime.now(timezone.utc),
        invited_by=None,
    )
    db = AsyncMock()
    db.execute.side_effect = [
        SimpleNamespace(scalar_one_or_none=lambda: org),  # dep: Organization
        SimpleNamespace(scalar_one_or_none=lambda: admin_membership),  # dep: membership
    ]
    db.get.return_value = org  # handler's own db.get(Organization)
    db.refresh.side_effect = lambda obj: None

    async def _db():
        yield db

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: _user(
        tier="team", organization_id="org-1"
    )
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.put(
                "/api/organizations/org-1/branding",
                json={
                    "logo_url": "https://cdn.acme.edu/logo.png",
                    "primary_color": "#003366",
                    "secondary_color": "#cccccc",
                },
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["primary_color"] == "#003366"
        assert org.logo_url == "https://cdn.acme.edu/logo.png"
        assert org.primary_color == "#003366"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_annotations_put_happy_path():
    """Owner replacing the annotations list — server stamps author + timestamp,
    drops the cached pdf_path, returns the updated report."""
    report = SimpleNamespace(
        id="r1",
        user_id="user-a",
        source_check_id=None,
        researcher_profile_id=None,
        report_type="source_verification",
        title="Stub",
        summary="Stub",
        pdf_path=None,
        share_token="stub-token",
        share_expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        deleted_at=None,
        annotations=None,
        source_check_ids=None,
        researcher_profile_ids=None,
        template="full",
        created_at=datetime.now(timezone.utc),
    )
    db = AsyncMock()
    db.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: report)
    db.refresh.side_effect = lambda obj: None

    async def _db():
        yield db

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: _user()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.put(
                "/api/reports/r1/annotations",
                json={"annotations": [{"text": "Reviewed."}, {"text": "Looks fine."}]},
            )
        assert r.status_code == 200, r.text
        # Server stamps author_name + created_at on each entry.
        assert isinstance(report.annotations, list)
        assert len(report.annotations) == 2
        assert report.annotations[0]["text"] == "Reviewed."
        assert report.annotations[0]["author_name"] == "Test User"
        assert report.annotations[0]["created_at"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_run_due_schedules_with_non_empty_input(monkeypatch):
    """Sweep runs for an active overdue schedule and inserts a Report row.
    Stubs PDF rendering since WeasyPrint isn't available in pure unit tests."""
    from app.tasks import scheduled_reports

    # Stub PDF generation — we want to verify the orchestration, not the bytes.
    monkeypatch.setattr(
        scheduled_reports, "html_to_pdf", lambda html: b"%PDF-stub"
    )
    monkeypatch.setattr(
        scheduled_reports, "save_pdf", lambda b: "/tmp/stub.pdf"
    )

    schedule = SimpleNamespace(
        id="s-1",
        user_id="user-a",
        frequency="weekly",
        template="executive_summary",
        active=True,
        last_run_at=None,
        next_run_at=datetime.now(timezone.utc) - timedelta(hours=1),  # overdue
    )
    user = SimpleNamespace(
        id="user-a",
        deactivated_at=None,
        deleted_at=None,
        tier="free",
        organization_id=None,
    )
    check = SimpleNamespace(
        id="sc-1",
        user_id="user-a",
        overall_credibility_score=80.0,
        ai_content_percentage=10.0,
        misinfo_claims_found=1,
        created_at=datetime.now(timezone.utc) - timedelta(days=2),
        deleted_at=None,
    )

    call_count = {"n": 0}

    def execute_side_effect(_q):
        call_count["n"] += 1
        if call_count["n"] == 1:  # active overdue schedules
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [schedule]))
        if call_count["n"] == 2:  # checks in window
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [check]))
        if call_count["n"] == 3:  # owner user lookup
            return SimpleNamespace(scalar_one_or_none=lambda: user)
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))

    db = AsyncMock()
    db.execute.side_effect = execute_side_effect

    added: list = []
    db.add = lambda obj: added.append(obj)

    count = await scheduled_reports.run_due_schedules(db)
    assert count == 1
    # Schedule advanced past now so the next sweep doesn't re-fire.
    assert schedule.last_run_at is not None
    assert schedule.next_run_at > datetime.now(timezone.utc)
    # A Report was queued for insertion.
    from app.models import Report

    assert any(isinstance(o, Report) for o in added)
