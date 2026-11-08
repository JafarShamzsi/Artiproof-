"""Tests for the new source-check features: bulk, history filters, rerun,
share token, and lightweight export.

These exercise the route layer's contract — ownership checks, idempotency,
filter shape, share-token flow, and export formats — without spinning up
a real DB. Where the routes read/write specific rows, we use SimpleNamespace
stubs and an in-memory fake AsyncSession.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app
from app.models.source_check import (
    AIDetectionResult,
    CitationCheck,
    ClaimAnalysis,
    SourceCheck,
)
from app.utils.auth import (
    get_current_user,
    get_current_user_allow_deactivated,
)


def _user(**overrides):
    base = SimpleNamespace(
        id="user-a",
        email="user-a@example.com",
        full_name="Test User",
        role="researcher",
        tier="free",
        locale="en",
        hashed_password=None,
        deactivated_at=None,
        deleted_at=None,
        email_verified_at=None,
        totp_secret=None,
        totp_enabled=False,
        totp_backup_codes=None,
        linked_providers=None,
        analysis_preferences=None,
        notification_preferences=None,
        pinned_items=None,
        organization_id=None,
        share_activity_with_team=True,
        institution=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


def _check(**overrides):
    base = SimpleNamespace(
        id="sc-1",
        user_id="user-a",
        input_type="url",
        input_content="https://example.com/article",
        input_title="Example article",
        status="completed",
        overall_credibility_score=82.0,
        ai_content_percentage=12.0,
        misinfo_claims_found=2,
        original_pdf_path=None,
        annotated_pdf_path=None,
        text_position_map=None,
        score_breakdown=None,
        model_metadata=None,
        share_token=None,
        deleted_at=None,
        completed_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


@pytest.fixture
def env(monkeypatch):
    """get_db + get_current_user wired to a fake AsyncSession + stub user.
    Tests mutate `env.checks` to seed state and override `env.db.execute`/
    `env.db.get` per scenario."""
    from app.tasks import celery_app

    if celery_app is not None:
        monkeypatch.setattr(celery_app, "send_task", Mock())
    user = _user()
    db = AsyncMock()

    # Default: every execute returns empty
    class _Empty:
        def all(self):
            return []

        def scalars(self):
            return SimpleNamespace(all=lambda: [], first=lambda: None)

        def scalar_one_or_none(self):
            return None

        def scalar_one(self):
            return None

        def scalar(self):
            return 0

    db.execute.return_value = _Empty()

    async def _db_dep():
        yield db

    app.dependency_overrides[get_db] = _db_dep
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_user_allow_deactivated] = lambda: user

    yield SimpleNamespace(user=user, db=db, checks={})
    app.dependency_overrides.clear()


# ─── History filters ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_accepts_filter_query_params(env):
    """The route should accept q/min_score/max_score/status/sort without error.
    We don't assert the SQL; we just confirm the param shape doesn't 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get(
            "/api/source-check/",
            params={
                "q": "climate",
                "min_score": 40,
                "max_score": 90,
                "status": "completed",
                "sort": "score_desc",
                "page": 1,
                "page_size": 20,
            },
        )
    assert r.status_code == 200
    body = r.json()
    assert body["page"] == 1
    assert body["page_size"] == 20


@pytest.mark.asyncio
async def test_list_rejects_invalid_sort(env):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/source-check/", params={"sort": "garbage"})
    assert r.status_code == 422


# ─── Batch poll ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_batch_returns_owned_checks(env):
    chk = _check(id="sc-mine")

    class _R:
        def scalars(self):
            return SimpleNamespace(all=lambda: [chk])

    env.db.execute.return_value = _R()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/source-check/batch", params={"ids": "sc-mine,sc-2"})
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["id"] == "sc-mine"


@pytest.mark.asyncio
async def test_batch_requires_ids(env):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/source-check/batch")
    assert r.status_code == 422


# ─── Bulk ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bulk_rejects_empty_items(env):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/source-check/bulk", json={"items": []})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_bulk_rejects_unsupported_type(env):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/source-check/bulk",
            json={
                "items": [
                    {"input_type": "ocr", "input_content": "anything"},
                ]
            },
        )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_bulk_caps_at_50(env):
    items = [{"input_type": "text", "input_content": f"x{i}"} for i in range(51)]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/source-check/bulk", json={"items": items})
    assert r.status_code == 400


# ─── Rerun ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rerun_404_when_not_found(env):
    """Empty execute means scalar_one_or_none() returns None → 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/source-check/no-such/rerun")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_rerun_403_for_other_user(env):
    other = _check(id="sc-other", user_id="someone-else")

    class _R:
        def scalar_one_or_none(self):
            return other

        def scalars(self):
            return SimpleNamespace(all=lambda: [])

    env.db.execute.return_value = _R()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/source-check/sc-other/rerun")
    assert r.status_code == 403


# ─── Share token ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_issue_share_token_is_idempotent(env):
    """Calling /share-token twice should return the same token."""
    chk = _check(share_token=None)

    class _R:
        def scalar_one_or_none(self):
            return chk

    env.db.execute.return_value = _R()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r1 = await c.post("/api/source-check/sc-1/share-token")
        # After first call, the token is on the row. Mock the next response.
        token1 = r1.json()["share_token"]
        # Re-issuing returns the same token because the column is now set.
        r2 = await c.post("/api/source-check/sc-1/share-token")
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["share_token"] == token1
    assert r2.json()["share_token"] == token1
    assert chk.share_token == token1
    # share_url uses APP_URL from settings
    assert r1.json()["share_url"].endswith(f"/check/shared/{token1}")


@pytest.mark.asyncio
async def test_revoke_share_token_clears_column(env):
    chk = _check(share_token="abc123")

    class _R:
        def scalar_one_or_none(self):
            return chk

    env.db.execute.return_value = _R()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.delete("/api/source-check/sc-1/share-token")
    assert r.status_code == 204
    assert chk.share_token is None


@pytest.mark.asyncio
async def test_get_shared_404_when_token_unknown():
    """No auth required for the public route, but the dep override on
    get_db still helps us return an empty result set."""
    db = AsyncMock()

    class _Empty:
        def scalar_one_or_none(self):
            return None

    db.execute.return_value = _Empty()

    async def _db_dep():
        yield db

    app.dependency_overrides[get_db] = _db_dep
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/api/source-check/shared/no-such-token")
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()


# ─── Export ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_export_json_contains_check_metadata(env):
    chk = _check(input_title="My check")

    call_count = {"n": 0}

    async def execute_side_effect(_q):
        call_count["n"] += 1
        # 1st call: select(SourceCheck) → scalar_one_or_none returns chk
        if call_count["n"] == 1:
            return SimpleNamespace(scalar_one_or_none=lambda: chk)
        # 2nd-4th: claims, ai, citations queries — empty
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))

    env.db.execute.side_effect = execute_side_effect
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/source-check/sc-1/export?format=json")
    assert r.status_code == 200
    body = json.loads(r.content)
    assert body["id"] == "sc-1"
    assert body["input_title"] == "My check"
    assert body["claims"] == []


@pytest.mark.asyncio
async def test_export_csv_format(env):
    chk = _check(input_title="My check")
    claim = SimpleNamespace(
        id="cl-1", claim_text="Statement", verdict="false",
        confidence=0.92, explanation="why", true_version=None,
        sources=None, origin_trace=None, position_in_text=None,
    )

    call_count = {"n": 0}

    async def execute_side_effect(_q):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return SimpleNamespace(scalar_one_or_none=lambda: chk)
        if call_count["n"] == 2:  # claims
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [claim]))
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))

    env.db.execute.side_effect = execute_side_effect

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/source-check/sc-1/export?format=csv")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    rows = list(csv.reader(io.StringIO(r.text)))
    # Header + 1 data row
    assert len(rows) == 2
    assert rows[0][0] == "check_id"
    assert rows[1][0] == "sc-1"
    assert rows[1][2] == "claim"
    assert rows[1][4] == "false"


# ─── SSE auth (stream tickets) ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_stream_ticket_owner_gets_ticket(env):
    """Owner of a check can mint a stream ticket."""
    chk = _check(id="sc-1", user_id="user-a")
    env.db.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: chk)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/source-check/sc-1/stream-ticket")
    assert r.status_code == 200
    assert r.json()["ticket"]


@pytest.mark.asyncio
async def test_stream_ticket_non_owner_403(env):
    """Non-owner can't mint a ticket — closes the unauth-amplification hole."""
    chk = _check(id="sc-1", user_id="user-OTHER")
    env.db.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: chk)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/source-check/sc-1/stream-ticket")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_stream_endpoint_requires_ticket():
    """SSE without a ticket query param 422s — FastAPI rejects the missing
    required Query parameter before any handler logic runs."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/source-check/sc-1/stream")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_stream_endpoint_rejects_bad_ticket():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/source-check/sc-1/stream?ticket=garbage")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_stream_endpoint_rejects_ticket_for_other_resource():
    """Ticket issued for sc-1 must not be reusable on sc-2."""
    from app.utils.auth import create_stream_ticket

    ticket = create_stream_ticket("user-a", "source_check", "sc-1")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get(f"/api/source-check/sc-2/stream?ticket={ticket}")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_stream_endpoint_rejects_researcher_ticket_on_source_check():
    """Cross-kind reuse — a researcher_profile ticket can't open a source_check stream."""
    from app.utils.auth import create_stream_ticket

    ticket = create_stream_ticket("user-a", "researcher_profile", "sc-1")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get(f"/api/source-check/sc-1/stream?ticket={ticket}")
    assert r.status_code == 403
