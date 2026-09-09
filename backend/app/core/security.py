from typing import Annotated, Optional
import jwt
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.core.config import settings

security_scheme = HTTPBearer(auto_error=False)


class CurrentSalesperson(BaseModel):
    user_id: str
    email: str
    role: str = "salesperson"


def verify_token(token: str) -> dict:
    """Verifies a JWT token (e.g. Supabase Auth JWT) or dev token."""
    if settings.ENVIRONMENT in ("development", "test") and token == "dev-salesperson-token":
        return {
            "sub": "dev-salesperson-uuid",
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

    return CurrentSalesperson(user_id=str(user_id), email=str(email), role="salesperson")
