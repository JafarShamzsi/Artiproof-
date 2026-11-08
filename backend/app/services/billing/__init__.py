"""Billing service surface.

Single export today: ``apply_tier_change`` — the chokepoint every
caller MUST go through to mutate ``user.tier``. The contract:

- Writes ``user.tier`` and a matching ``tier_change_audits`` row in
  the same transaction. If either fails, both roll back.
- Accepts an optional ``billing_event`` so the audit row links to the
  webhook callback that drove the change.
- Validates the new tier against ``TIER_LIMITS`` so a typo can't
  install ``"enterpise"`` on a user.

Routers should never touch ``user.tier`` directly. The admin router
goes through this (Phase D moves it off the inline mutation it had
in Phase B); the future webhook goes through this; the future
self-serve cancel will go through this.
"""

from app.services.billing.tier_change import apply_tier_change

__all__ = ["apply_tier_change"]
