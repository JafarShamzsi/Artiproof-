"""Tests for the new report-features batch:
- Template renderers (smoke).
- POST /api/reports/generate validation for new templates + multi-input.
- PUT /api/reports/{id}/annotations.
- /api/me/report-schedules CRUD basics.
- /api/organizations/{id}/branding tier gating.
"""

from __future__ import annotations

from datetime import datetime, timezone
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
    db.execute.return_value per-call."""
    db = AsyncMock()
    result = SimpleNamespace(
        scalars=lambda: SimpleNamespace(all=lambda: rows or []),
        scalar_one_or_none=lambda: scalar,
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
async def test_branding_requires_team_tier():
    async def _db():
        yield _stub_db_with()

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
        assert "team" in r.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_branding_requires_org_membership():
    """Team-tier user not in the target org → 403."""
    async def _db():
        yield _stub_db_with()

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
