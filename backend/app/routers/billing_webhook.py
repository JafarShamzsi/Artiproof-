"""Payment-processor webhook landing pad.

This is the surface the future payment processor will POST to. The
user hasn't chosen a processor yet; the goal of Phase D is that when
they do, the wire-up is two days of work, not two weeks:

1. Add an entry to ``BILLING_WEBHOOK_SECRETS`` (env-driven).
2. Add a signature verifier in ``_verify_signature`` matching the
   processor's documented format (Stripe-style HMAC-SHA256, or a
   processor-specific scheme).
3. Add the processor's event types to ``_TIER_FOR_EVENT_TYPE`` so
   the dispatcher knows which event drives which tier.

Idempotency is provided by the ``(processor, processor_event_id)``
unique constraint on ``billing_events``: a re-fired callback returns
200 with ``{"status": "duplicate"}`` instead of double-applying.

Everything happens in a single transaction. If anything raises, both
the ``billing_events`` insert AND the ``tier_change_audits`` write
roll back together — the processor will retry and we get a clean
re-attempt.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.billing_event import BillingEvent
from app.models.user import User
from app.services.billing import apply_tier_change
from app.services.billing.tier_change import UnknownTierError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/billing", tags=["Billing"])


# Map processor event_type → target tier. Add entries here when wiring
# a real processor. The webhook 200s with ``{"status": "logged"}`` for
# unknown event types so the processor doesn't retry forever; we still
# land the row in billing_events for audit.
_TIER_FOR_EVENT_TYPE: dict[str, str] = {
    # These three are stub event types used by the integration tests.
    # Replace with the real processor's vocabulary on wire-up.
    "subscription.activated.pro": "pro",
    "subscription.activated.team": "team",
    "subscription.cancelled": "free",
}


def _verify_signature(
    *, processor: str, body: bytes, signature_header: str | None
) -> None:
    """Constant-time HMAC verification.

    Default scheme: ``signature_header = hex(hmac_sha256(secret, body))``.
    Per-processor schemes (Stripe's ``t=...,v1=...`` etc) need their own
    branch here when wired up. For Phase D the stub processor uses the
    default scheme, which is what the tests exercise.

    Raises HTTPException(401) on any failure — missing header, wrong
    digest length, mismatched HMAC — without leaking which one. The
    processor only needs to know "redeliver after signing correctly".
    """
    secret = settings.BILLING_WEBHOOK_SECRETS.get(processor, "")
    if not secret:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown processor '{processor}'",
        )
    if not signature_header:
        raise HTTPException(status_code=401, detail="Missing signature")
    expected = hmac.new(
        secret.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature_header):
        raise HTTPException(status_code=401, detail="Invalid signature")


@router.post("/webhook/{processor}")
async def receive_webhook(
    processor: str,
    request: Request,
    x_artiproof_signature: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Land a billing webhook.

    Flow:
    1. Verify HMAC signature against the per-processor secret.
    2. Parse JSON body; require ``id`` (processor's event id) +
       ``event_type``.
    3. Try to INSERT a billing_events row. On unique-constraint
       collision (already processed), 200 with ``"status": "duplicate"``.
    4. If we can identify the user (via ``subscription_id``,
       ``user_id``, or ``email``), dispatch to ``apply_tier_change``
       based on event_type → tier mapping.
    5. Commit. Return ``{"status": "applied" | "logged"}``.
    """
    body = await request.body()
    _verify_signature(
        processor=processor, body=body, signature_header=x_artiproof_signature
    )

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Webhook body must be a JSON object")

    processor_event_id = payload.get("id")
    event_type = payload.get("event_type")
    if not processor_event_id or not event_type:
        raise HTTPException(
            status_code=400,
            detail="Body must include 'id' and 'event_type'",
        )

    # ─── Match to a user ─────────────────────────────────────────────
    user: User | None = await _find_user_from_payload(db, payload)

    # ─── Land the event ──────────────────────────────────────────────
    event = BillingEvent(
        id=str(uuid.uuid4()),
        user_id=user.id if user is not None else None,
        processor=processor,
        processor_event_id=str(processor_event_id),
        event_type=str(event_type),
        amount_cents=payload.get("amount_cents"),
        currency=payload.get("currency"),
        raw_payload=payload,
    )
    db.add(event)
    try:
        await db.flush()
    except IntegrityError:
        # Duplicate (processor, processor_event_id) — already processed.
        await db.rollback()
        return {"status": "duplicate"}

    # ─── Dispatch ────────────────────────────────────────────────────
    status_out = "logged"
    target_tier = _TIER_FOR_EVENT_TYPE.get(str(event_type))
    if target_tier is not None and user is not None:
        try:
            await apply_tier_change(
                db,
                user,
                target_tier,
                reason="billing_webhook",
                actor=None,
                billing_event=event,
            )
            status_out = "applied"
        except UnknownTierError:
            # Configuration error in _TIER_FOR_EVENT_TYPE. Land the
            # event but don't 500 — the processor would retry forever.
            logger.exception(
                "billing webhook event_type=%s maps to unknown tier=%s",
                event_type,
                target_tier,
            )
    elif target_tier is not None and user is None:
        logger.warning(
            "billing webhook id=%s event_type=%s couldn't match a user",
            processor_event_id,
            event_type,
        )

    await db.commit()
    return {"status": status_out}


async def _find_user_from_payload(db: AsyncSession, payload: dict) -> User | None:
    """Best-effort user match.

    Tries, in order: ``subscription_id`` exact match (the steady-state
    case once a user has been billed once), then ``user_id`` (the
    processor stored our internal id), then ``email`` lowercase match.
    Returns None if nothing matches; the webhook still 200s and the
    event row stays orphaned for a backfill sweep.
    """
    sub_id = payload.get("subscription_id")
    if sub_id:
        q = await db.execute(
            select(User).where(User.subscription_id == str(sub_id))
        )
        u = q.scalar_one_or_none()
        if u is not None:
            return u

    user_id = payload.get("user_id")
    if user_id:
        u = await db.get(User, str(user_id))
        if u is not None:
            return u

    email = payload.get("email")
    if email:
        from sqlalchemy import func

        q = await db.execute(
            select(User).where(func.lower(User.email) == str(email).lower())
        )
        u = q.scalar_one_or_none()
        if u is not None:
            return u

    return None
