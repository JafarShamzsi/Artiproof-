"""Persistent invite records for the org membership flow.

The invite *email* itself carries a signed JWT (see
``app.utils.auth.create_invite_token``) which is the stateless half of
the equation — the new user clicks the link, the signup flow validates
the token, and they're attached as a member. That alone is enough to
make signup work.

This table is the **stateful** half. The ``/team`` workspace needs:

- a list of pending invites to render in the Invites tab,
- a way for an admin to *resend* an invite without re-issuing the token
  (so the URL the invitee already has in their inbox keeps working),
- a way to *revoke* an invite so a stolen token can't be used.

So we store the token alongside ``status ∈ {pending, accepted,
revoked, expired}``. Signup checks the row: an accepted/revoked/expired
row is rejected regardless of whether the JWT is otherwise valid.

One *active* invite per (org, lower(email)) — multiple sends for the
same address bump the existing row instead of creating duplicates.
"""

import uuid

import sqlalchemy as sa

from app.models.base import Base


class OrganizationInvite(Base):
    __tablename__ = "organization_invites"

    id = sa.Column(sa.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = sa.Column(
        sa.String,
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    email = sa.Column(sa.String, nullable=False)
    role = sa.Column(sa.String, nullable=False, server_default="member")
    token = sa.Column(sa.Text, nullable=False)
    # "pending" -> "accepted" / "revoked" / "expired". Set by route layer.
    status = sa.Column(
        sa.String, nullable=False, server_default="pending"
    )
    invited_by = sa.Column(
        sa.String,
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = sa.Column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
    )
    expires_at = sa.Column(sa.DateTime(timezone=True), nullable=False)
    accepted_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    revoked_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
