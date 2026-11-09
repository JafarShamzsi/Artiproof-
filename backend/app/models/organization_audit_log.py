"""Org-management audit trail.

Every mutation to org membership / settings / seat limit goes through
``app.services.org_audit.record_org_action`` which writes one row here
and emits a parallel structured log line. The ``/team`` Audit tab pages
through this table newest-first.

Action vocabulary (free text but stay in this set):

- ``invite_sent`` — admin invited a new email. Payload: {email, role}.
- ``invite_revoked`` — admin revoked a pending invite. Payload: {email}.
- ``invite_resent`` — admin re-mailed an existing pending invite.
- ``member_added`` — existing user attached to the org (either accepted
  an invite or admin attached them directly). Payload: {email, role}.
- ``member_removed`` — admin removed a member. Payload: {email}.
- ``role_changed`` — admin changed a member's role. Payload:
  {from_role, to_role}.
- ``seat_limit_changed`` — admin (or backend) changed the cap. Payload:
  {from, to}.
- ``org_settings_changed`` — admin edited name / contact_email.
  Payload: {fields: ["name", ...]}.
- ``org_created`` — self-serve "Start a team" trial creation. Payload:
  {is_trial, trial_ends_at}.

Rows are never deleted on routine usage. ``ON DELETE CASCADE`` from
``organization_id`` does the cleanup when an org is hard-deleted (which
is itself rare and only happens via direct DB intervention).
"""

import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import Base


class OrganizationAuditLog(Base):
    __tablename__ = "organization_audit_logs"

    id = sa.Column(sa.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = sa.Column(
        sa.String,
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_user_id = sa.Column(
        sa.String,
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    action = sa.Column(sa.String, nullable=False)
    target_user_id = sa.Column(
        sa.String,
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    payload = sa.Column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    created_at = sa.Column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
    )
