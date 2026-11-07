from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://artiproof:artiproof@localhost:5432/artiproof"
    DATABASE_URL_SYNC: str = "postgresql://artiproof:artiproof@localhost:5432/artiproof"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # AI
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # Google Fact Check
    GOOGLE_FACTCHECK_API_KEY: str = ""
    GOOGLE_CLIENT_ID: str = "14207070717-grg8dt94ef75o3fkhcnntgmm3mun6i7g.apps.googleusercontent.com"

    # Academic data APIs (optional)
    SEMANTIC_SCHOLAR_API_KEY: str = ""
    SCOPUS_API_KEY: str = ""

    # Auth
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 1440

    # App
    APP_URL: str = "http://localhost:3000"
    API_URL: str = "http://localhost:8000"

    model_config = {"env_file": None, "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
