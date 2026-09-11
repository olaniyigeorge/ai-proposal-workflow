import enum
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class SalespersonAccountStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class SalespersonAccount(Base, TimestampMixin):
    """Gates real (Supabase Auth) sign-ins behind approval — a self-serve
    signUp() creates a real, working Supabase Auth account instantly, but
    that alone must not be enough to use this app: this table is the
    backend's own record of whether that account is actually allowed to act
    as a salesperson yet.

    Row lifecycle: `get_current_salesperson` (app/core/security.py) creates
    one as PENDING the first time a given Supabase user makes an
    authenticated request, if none exists yet — self-registering, not a
    separate signup-confirmation endpoint the frontend has to remember to
    call. Every request from a PENDING or REJECTED account is rejected with
    403 until an already-APPROVED salesperson approves them (see
    services/salesperson_account_service.py) — consistent with this
    project's "no separate approver role, any salesperson may act" model
    (decisions #21): approving a new colleague's account requires no more
    privilege than approving a proposal does.

    Bootstrap problem: nobody can be approved until at least one approved
    account exists. `scripts/approve_salesperson.py` exists specifically to
    manually approve the first account(s) directly against the DB — not
    exposed via the API, since exposing "approve the first account" as an
    endpoint would just move the same bootstrap problem one level down.
    The dev token (`dev-salesperson-token`) bypasses this table entirely
    (see security.py) — it never had a real Supabase user_id to gate on.
    """

    __tablename__ = "salesperson_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, nullable=False
    )
    supabase_user_id: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[SalespersonAccountStatus] = mapped_column(
        Enum(SalespersonAccountStatus, native_enum=False),
        default=SalespersonAccountStatus.PENDING,
        nullable=False,
    )
    approved_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # The name a salesperson sets for themselves (self-service, see
    # PATCH /auth/me) — this is what gets written into a proposal's free-text
    # `salesperson_name` column when they self-claim an unassigned proposal
    # (services/proposal_service.py::claim_proposal). Unique so two accounts
    # can't claim proposals under an indistinguishable name; nullable because
    # a freshly-approved account may not have set one yet (they can't claim
    # anything until they do — see the claim endpoint's own guard).
    display_name: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, nullable=True
    )
