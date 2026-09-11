from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "AI Proposal Workflow"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # SQLAlchemy's `echo` used to be tied directly to DEBUG — that's why a
    # deploy with DEBUG=true (the .env.example default nobody remembered to
    # flip for prod) logs every single SQL statement, twice over (once via
    # SQLAlchemy's own "sqlalchemy.engine" logger, once again via root-logger
    # propagation into app/utils/logger.py's handler). Split into its own
    # flag, default off — DEBUG can stay on for other purposes without
    # flooding the logs with SQL.
    SQL_ECHO: bool = False

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./proposals_dev.db"

    # Supabase & Auth
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    SUPABASE_JWT_SECRET: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"

    # Supabase Storage (Phase 6: generated proposal PDFs)
    DOCUMENT_STORAGE_BUCKET: str = "proposal-documents"

    # Intake Webhook
    WEBHOOK_SECRET: str = "dev-webhook-secret"

    # Claude API (section generation/regeneration)
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-5"
    # ~200 word target sections need well under this; headroom for a
    # slightly-over-target response without truncating mid-sentence.
    CLAUDE_MAX_TOKENS: int = 500

    # Data retention (docs/reference/data-retention-policy.md) — enforced by
    # scripts/enforce_retention.py, not automatically on a timer inside the
    # API process itself (per CLAUDE.md: long-running/destructive work
    # doesn't belong inline in a request handler, and this isn't
    # request-triggered at all — it's a scheduled job).
    PROPOSAL_RETENTION_MONTHS: int = 24
    ACTIVITY_LOG_RETENTION_MONTHS: int = 12

    # CORS
    # Render's BACKEND_CORS_ORIGINS env var is authoritative in prod — this
    # default is only a local-dev fallback plus a safety net for prod if that
    # env var is ever unset. Must include the deployed frontend origin
    # (docs/submission/one-pager.md) or every cross-origin request from it
    # fails preflight with "Disallowed CORS origin" (400 on the OPTIONS call).
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://ai-proposal-workflow.vercel.app",
    ]

    # Client delivery (Phase 7) — Resend (https://resend.com), REST API.
    RESEND_API_KEY: str = ""
    EMAIL_FROM_ADDRESS: str = "proposals@koyatalent.com"
    EMAIL_FROM_NAME: str = "Koya Talent"
    # Absolute base URL this backend is reachable at — used to build the
    # client-facing document link embedded in the delivery email (an email
    # body needs an absolute URL; it can't use a relative path). Points at
    # the /public/... redirect endpoint, never at a raw signed Storage URL
    # directly, so the link never expires from the client's perspective
    # (see docs/edge-cases.md "Delivery links must not expire before a
    # client opens them").
    PUBLIC_BASE_URL: str = "http://localhost:8000"


settings = Settings()
