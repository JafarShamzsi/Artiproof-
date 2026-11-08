"""OpenTelemetry init/teardown.

All imports happen inside the init function so a deployment that omits
the OTel env var (the default) doesn't pay the import cost.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


_initialized = False
_provider: Any = None


def init_otel(app: Any | None = None) -> bool:
    """Initialize OpenTelemetry if OTEL_EXPORTER_OTLP_ENDPOINT is set.

    Args:
        app: optional FastAPI app to auto-instrument. The HTTP middleware
            wraps the app; passing it here installs the integration in one shot.

    Returns:
        True if initialization happened, False if OTel is disabled (the
        common case in dev / local runs).
    """
    global _initialized, _provider

    endpoint = getattr(settings, "OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if not endpoint:
        return False
    if _initialized:
        return True

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
    except Exception:
        logger.exception("OpenTelemetry libs unavailable — skipping init")
        return False

    resource = Resource.create(
        {
            SERVICE_NAME: "artiproof-api",
            SERVICE_VERSION: "1.0.0",
            "deployment.environment": settings.ENVIRONMENT,
        }
    )
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _provider = provider

    # FastAPI auto-instrumentation. Wraps every route in a server span.
    if app is not None:
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

            FastAPIInstrumentor.instrument_app(app)
        except Exception:
            logger.exception("FastAPI OTel instrumentation failed")

    # SQLAlchemy instrumentation. Each engine.execute becomes a span.
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from app.database import engine

        SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
    except Exception:
        logger.exception("SQLAlchemy OTel instrumentation failed")

    # Celery instrumentation. Each task becomes a consumer span.
    try:
        from opentelemetry.instrumentation.celery import CeleryInstrumentor

        CeleryInstrumentor().instrument()
    except Exception:
        # Celery may not be installed in lightweight test envs.
        logger.debug("Celery OTel instrumentation skipped")

    _initialized = True
    logger.info("OpenTelemetry initialized — endpoint=%s", endpoint)
    return True


def shutdown_otel() -> None:
    """Flush spans on graceful shutdown. Safe to call when uninitialized."""
    global _provider, _initialized
    if _provider is None:
        return
    try:
        _provider.shutdown()
    except Exception:
        logger.exception("OTel provider shutdown failed")
    _provider = None
    _initialized = False
