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

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
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
