import logging
import sys
import time
import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session, get_db
from app.routers import (
    admin_router,
    analytics_router,
    auth_router,
    billing_webhook_router,
    dashboard_router,
    health_router,
    organizations_router,
    report_schedules_router,
    reports_router,
    researcher_router,
    sales_router,
    security_router,
    source_check_router,
    watchlist_router,
)
from app.routers.seed import router as seed_router
from app.utils.rate_limit import limiter

# ─── Request-ID propagation ───────────────────────────────────────────────
# The middleware below sets this contextvar at the start of every request;
# the log formatter and the `with_request_id()` helper read it back. Async
# tasks spawned during the request inherit the var, so Celery handlers /
# background work scoped to a request can include the same id in logs.
_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


def current_request_id() -> str:
    return _request_id_ctx.get()


class _RequestIdFilter(logging.Filter):
    """Stamps every log record with the current request id (or '-' outside
    a request). Used by the formatter to render ``request_id=<uuid>``."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id_ctx.get()
        return True


# ─── Logging configuration ────────────────────────────────────────────────
# Configure once at import time so every logger inherits the format.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [req=%(request_id)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
# Inject request-id into every record. Filters on a Logger only run on
# records ORIGINATING from that logger — records propagated from a child
# logger skip the parent's filters and go straight to the parent's
# handlers. So attach the filter to every root handler instead, which
# guarantees it runs on every record that reaches stdout.
for _h in logging.getLogger().handlers:
    _h.addFilter(_RequestIdFilter())
# Quiet down noisy third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

logger = logging.getLogger("artiproof")


def _init_sentry() -> bool:
    """Initialize Sentry when SENTRY_DSN is set; no-op otherwise. Imported
    lazily so the SDK isn't loaded into memory for dev runs that don't
    care about error tracking."""
    if not settings.SENTRY_DSN:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.SENTRY_ENVIRONMENT or settings.ENVIRONMENT,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
            ],
            # Attach the request id so an event in Sentry links back to the
            # log line. The middleware sets the tag per-request below.
            send_default_pii=False,
        )
        return True
    except Exception:
        logger.exception("Sentry init failed — continuing without it")
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ─── Startup validation ───────────────────────────────────────────────
    is_production = settings.ENVIRONMENT.lower() == "production"

    # Initialize Sentry first so any subsequent startup errors are captured.
    sentry_on = _init_sentry()
    if sentry_on:
        logger.info("Sentry initialized — env=%s", settings.SENTRY_ENVIRONMENT or settings.ENVIRONMENT)
    elif is_production:
        logger.warning("SENTRY_DSN is unset — production errors will not be tracked")

    # JWT_SECRET hardening — three failure classes, each gated on
    # `is_production` because dev environments need to be permissive:
    #   1. Empty / placeholder value — refuses to start in prod, warns in dev.
    #   2. Too-short secret — anything under 32 chars is brute-forceable
    #      against HS256; refuse in prod, warn in dev.
    #   3. Anything else — fine.
    _PLACEHOLDER_SECRETS = {
        "",
        "change-me-in-production",
        "replace-with-strong-random-value",
        "ci-test-secret-not-for-production",
    }
    is_placeholder = settings.JWT_SECRET in _PLACEHOLDER_SECRETS
    is_too_short = len(settings.JWT_SECRET) < 32
    if is_placeholder or is_too_short:
        if is_production:
            raise RuntimeError(
                "JWT_SECRET must be a strong random value (>= 32 chars) in "
                "production. Generate one with `openssl rand -hex 32` and set "
                "the JWT_SECRET environment variable."
            )
        if is_placeholder:
            logger.warning(
                "Using placeholder JWT_SECRET — set a real value before deploying."
            )
        elif is_too_short:
            logger.warning(
                "JWT_SECRET is shorter than 32 characters — generate a longer "
                "value before deploying."
            )

    if is_production and not settings.GOOGLE_CLIENT_ID:
        logger.warning("GOOGLE_CLIENT_ID is empty — Google sign-in will be disabled.")

    missing = []
    if not settings.GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY — AI claim/citation/content analysis disabled")
    if not settings.GOOGLE_FACTCHECK_API_KEY:
        missing.append("GOOGLE_FACTCHECK_API_KEY — fact-check database lookup disabled")
    if not settings.RESEND_API_KEY:
        # Loud in prod because no email = password reset + verification +
        # scheduled report digests silently disabled.
        msg = (
            "RESEND_API_KEY — emails (password reset / verify / scheduled "
            "reports) will be logged, not delivered"
        )
        if is_production:
            logger.critical(msg)
        else:
            missing.append(msg)
    for w in missing:
        logger.warning(w)
    if missing:
        logger.warning("Configure missing values in .env for full functionality.")

    # Verify DB connectivity. In production this is fatal — better to fail
    # the deploy than to start a broken pod and serve 500s. Use the session
    # factory directly so the context manager properly returns the connection
    # to the pool (breaking out of `get_db()`'s async generator would leak it).
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        logger.info("Database connectivity verified.")
    except Exception as e:
        msg = f"Database connection failed during startup: {type(e).__name__}: {e}"
        if is_production:
            logger.critical(msg)
            raise RuntimeError(msg) from e
        logger.warning(msg)

    # OpenTelemetry init — opt-in via OTEL_EXPORTER_OTLP_ENDPOINT. No-op
    # when the env var is empty, which is the default. Wraps the FastAPI
    # app + SQLAlchemy engine + Celery for distributed tracing.
    try:
        from app.observability import init_otel

        if init_otel(app):
            logger.info(
                "OpenTelemetry instrumentation active — endpoint=%s",
                settings.OTEL_EXPORTER_OTLP_ENDPOINT,
            )
    except Exception:
        logger.exception("OTel init failed — continuing without it")

    logger.info("ArtiProof backend ready — env=%s", settings.ENVIRONMENT)

    yield

    # ─── Graceful shutdown ────────────────────────────────────────────────
    # Dispose of the async engine so pooled connections are returned cleanly.
    logger.info("Shutting down ArtiProof backend...")
    try:
        from app.observability import shutdown_otel

        shutdown_otel()
    except Exception:
        logger.exception("Error shutting down OpenTelemetry")
    try:
        from app.database import engine
        await engine.dispose()
    except Exception:
        logger.exception("Error closing database engine")


OPENAPI_TAGS = [
    {
        "name": "Authentication",
        "description": "Sign-up, sign-in (password / Google OAuth), token refresh, and the "
                       "`/me` profile endpoint.",
    },
    {
        "name": "Source Verification",
        "description": "Upload a URL or PDF and run the full pipeline — claim extraction, "
                       "fact-checking, AI-content detection, and citation analysis.",
    },
    {
        "name": "Researcher Integrity",
        "description": "Look up a researcher by ORCID/name, fetch their publications, and "
                       "compute self-citation rates, citation rings, and topic relevance.",
    },
    {
        "name": "Reports",
        "description": "Render and download HTML/PDF reports for completed analyses.",
    },
    {
        "name": "Dashboard",
        "description": "Aggregate stats, recent activity feed, and trend data for the "
                       "user's history.",
    },
    {
        "name": "Seed (dev only)",
        "description": "Test-data fixtures. **Disabled in production** by an environment "
                       "guard.",
    },
]


app = FastAPI(
    title="ArtiProof API",
    description=(
        "Research Integrity Platform — source verification, AI content detection, "
        "citation analysis, and researcher integrity scoring.\n\n"
        "All routes under `/api/*` require a bearer token from `/api/auth/login` "
        "unless explicitly marked otherwise."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=OPENAPI_TAGS,
    contact={"name": "ArtiProof", "url": "https://example.invalid"},
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

cors_origins = list(settings.CORS_ORIGINS)
if settings.APP_URL and settings.APP_URL not in cors_origins:
    cors_origins.append(settings.APP_URL)

# Default to None (no regex) so previews must be explicitly enabled. The previous
# Origin matching is explicit; the local showcase has no hosting bindings.
cors_regex = settings.CORS_ORIGIN_REGEX or None

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=cors_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)


# ─── Request logging middleware ───────────────────────────────────────────
HEALTH_PATHS = {"/health", "/api/health"}


@app.middleware("http")
async def request_id_and_logging(request: Request, call_next):
    """Stamp every request with a UUID, propagate it through logs + Sentry,
    and emit a one-line access log on completion.

    Accepts an inbound `X-Request-ID` header so a load balancer / client
    that already generated one (e.g. fly.io, Cloudflare) gets honored —
    otherwise a fresh UUIDv4 is minted. The id appears in:
      - every log line via the _RequestIdFilter
      - the response header so the client can quote it in a bug report
      - the Sentry scope so errors link back to the log line
    """
    incoming = request.headers.get("x-request-id")
    request_id = incoming if incoming and len(incoming) <= 64 else str(uuid.uuid4())
    token = _request_id_ctx.set(request_id)

    # Best-effort Sentry tag. The SDK is optional so wrap in try/except.
    try:
        import sentry_sdk

        scope = sentry_sdk.get_current_scope()
        scope.set_tag("request_id", request_id)
        scope.set_tag("path", request.url.path)
    except Exception:
        pass

    start = time.monotonic()
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        duration_ms = (time.monotonic() - start) * 1000
        if request.url.path not in HEALTH_PATHS:
            client = request.client.host if request.client else "-"
            logger.info(
                "%s %s status=%d duration=%.1fms ip=%s",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
                client,
            )
        return response
    finally:
        # Reset AFTER the access-log emit so the log line carries the
        # request id rather than the default sentinel. If call_next raises,
        # the reset still runs and the next request starts clean.
        _request_id_ctx.reset(token)


app.include_router(auth_router)
app.include_router(security_router)
app.include_router(source_check_router)
app.include_router(researcher_router)
app.include_router(reports_router)
app.include_router(report_schedules_router)
app.include_router(organizations_router)
app.include_router(dashboard_router)
app.include_router(analytics_router)
app.include_router(watchlist_router)
app.include_router(admin_router)
app.include_router(billing_webhook_router)
app.include_router(health_router)
app.include_router(sales_router)
app.include_router(seed_router)


@app.get("/health")
async def health_check():
    """Liveness probe — always 200 as long as the process is alive.

    Used by local liveness clients. Intentionally does not test DB or
    Redis: a degraded Redis shouldn't restart the API (that would only
    create a restart loop while the dependency is recovering). For
    *readiness* checks (DB+Redis up) use ``/api/health``.
    """
    return {"status": "healthy", "service": "artiproof-api", "version": "1.0.0"}


@app.get("/api/health")
async def detailed_health(response: Response, db: AsyncSession = Depends(get_db)):
    """Readiness probe — pings DB + Redis, returns 503 when either is down.

    Public endpoint, so the response is intentionally terse: only the
    hard dependencies (DB, Redis) appear. Per-integration configuration
    state used to be exposed here, but anonymous callers don't need to
    know which API keys are present — that's internal info.
    """
    services: dict[str, str] = {}
    overall = "ok"

    try:
        await db.execute(text("SELECT 1"))
        services["database"] = "ok"
    except Exception as e:
        services["database"] = f"error: {type(e).__name__}"
        overall = "degraded"

    try:
        from redis.asyncio import from_url  # type: ignore
        r = from_url(settings.REDIS_URL, socket_connect_timeout=2)
        try:
            await r.ping()
            services["redis"] = "ok"
        finally:
            await r.aclose()
    except Exception as e:
        services["redis"] = f"error: {type(e).__name__}"
        if overall == "ok":
            overall = "degraded"

    if overall != "ok":
        response.status_code = 503

    return {
        "status": overall,
        "service": "artiproof-api",
        "version": "1.0.0",
        "services": services,
    }
