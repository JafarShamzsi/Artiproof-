"""Celery task execution log.

One row per task run — both successful and failed. Failure → an
additional row lands in celery_dlq when retries run out.
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa

from app.models.base import Base


class CeleryRunLog(Base):
    __tablename__ = "celery_run_log"

    id = sa.Column(sa.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_name = sa.Column(sa.String, nullable=False, index=True)
    task_id = sa.Column(sa.String, nullable=False, index=True)
    # "started" | "success" | "failed" | "retry"
    status = sa.Column(sa.String, nullable=False)
    duration_ms = sa.Column(sa.Integer, nullable=True)
    started_at = sa.Column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
        index=True,
    )
    finished_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    exception_class = sa.Column(sa.String, nullable=True)
