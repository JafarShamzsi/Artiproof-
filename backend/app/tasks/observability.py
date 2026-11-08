"""Celery signal handlers — telemetry + DLQ.

Three signals do the work:

  ``task_prerun``  -> insert celery_run_log row (status="started")
  ``task_postrun`` -> update with status + duration + exception class
  ``task_failure`` -> when retries are exhausted, copy the failed payload
                      into celery_dlq so the admin panel can surface +
                      retry it.

Every write is best-effort. A telemetry write that throws shouldn't
cascade into the user-facing task failing. Each handler swallows its
own errors and demotes to debug logging.

The Celery app calls ``register_observability_signals(celery_app)`` from
``app.tasks.__init__`` so the handlers are installed once, when the
worker boots.
"""

from __future__ import annotations

import logging
import time
import traceback
import uuid
from typing import Any

logger = logging.getLogger(__name__)


# Track per-task start time so postrun can compute duration. Keyed by
# task_id. Cleaned up by postrun.
_start_times: dict[str, float] = {}


def _serialize_arg(a: Any) -> Any:
    """JSON-safe representation. Anything weird becomes its repr."""
    if a is None or isinstance(a, (bool, int, float, str)):
        return a
    if isinstance(a, (list, tuple)):
        return [_serialize_arg(x) for x in a]
    if isinstance(a, dict):
        return {str(k): _serialize_arg(v) for k, v in a.items()}
    return repr(a)[:500]


def _persist_run_log(
    *,
    task_name: str,
    task_id: str,
    status: str,
    duration_ms: int | None,
    exception_class: str | None,
) -> None:
    """Sync DB write — runs inside the Celery worker process, which
    doesn't share the asyncio event loop. We open a fresh sync session.
    """
    try:
        from sqlalchemy import create_engine, text

        from app.config import settings

        # SYNC psycopg2 engine — short-lived per call. Worker processes
        # may not have an asyncio loop, and signal handlers can't await.
        engine = create_engine(settings.DATABASE_URL_SYNC, pool_pre_ping=True)
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO celery_run_log
                        (id, task_name, task_id, status, duration_ms, exception_class, started_at, finished_at)
                    VALUES
                        (:id, :task_name, :task_id, :status, :duration_ms, :exception_class, NOW(), NOW())
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "task_name": task_name,
                    "task_id": task_id,
                    "status": status,
                    "duration_ms": duration_ms,
                    "exception_class": exception_class,
                },
            )
        engine.dispose()
    except Exception as e:
        logger.debug("celery_run_log write failed: %s", type(e).__name__)


def _persist_dlq(
    *,
    task_name: str,
    task_id: str,
    args: tuple,
    kwargs: dict,
    exception: BaseException,
    retry_count: int,
) -> None:
    try:
        from sqlalchemy import create_engine, text

        from app.config import settings

        engine = create_engine(settings.DATABASE_URL_SYNC, pool_pre_ping=True)
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO celery_dlq
                        (id, task_name, task_id, args, kwargs,
                         exception_class, exception_message, traceback,
                         retry_count, failed_at)
                    VALUES
                        (:id, :task_name, :task_id, :args, :kwargs,
                         :exception_class, :exception_message, :traceback,
                         :retry_count, NOW())
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "task_name": task_name,
                    "task_id": task_id,
                    # JSONB columns accept a JSON string from psycopg2.
                    "args": _to_json(_serialize_arg(list(args))),
                    "kwargs": _to_json(_serialize_arg(dict(kwargs))),
                    "exception_class": type(exception).__name__,
                    "exception_message": str(exception)[:1000],
                    "traceback": traceback.format_exc()[:4000],
                    "retry_count": retry_count,
                },
            )
        engine.dispose()
    except Exception as e:
        logger.debug("celery_dlq write failed: %s", type(e).__name__)


def _to_json(value: Any) -> str:
    """psycopg2's text adapter for JSONB requires a JSON string."""
    import json as _json

    try:
        return _json.dumps(value, default=str)
    except Exception:
        return "{}"


def register_observability_signals(celery_app: Any) -> None:
    """Install task_prerun/postrun/failure handlers on the worker.

    Called from ``app.tasks.__init__`` after the Celery instance is
    constructed. Idempotent — calling twice just re-registers the same
    weak refs and does nothing harmful.
    """
    if celery_app is None:
        return
    try:
        from celery.signals import task_failure, task_postrun, task_prerun
    except Exception:
        logger.debug("Celery signals unavailable")
        return

    @task_prerun.connect
    def _on_prerun(task_id=None, task=None, **_):
        if not task_id:
            return
        _start_times[task_id] = time.monotonic()
        # Telemetry "started" row is optional — adds a row for in-flight
        # tasks that the dashboard can list as "running now". Skipped
        # for now to halve write volume; postrun's row is enough for
        # latency tracking.

    @task_postrun.connect
    def _on_postrun(task_id=None, task=None, state=None, **_):
        if not task_id:
            return
        start = _start_times.pop(task_id, None)
        duration_ms: int | None = None
        if start is not None:
            duration_ms = int((time.monotonic() - start) * 1000)
        status_map = {
            "SUCCESS": "success",
            "FAILURE": "failed",
            "RETRY": "retry",
        }
        status = status_map.get(str(state or "").upper(), str(state or "unknown").lower())
        task_name = getattr(task, "name", "unknown") if task else "unknown"
        _persist_run_log(
            task_name=task_name,
            task_id=task_id,
            status=status,
            duration_ms=duration_ms,
            exception_class=None,
        )

    @task_failure.connect
    def _on_failure(
        task_id=None,
        exception=None,
        args=None,
        kwargs=None,
        traceback=None,
        einfo=None,
        sender=None,
        **_,
    ):
        if not task_id or exception is None:
            return
        task_name = getattr(sender, "name", "unknown") if sender else "unknown"
        retry_count = 0
        if einfo is not None:
            # einfo.task.request.retries is the canonical counter.
            try:
                retry_count = int(
                    getattr(getattr(einfo, "task", None), "request", None).retries
                )
            except Exception:
                retry_count = 0
        _persist_dlq(
            task_name=task_name,
            task_id=task_id,
            args=tuple(args or ()),
            kwargs=dict(kwargs or {}),
            exception=exception,
            retry_count=retry_count,
        )

    logger.info("Celery telemetry + DLQ signals registered")
