"""Single chokepoint for every mutation of ``user.tier``.

The whole point of having a chokepoint is that the audit trail can
never drift from reality. A tier change anywhere in the app that
skipped this helper would be invisible to finance reconciliation; the
contract is enforced socially (review + tests), not by the DB —
SQLAlchemy doesn't have row-level triggers we'd want to depend on.

Inputs
------

- ``db`` — the active session. Caller is responsible for committing.
  This helper deliberately does NOT commit because some callers (e.g.
  the webhook) want to insert other rows in the same transaction.
- ``user`` — the User row to mutate. Must already be loaded into the
  session. The helper mutates ``user.tier`` in place.
- ``new_tier`` — target tier. Validated against ``TIER_LIMITS`` so a
  caller can't install an unknown tier string.
- ``reason`` — free-text reason code. See ``TierChangeAudit`` for the
  encouraged values. Stored as-is.
- ``actor`` — the User who triggered the change (admin panel) or
  None (system-initiated: webhook, signup intent).
- ``billing_event`` — optional ``BillingEvent`` row. If provided, the
  audit row links to it via ``billing_event_id`` so finance can
  trace which webhook caused which tier shift.

Returns
-------

The ``TierChangeAudit`` row (already added to the session, not yet
committed). Caller can stash the id, inspect ``from_tier``, etc.

No-op handling
--------------

If ``user.tier == new_tier`` the helper still writes an audit row
(``from_tier == to_tier``) so we have a record of the no-op. That's
useful for reconciliation: a re-fired webhook event hitting the
no-op path proves the system correctly absorbed the duplicate
instead of silently dropping it.
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import TIER_LIMITS
from app.models.billing_event import BillingEvent
from app.models.tier_change_audit import TierChangeAudit
from app.models.user import User


class UnknownTierError(ValueError):
    """Raised when a caller passes a tier string that isn't in
    ``TIER_LIMITS``. Bubbles up as a 400/422 at the route layer."""


async def apply_tier_change(
    db: AsyncSession,
    user: User,
    new_tier: str,
    *,
    reason: str,
    actor: Optional[User] = None,
    billing_event: Optional[BillingEvent] = None,
) -> TierChangeAudit:
    """Mutate ``user.tier`` and write a matching audit row.

    Caller must commit the session — this helper does not, so that the
    webhook can insert ``billing_events`` and ``tier_change_audits`` in
    one atomic transaction.
    """
    if new_tier not in TIER_LIMITS:
        raise UnknownTierError(
            f"Unknown tier '{new_tier}'. Known: {sorted(TIER_LIMITS)}"
        )
    if not reason:
        raise ValueError("reason is required for every tier change")

    previous = user.tier
    user.tier = new_tier

    audit = TierChangeAudit(
        id=str(uuid.uuid4()),
        user_id=user.id,
        from_tier=previous,
        to_tier=new_tier,
        changed_by_user_id=actor.id if actor is not None else None,
        reason=reason,
        billing_event_id=billing_event.id if billing_event is not None else None,
    )
    db.add(audit)
    return audit
