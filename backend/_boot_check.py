import sys, os
sys.path.insert(0, ".")
os.environ.setdefault("SUPABASE_URL", "https://placeholder.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "placeholder-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "dev-jwt-secret")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")  # aiosqlite: relative in-memory DB via three slashes
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("WEBHOOK_SECRET", "dev-webhook-secret")
os.environ.setdefault("RESEND_API_KEY", "re_placeholder")
os.environ.setdefault("EMAIL_FROM_ADDRESS", "noreply@example.com")
os.environ.setdefault("EMAIL_FROM_NAME", "Koya Talent")
os.environ.setdefault("CLAUDE_MODEL", "claude-sonnet-5")
os.environ.setdefault("CLAUDE_MAX_TOKENS", "500")
os.environ.setdefault("CLAUDE_API_KEY", "sk-placeholder")

from app.main import app
print(f"boot OK — app={app.title} routes={len(app.routes)}")
for r in app.routes:
    p = getattr(r, "path", "")
    if p.startswith("/api/v1/client") or p.startswith("/api/v1/salesperson") or p.startswith("/api/v1/proposals"):
        print(f"  {p} {list(getattr(r, 'methods', []))}")
