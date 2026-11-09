"""Billing scaffolding — apply_tier_change + webhook.

Two things being pinned:

1. ``apply_tier_change`` is the single chokepoint for mutating
   ``user.tier``. Every call writes a matching ``tier_change_audits``
   row in the same session. Unknown tiers raise ``UnknownTierError``
   without touching the user.

2. The webhook landing pad:
   - 401s on missing or wrong HMAC signature.
   - 404s on unknown processor (per the env config).
   - 400s on invalid JSON or missing required keys.
   - is idempotent on ``(processor, processor_event_id)`` — the second
     submission of the same event returns ``"duplicate"`` and applies
     nothing.
   - dispatches off ``event_type`` → ``apply_tier_change`` when the
     event type is mapped AND the user matches.
   - 200s on unknown event types so the processor doesn't retry forever;
     the row still lands in ``billing_events`` for audit.

Pure-stub tests where the route surface is the contract. The DB stub
mimics enough of an AsyncSession that the webhook's flow (add →
flush → unique-constraint check → commit) round-trips correctly.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.main import app
from app.services.billing import apply_tier_change
from app.services.billing.tier_change import UnknownTierError


# ─── apply_tier_change ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_apply_tier_change_records_transition_and_audit():
    """The happy path: mutates user.tier and adds a TierChangeAudit row
    with the right shape. The caller (not the helper) commits."""
    user = SimpleNamespace(id="u1", tier="free")
    db = AsyncMock()
    db.add = lambda obj: db._added.append(obj)
    db._added = []  # type: ignore[attr-defined]

    audit = await apply_tier_change(
        db,
        user,
        "pro",
        reason="admin_panel",
        actor=SimpleNamespace(id="admin-1"),
    )
    assert user.tier == "pro"
    assert audit.from_tier == "free"
    assert audit.to_tier == "pro"
    assert audit.reason == "admin_panel"
    assert audit.changed_by_user_id == "admin-1"
    # The helper never commits — caller's responsibility.
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_apply_tier_change_records_no_op():
    """When the new tier matches the current tier, still write an audit
    row (from_tier == to_tier). Makes re-fired webhook events provably
    absorbed rather than silently dropped."""
    user = SimpleNamespace(id="u1", tier="pro")
    db = AsyncMock()
    db.add = lambda obj: db._added.append(obj)
    db._added = []  # type: ignore[attr-defined]

    audit = await apply_tier_change(
        db, user, "pro", reason="billing_webhook"
    )
    assert user.tier == "pro"
    assert audit.from_tier == "pro"
    assert audit.to_tier == "pro"
    assert audit.reason == "billing_webhook"


@pytest.mark.asyncio
async def test_apply_tier_change_rejects_unknown_tier():
    user = SimpleNamespace(id="u1", tier="free")
    db = AsyncMock()
    db.add = lambda obj: db._added.append(obj)
    db._added = []  # type: ignore[attr-defined]
    with pytest.raises(UnknownTierError):
        await apply_tier_change(
            db, user, "enterprise", reason="admin_panel"
        )
    # User wasn't mutated.
    assert user.tier == "free"


@pytest.mark.asyncio
async def test_apply_tier_change_requires_reason():
    user = SimpleNamespace(id="u1", tier="free")
    db = AsyncMock()
    with pytest.raises(ValueError):
        await apply_tier_change(db, user, "pro", reason="")


@pytest.mark.asyncio
async def test_apply_tier_change_links_billing_event():
    user = SimpleNamespace(id="u1", tier="free")
    db = AsyncMock()
    db.add = lambda obj: db._added.append(obj)
    db._added = []  # type: ignore[attr-defined]
    billing_event = SimpleNamespace(id="bev-1")

    audit = await apply_tier_change(
        db,
        user,
        "pro",
        reason="billing_webhook",
        billing_event=billing_event,
    )
    assert audit.billing_event_id == "bev-1"


# ─── Webhook signature + processor validation ──────────────────────────────


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


@pytest.fixture
def stub_processor(monkeypatch):
    """Inject a stub processor with a known secret. Tests share this
    fixture so the env mutation rolls back automatically."""
    monkeypatch.setattr(
        "app.config.settings.BILLING_WEBHOOK_SECRETS", {"stub": "test-secret"}
    )
    return "stub", "test-secret"


class _WebhookDb:
    """Minimal AsyncSession stand-in for the webhook handler.

    Tracks the row added via ``add`` so the test can assert on it,
    and lets the test set ``flush_raises`` to simulate a unique
    constraint collision (idempotency test).
    """

    def __init__(self, *, user=None, flush_raises=False):
        self.user = user
        self.flush_raises = flush_raises
        self.added: list = []
        self.committed = False
        self.rolled_back = False

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        if self.flush_raises:
            raise IntegrityError("dup", params=None, orig=Exception("dup"))

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True

    async def get(self, model, pk):
        from app.models.user import User as UserModel

        if model is UserModel and self.user is not None and self.user.id == pk:
            return self.user
        return None

    async def execute(self, q):
        # The webhook does a few SELECTs to find the user. Return a
        # result that yields self.user when sub_id matches; otherwise
        # None. This isn't full SQL, just enough that the user lookup
        # behaves how the test expects.
        u = self.user

        class _R:
            def scalar_one_or_none(_self):
                return u

        return _R()


def _wire_db(monkeypatch, db):
    async def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_webhook_404_on_unknown_processor(monkeypatch):
    monkeypatch.setattr("app.config.settings.BILLING_WEBHOOK_SECRETS", {})
    _wire_db(monkeypatch, _WebhookDb())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/billing/webhook/unknown",
            content=b"{}",
            headers={"X-ArtiProof-Signature": "anything"},
        )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_webhook_401_without_signature(stub_processor, monkeypatch):
    proc, _secret = stub_processor
    _wire_db(monkeypatch, _WebhookDb())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(f"/api/billing/webhook/{proc}", content=b"{}")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_webhook_401_on_bad_signature(stub_processor, monkeypatch):
    proc, _secret = stub_processor
    _wire_db(monkeypatch, _WebhookDb())
    body = b'{"id":"e1","event_type":"x"}'
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            f"/api/billing/webhook/{proc}",
            content=body,
            headers={"X-ArtiProof-Signature": "0" * 64},  # wrong but right length
        )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_webhook_400_on_missing_required_keys(
    stub_processor, monkeypatch
):
    proc, secret = stub_processor
    _wire_db(monkeypatch, _WebhookDb())
    body = b"{}"
    sig = _sign(secret, body)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            f"/api/billing/webhook/{proc}",
            content=body,
            headers={"X-ArtiProof-Signature": sig},
        )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_webhook_defers_tier_event_when_user_unknown(
    stub_processor, monkeypatch
):
    """Recognized tier-change event + no matching user → 202 deferred.

    Older behavior committed the billing_event row even with no user
    match, which triggered the unique (processor, processor_event_id)
    constraint on every retry — silently swallowing the upgrade
    forever. The handler now rolls back the row so the processor's
    next retry can land it as soon as the user record exists.
    """
    proc, secret = stub_processor
    db = _WebhookDb(user=None)
    _wire_db(monkeypatch, db)
    payload = {
        "id": "evt-1",
        "event_type": "subscription.activated.pro",
        "subscription_id": "sub-nope",
    }
    body = json.dumps(payload).encode("utf-8")
    sig = _sign(secret, body)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            f"/api/billing/webhook/{proc}",
            content=body,
            headers={"X-ArtiProof-Signature": sig},
        )
    assert r.status_code == 202
    body_json = r.json()
    assert body_json["status"] == "deferred"
    assert body_json["reason"] == "user_not_found"
    # Roll back, NOT commit — otherwise the unique constraint on
    # (processor, processor_event_id) deduplicates every retry to a
    # no-op and the user never gets upgraded.
    assert db.rolled_back is True
    assert db.committed is False


@pytest.mark.asyncio
async def test_webhook_applies_tier_change_when_user_matches(
    stub_processor, monkeypatch
):
    """User found AND event_type mapped → apply_tier_change runs and
    the response confirms ``status="applied"``. A TierChangeAudit row
    also lands in the session."""
    proc, secret = stub_processor
    user = SimpleNamespace(
        id="u1",
        tier="free",
        subscription_id="sub-1",
        organization_id=None,
        email="u1@example.com",
    )
    db = _WebhookDb(user=user)
    _wire_db(monkeypatch, db)
    payload = {
        "id": "evt-2",
        "event_type": "subscription.activated.pro",
        "subscription_id": "sub-1",
    }
    body = json.dumps(payload).encode("utf-8")
    sig = _sign(secret, body)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            f"/api/billing/webhook/{proc}",
            content=body,
            headers={"X-ArtiProof-Signature": sig},
        )
    assert r.status_code == 200
    assert r.json()["status"] == "applied"
    assert user.tier == "pro"
    assert db.committed is True
    # Both BillingEvent and TierChangeAudit rows should be in the
    # session.
    class_names = {o.__class__.__name__ for o in db.added}
    assert "BillingEvent" in class_names
    assert "TierChangeAudit" in class_names


@pytest.mark.asyncio
async def test_webhook_is_idempotent_on_duplicate_event(
    stub_processor, monkeypatch
):
    """A redelivered webhook (unique violation on (processor,
    processor_event_id)) returns 200 with ``status="duplicate"`` and
    applies nothing."""
    proc, secret = stub_processor
    user = SimpleNamespace(
        id="u1",
        tier="free",
        subscription_id="sub-1",
        organization_id=None,
        email="u1@example.com",
    )
    db = _WebhookDb(user=user, flush_raises=True)
    _wire_db(monkeypatch, db)
    payload = {
        "id": "evt-3",
        "event_type": "subscription.activated.pro",
        "subscription_id": "sub-1",
    }
    body = json.dumps(payload).encode("utf-8")
    sig = _sign(secret, body)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            f"/api/billing/webhook/{proc}",
            content=body,
            headers={"X-ArtiProof-Signature": sig},
        )
    assert r.status_code == 200
    assert r.json()["status"] == "duplicate"
    assert user.tier == "free"  # NOT mutated on duplicate
    assert db.rolled_back is True


@pytest.mark.asyncio
async def test_webhook_logs_unknown_event_type_without_failing(
    stub_processor, monkeypatch
):
    """Unknown event_type → ``status="logged"``, no tier change. The
    processor must NOT retry a logged event."""
    proc, secret = stub_processor
    user = SimpleNamespace(
        id="u1",
        tier="free",
        subscription_id="sub-1",
        organization_id=None,
        email="u1@example.com",
    )
    db = _WebhookDb(user=user)
    _wire_db(monkeypatch, db)
    payload = {
        "id": "evt-4",
        "event_type": "some.unknown.event",
        "subscription_id": "sub-1",
    }
    body = json.dumps(payload).encode("utf-8")
    sig = _sign(secret, body)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            f"/api/billing/webhook/{proc}",
            content=body,
            headers={"X-ArtiProof-Signature": sig},
        )
    assert r.status_code == 200
    assert r.json()["status"] == "logged"
    assert user.tier == "free"


# ─── Sales inquiry ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sales_inquiry_accepts_minimal_payload(monkeypatch):
    """Anonymous inquiry with just email + name lands as a sales_leads
    row. The response confirms receipt without leaking the id."""
    class _DB:
        def __init__(self):
            self.added: list = []
            self.committed = False

        def add(self, obj):
            self.added.append(obj)

        async def commit(self):
            self.committed = True

        async def refresh(self, obj):
            return obj

    db = _DB()

    async def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/sales/inquiry",
            json={
                "email": "dean@university.edu",
                "name": "Dean Smith",
            },
        )
    assert r.status_code == 201
    assert r.json()["received"] is True
    # A SalesLead row should have been added.
    assert any(o.__class__.__name__ == "SalesLead" for o in db.added)
    lead = next(o for o in db.added if o.__class__.__name__ == "SalesLead")
    assert lead.email == "dean@university.edu"
    assert lead.name == "Dean Smith"
    assert lead.user_id is None  # anonymous


@pytest.mark.asyncio
async def test_sales_inquiry_rejects_bad_email(monkeypatch):
    class _DB:
        def add(self, obj):
            pass

        async def commit(self):
            pass

        async def refresh(self, obj):
            return obj

    async def _get_db():
        yield _DB()

    app.dependency_overrides[get_db] = _get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/sales/inquiry",
            json={"email": "not-an-email", "name": "X"},
        )
    assert r.status_code == 422
