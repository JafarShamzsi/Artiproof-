"""Active session tracking — populated on login, consumed by get_current_user.

Each issued JWT carries a `jti` claim that matches `Session.id`. The auth
dep looks the row up on every request to (a) reject revoked sessions and
(b) update last_used_at. Tokens issued before this table existed have no
`jti` and skip the lookup entirely (legacy compatibility).
"""

import uuid

import sqlalchemy as sa

from app.models.base import Base
from app.models.mixins import TimestampMixin


class Session(Base, TimestampMixin):
    __tablename__ = "sessions"

    id = sa.Column(sa.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = sa.Column(
        sa.String,
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_agent = sa.Column(sa.String, nullable=True)
    ip_address = sa.Column(sa.String, nullable=True)
    last_used_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    revoked_at = sa.Column(sa.DateTime(timezone=True), nullable=True, index=True)
    # Best-effort label so the user can recognize "this is my work laptop".
    # Frontend may display the user_agent verbatim if this is empty.
    label = sa.Column(sa.String, nullable=True)
