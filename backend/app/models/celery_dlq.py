"""Dead-letter queue for Celery tasks that exhausted their retries.

Each row is one terminally-failed task. Admin panel reads from
``WHERE resolved_at IS NULL`` to surface the active backlog and offers
a per-row "retry" action that re-enqueues the same args/kwargs into the
original task name, then stamps ``resolved_at`` + ``resolved_by_user_id``.
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import Base


class CeleryDLQ(Base):
    __tablename__ = "celery_dlq"

    id = sa.Column(sa.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_name = sa.Column(sa.String, nullable=False, index=True)
    task_id = sa.Column(sa.String, nullable=False, index=True)
    args = sa.Column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    kwargs = sa.Column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    exception_class = sa.Column(sa.String, nullable=False)
    exception_message = sa.Column(sa.Text, nullable=True)
    traceback = sa.Column(sa.Text, nullable=True)
    retry_count = sa.Column(sa.Integer, nullable=False, server_default="0")
    failed_at = sa.Column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
        index=True,
    )
    resolved_at = sa.Column(
        sa.DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    resolved_by_user_id = sa.Column(sa.String, nullable=True)
