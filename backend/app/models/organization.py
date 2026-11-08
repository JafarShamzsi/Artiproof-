"""Organization — the unit of "team" identity.

Existence is required for tier='team' users to use team activity features.
For now organizations are seeded out-of-band (admin script / DB seed); a
user-facing invite + admin UI for membership is a separate phase.
"""

import uuid

import sqlalchemy as sa

from app.models.base import Base
from app.models.mixins import TimestampMixin


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id = sa.Column(sa.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = sa.Column(sa.String, nullable=False)
    # Optional human-readable slug for URL generation later. Unique when set.
    slug = sa.Column(sa.String, nullable=True, unique=True)
    # White-label branding for generated reports. URL-based for now — file
    # upload is a future phase. Renderer falls back to ArtiProof's brand
    # when logo_url is null.
    logo_url = sa.Column(sa.String, nullable=True)
    # CSS color (e.g. "#7C2828") substituted into the report header rule.
    primary_color = sa.Column(sa.String(16), nullable=True)
    secondary_color = sa.Column(sa.String(16), nullable=True)
    # Team-plan v1 additions:
    #   seat_limit — max members for the org. Enforced on invite/attach.
    #     Default 10 matches the Team Starter bracket. Increases require
    #     a plan upgrade (today: contact-sales; future: Stripe).
    #   is_trial / trial_ends_at — set when an org is created via the
    #     self-serve "Start a team" flow. After expiry, the route layer
    #     freezes writes until a sales contact converts the trial.
    #   contact_email — the billing / admin contact for the org. Distinct
    #     from individual member emails; used for renewal reminders.
    seat_limit = sa.Column(sa.Integer, nullable=False, server_default="10")
    is_trial = sa.Column(
        sa.Boolean, nullable=False, server_default=sa.text("false")
    )
    trial_ends_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    contact_email = sa.Column(sa.String, nullable=True)
