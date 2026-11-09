"""Phase E telemetry tests: Gemini cost helpers + Celery DLQ surface.

Focuses on the pure-function path (``estimate_cost_usd``, signal
serialization) and the admin DLQ retry endpoint using the in-memory db
stub from ``test_admin_endpoints``. The Gemini metric write itself is
fire-and-forget against a real Postgres — covered by an integration
spec out of this unit suite.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app
from app.services.gemini import GEMINI_PRICING, estimate_cost_usd
from app.services.gemini.client import _FALLBACK_PRICE
from app.utils.auth import get_current_user


# ─── estimate_cost_usd ───────────────────────────────────────────────────


def test_cost_is_zero_when_no_tokens():
    assert (
        estimate_cost_usd(input_tokens=0, output_tokens=0, model="gemini-2.0-flash")
        == 0.0
    )


def test_cost_uses_published_pricing_for_known_model():
    # gemini-2.0-flash: $0.10/1M in, $0.40/1M out (from GEMINI_PRICING).
    # 1M in + 1M out = 0.10 + 0.40 = 0.50.
    cost = estimate_cost_usd(
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        model="gemini-2.0-flash",
    )
    assert cost == 0.5


def test_cost_falls_back_for_unknown_model():
    # Unknown model takes the conservative fallback (midpoint). The exact
    # number isn't important; what matters is it's non-zero and matches
    # the documented fallback.
    cost = estimate_cost_usd(
        input_tokens=1_000_000,
        output_tokens=0,
        model="gemini-2026-fictional",
    )
    assert cost == _FALLBACK_PRICE["input_per_1m"]


def test_pricing_table_covers_default_model():
    # The default Gemini model declared in app.config.settings.GEMINI_MODEL
    # should always have an explicit price so dashboards don't fall back.
    from app.config import settings

    assert settings.GEMINI_MODEL in GEMINI_PRICING, (
        f"Default model {settings.GEMINI_MODEL} missing from GEMINI_PRICING — "
        "price the new default or the cost dashboard will lie."
    )


# ─── Admin DLQ endpoints ─────────────────────────────────────────────────


def _admin(**overrides):
    base = SimpleNamespace(
        id="admin-1",
        email="admin@example.com",
        full_name="Admin",
        role="admin",
        tier="team",
        organization_id=None,
        deactivated_at=None,
        deleted_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        email_verified_at=None,
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


def _researcher(**overrides):
    base = _admin()
    base.role = "researcher"
    return base


def _make_dlq_row(*, id="dlq-1", resolved_at=None):
    return SimpleNamespace(
        id=id,
        task_name="source_check.run_pipeline",
        task_id="task-1",
        args=["check-123"],
        kwargs={},
        exception_class="TimeoutError",
        exception_message="Gemini timeout",
        traceback="traceback...",
        retry_count=3,
        failed_at=datetime.now(timezone.utc),
        resolved_at=resolved_at,
        resolved_by_user_id=None,
    )


class _DlqDb:
    """Minimal fake supporting db.get + db.commit."""

    def __init__(self, row=None):
        self.row = row
        self.commit = AsyncMock()

    async def get(self, model, pk):
        from app.models.celery_dlq import CeleryDLQ

        if model is CeleryDLQ and self.row is not None and self.row.id == pk:
            return self.row
        return None

    async def execute(self, _q):
        class _R:
            def scalars(self):
                class _S:
                    def all(self_inner):
                        return []
                return _S()
        return _R()


@pytest.mark.asyncio
async def test_dlq_retry_requires_admin(monkeypatch):
    db = _DlqDb()

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: _researcher()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as client:
            r = await client.post("/api/admin/celery/dlq/dlq-1/retry")
        assert r.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_dlq_retry_404_when_missing():
    db = _DlqDb(row=None)

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: _admin()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as client:
            r = await client.post("/api/admin/celery/dlq/dlq-missing/retry")
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_dlq_retry_marks_resolved_even_when_celery_unavailable(monkeypatch):
    """When celery_app is None (no Redis in tests), retry should still
    mark the row resolved so the operator can move on. The response
    signals enqueued=False so the operator knows."""
    row = _make_dlq_row()
    db = _DlqDb(row=row)

    # Force celery_app=None to simulate a worker-less environment.
    import app.tasks as tasks_module

    monkeypatch.setattr(tasks_module, "celery_app", None)

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: _admin()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as client:
            r = await client.post("/api/admin/celery/dlq/dlq-1/retry")
        assert r.status_code == 200
        body = r.json()
        assert body["enqueued"] is False
        assert body["new_task_id"] is None
        assert body["dlq_id"] == "dlq-1"
        # The handler should also stamp the DLQ row.
        assert row.resolved_at is not None
        assert row.resolved_by_user_id == "admin-1"
        db.commit.assert_awaited()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_dlq_retry_409_when_already_resolved():
    row = _make_dlq_row(resolved_at=datetime.now(timezone.utc))
    db = _DlqDb(row=row)

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: _admin()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as client:
            r = await client.post("/api/admin/celery/dlq/dlq-1/retry")
        assert r.status_code == 409
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_dlq_retry_enqueues_via_celery_when_available(monkeypatch):
    row = _make_dlq_row()
    db = _DlqDb(row=row)

    fake_async_result = SimpleNamespace(id="new-task-99")
    fake_app = MagicMock()
    fake_app.send_task.return_value = fake_async_result

    import app.tasks as tasks_module

    monkeypatch.setattr(tasks_module, "celery_app", fake_app)

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: _admin()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as client:
            r = await client.post("/api/admin/celery/dlq/dlq-1/retry")
        assert r.status_code == 200
        body = r.json()
        assert body["enqueued"] is True
        assert body["new_task_id"] == "new-task-99"
        fake_app.send_task.assert_called_once()
        # Args/kwargs from the DLQ row must be passed verbatim.
        call_args = fake_app.send_task.call_args
        assert call_args.args[0] == "source_check.run_pipeline"
        assert call_args.kwargs["args"] == ["check-123"]
        assert call_args.kwargs["kwargs"] == {}
    finally:
        app.dependency_overrides.clear()
