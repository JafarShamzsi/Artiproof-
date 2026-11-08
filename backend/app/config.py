from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Environment: "development" | "staging" | "production"
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://artiproof:artiproof@localhost:5432/artiproof"
    DATABASE_URL_SYNC: str = "postgresql://artiproof:artiproof@localhost:5432/artiproof"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    # Optional explicit origin matcher; empty by default for local review.
    CORS_ORIGIN_REGEX: str = ""

    # AI
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # Google Fact Check
    GOOGLE_FACTCHECK_API_KEY: str = ""
    GOOGLE_CLIENT_ID: str = ""  # Required for Google sign-in: set via GOOGLE_CLIENT_ID env var

    # Academic data APIs (optional)
    SEMANTIC_SCHOLAR_API_KEY: str = ""
    SCOPUS_API_KEY: str = ""

    # Auth
    JWT_SECRET: str = ""  # Required: set via JWT_SECRET env var (must be a strong random value)
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 1440

    # App
    APP_URL: str = "http://localhost:3000"
    API_URL: str = "http://localhost:8000"

    # Outbound HTTP identity (used by CrossRef and other politeness-required APIs)
    CONTACT_EMAIL: str = "info@example.invalid"

    # Email delivery (Resend). Empty key → logs-only stub for dev.
    # Production startup warns when this is unset. EMAIL_FROM must be a
    # verified sender in the Resend dashboard.
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "ArtiProof <noreply@example.invalid>"

    # Observability (Sentry). Empty DSN → no error tracking. The traces
    # sample rate defaults low because every Celery pipeline run would
    # otherwise pull a trace and inflate the bill; bump SENTRY_TRACES_SAMPLE
    # to 0.5+ when actively debugging perf.
    SENTRY_DSN: str = ""
    SENTRY_ENVIRONMENT: str = ""  # falls back to ENVIRONMENT when empty
    SENTRY_TRACES_SAMPLE_RATE: float = 0.05

    # Billing webhook signing — per-processor HMAC secret. Empty string
    # means the webhook endpoint refuses every callback (production-safe
    # default; nothing is wired). The processor name in the URL must
    # match a key in BILLING_WEBHOOK_SECRETS for the request to be
    # accepted. JSON object via env: BILLING_WEBHOOK_SECRETS='{"stub":"abc","X":"def"}'.
    BILLING_WEBHOOK_SECRETS: dict[str, str] = {}

    # Demo seeding (used by /api/seed/demo). Two layers of gating:
    #   - ENABLE_SEED_ROUTES must be true (default false). The previous
    #     `ENVIRONMENT != "production"` check accidentally enabled the
    #     route on staging / preview environments, where attackers can
    #     enumerate and trample real test data. Operators must opt in
    #     explicitly per environment.
    #   - ENVIRONMENT cannot be "production" (belt-and-braces — even if
    #     the flag is set in prod by mistake, the prod check still wins).
    ENABLE_SEED_ROUTES: bool = False
    DEMO_EMAIL: str = "demo@example.invalid"
    DEMO_PASSWORD: str = "demo1234"

    model_config = {"env_file": None, "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
