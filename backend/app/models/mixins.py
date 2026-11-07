"""Reusable column mixins.

Apply by inheriting alongside Base, e.g.:

    class SourceCheck(Base, TimestampMixin, SoftDeleteMixin):
        ...
"""

import sqlalchemy as sa


class TimestampMixin:
    created_at = sa.Column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
    updated_at = sa.Column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    deleted_at = sa.Column(sa.DateTime(timezone=True), nullable=True, index=True)
