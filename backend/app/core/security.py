from typing import Annotated, Optional
import jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.salesperson_account import SalespersonAccountStatus
from app.services.salesperson_account_service import get_or_create_pending

security_scheme = HTTPBearer(auto_error=False)

DEV_TOKEN = "dev-salesperson-token"
DEV_USER_ID = "dev-salesperson-uuid"


class CurrentSalesperson(BaseModel):
    user_id: str
    email: str
    role: str = "salesperson"


def verify_token(token: str) -> dict:
    """Verifies a JWT token (e.g. Supabase Auth JWT) or dev token."""
    if settings.ENVIRONMENT in ("development", "test") and token == DEV_TOKEN:
        return {
            "sub": DEV_USER_ID,
            "email": "salesperson@example.com",
            "role": "salesperson",
        }

    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=[settings.ALGORITHM],
            options={"verify_aud": False},
        )
        return payload
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {str(exc)}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_current_salesperson(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Security(security_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CurrentSalesperson:
    """Dependency that enforces single-role (salesperson) authentication.

    Per Decision #21: There is only one role: 'salesperson'. All authenticated users
    operate under this role.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_token(credentials.credentials)
    user_id = payload.get("sub") or payload.get("id")
    email = payload.get("email", "")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload: missing user identifier",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # RLS defense-in-depth (migrations/versions/c7d8e9f0a1b2_*.py, docs/
    # reference/data-retention-policy.md): flags this transaction as *having
    # a validly-signed JWT* so DB-level policies allow access — deliberately
    # set before the approval-gate check below, not after, since that check
    # itself needs to read/write `salesperson_accounts` for a brand-new
    # (not-yet-approved) user. RLS's job is "is this a real authenticated
    # request at all," not "is this user approved" — that distinction is
    # enforced at the app layer via the 403 below, same as everywhere else in
    # this codebase. `db` here is the SAME session instance the route
    # handler receives (FastAPI caches Depends(get_db) per request), so this
    # takes effect before any query the route makes. A no-op until
    # DATABASE_URL is cut over to the app_runtime role — the current
    # (table-owning) role bypasses RLS regardless. `SET LOCAL` is
    # Postgres-specific (the sqlite dev/test DB doesn't understand it), so
    # this is skipped entirely off Postgres.
    bind = db.get_bind()
    if bind.dialect.name == "postgresql":
        await db.execute(text("SET LOCAL app.authenticated = 'true'"))

    # Approval gate (docs/edge-cases.md, 2026-09-11): a real self-serve
    # Supabase signUp() creates a working, JWT-issuing account instantly —
    # this is what stops that alone from being enough to use the app. The
    # dev token has no real Supabase user behind it, so it bypasses this
    # table entirely rather than getting a phantom pending row.
    if user_id != DEV_USER_ID:
        account = await get_or_create_pending(db, str(user_id), str(email))
        if account.status != SalespersonAccountStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Your account is pending approval from an existing salesperson."
                    if account.status == SalespersonAccountStatus.PENDING
                    else "Your account request was not approved."
                ),
            )

    return CurrentSalesperson(user_id=str(user_id), email=str(email), role="salesperson")
