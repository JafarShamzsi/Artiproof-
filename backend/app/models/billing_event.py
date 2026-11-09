"""Webhook landing record.

Every callback from the payment processor lands as a row here BEFORE
any tier mutation. The ``(processor, processor_event_id)`` unique
index makes the insert idempotent — a redelivered webhook returns
without double-applying. ``apply_tier_change`` then dispatches off
``event_type`` to update the user's tier and writes a matching row
to ``tier_change_audits`` so the audit trail links back.

Why nullable user_id
--------------------
The processor's first webhook for a brand-new subscription can arrive
microseconds after the signup that created it; if the queue beats the
HTTP response we won't have matched the subscription_id to a user yet.
Rather than reject, we land the row and let a backfill sweep attach it.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import Base


class BillingEvent(Base):
    __tablename__ = "billing_events"

    id = sa.Column(sa.String, primary_key=True)
    user_id = sa.Column(
        sa.String,
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    processor = sa.Column(sa.String, nullable=False)
    processor_event_id = sa.Column(sa.String, nullable=False)
    event_type = sa.Column(sa.String, nullable=False)
    amount_cents = sa.Column(sa.Integer, nullable=True)
    currency = sa.Column(sa.String(3), nullable=True)
    raw_payload = sa.Column(JSONB, nullable=False)
    created_at = sa.Column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "processor",
            "processor_event_id",
            name="uq_billing_events_processor_event_id",
        ),
    )
