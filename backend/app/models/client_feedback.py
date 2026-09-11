import enum
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class ClientResponseType(str, enum.Enum):
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    NO_RESPONSE = "NO_RESPONSE"


class ClientResponseRecord(Base, TimestampMixin):
    """Unauthenticated client response to a delivered proposal.

    The client-facing page (no auth) records ACCEPTED / DECLINED / NO_RESPONSE
    plus optional free-text feedback. One row per proposal (we dedupe on the
    client's first meaningful response — ACCEPTED/DECLINED — and treat a
    second click as a no-op). The link in the delivery email points at the
    public client page; the POST that records the response is also public
    (no JWT) — identity is the proposal_id in the URL + a lightweight
    per-proposal idempotency key generated server-side and embedded in the
    form/link to prevent replay.

    Where 'accepted' should move the proposal to a warmer state for the
    salesperson (e.g. so won-rate KPIs and follow-up workflows fire), the
    transition is handled explicitly in the service layer, not silently here.
    """

    __tablename__ = "client_response_records"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, nullable=False
    )
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("proposals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    response_type: Mapped[ClientResponseType] = mapped_column(
        Enum(ClientResponseType, native_enum=False), nullable=False
    )
    feedback_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Light abuse signal only — not used as identity; truncated/cleared at
    # the boundary. Stored as a string, never interpreted as anything richer.
    client_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    proposal = relationship("Proposal")


class FeedbackCategory(str, enum.Enum):
    BUG = "BUG"
    FEATURE_REQUEST = "FEATURE_REQUEST"
    GENERAL = "GENERAL"


class FeedbackEntry(Base, TimestampMixin):
    """Salesperson feedback about the system — auth required to POST.

    Lightweight: category + free text + the actor's email (from the JWT, not
    a FK to keep it simple). Read-backed by the team so patterns can be
    spotted; no in-app 'mark as addressed' state in this phase — that is a
    follow-up, not part of the minimal feedback collection surface.
    """

    __tablename__ = "feedback_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, nullable=False
    )
    category: Mapped[FeedbackCategory] = mapped_column(
        Enum(FeedbackCategory, native_enum=False), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    actor_email: Mapped[str] = mapped_column(String(255), nullable=False)
