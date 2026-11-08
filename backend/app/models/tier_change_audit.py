"""Audit log for every mutation of ``user.tier``.

The contract: NOTHING writes to ``user.tier`` without writing a
matching row here. The ``apply_tier_change`` service in
``app/services/billing/`` is the single chokepoint, so as long as
callers go through it, the audit is automatic.

Reason codes (free text, but use these to keep dashboards clean):

- ``admin_panel`` — admin user manually changed the tier via the
  admin router.
- ``billing_webhook`` — webhook callback drove the change. The
  ``billing_event_id`` column points at the originating event so
  finance can reconcile.
- ``signup_intent`` — captured on registration when the user arrived
  with a ``?plan=`` param. Records intent, NOT an actual upgrade
  (their tier stays the same until the processor confirms payment).
- ``support_override`` — manual support intervention from a script.
- ``self_serve_cancel`` — user cancelled their subscription via the
  Settings page (future Phase D+).
"""

import sqlalchemy as sa

from app.models.base import Base


class TierChangeAudit(Base):
    __tablename__ = "tier_change_audits"

    id = sa.Column(sa.String, primary_key=True)
    user_id = sa.Column(
        sa.String,
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_tier = sa.Column(sa.String, nullable=True)
    to_tier = sa.Column(sa.String, nullable=False)
    changed_by_user_id = sa.Column(
        sa.String,
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    changed_at = sa.Column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
        index=True,
    )
    reason = sa.Column(sa.String, nullable=False)
    billing_event_id = sa.Column(
        sa.String,
        sa.ForeignKey("billing_events.id", ondelete="SET NULL"),
        nullable=True,
    )
