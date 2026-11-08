"""OpenTelemetry initialization (opt-in).

OTel is gated on ``settings.OTEL_EXPORTER_OTLP_ENDPOINT``. When unset
(the default), ``init_otel`` is a no-op — none of the OTel packages
attempt to connect anywhere, and the per-call ``_tracer()`` helpers in
``app.services.gemini.client`` return None.

When set:
  - FastAPI auto-instrumentation captures every request as a span
  - SQLAlchemy auto-instrumentation captures every query
  - Celery auto-instrumentation captures every task
  - Manual spans (Gemini calls) attach to whichever trace is active

OTel is initialized once, in the FastAPI ``lifespan`` startup before
the API begins serving traffic.
"""

from app.observability.otel import init_otel, shutdown_otel


__all__ = ["init_otel", "shutdown_otel"]
