import enum
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class DeliveryStatus(str, enum.Enum):
    SENT = "sent"
    FAILED = "failed"
    BOUNCED = "bounced"


class DeliveryRecord(Base, TimestampMixin):
    """One row per delivery attempt — CLAUDE.md: "delivery status
    (sent/bounced/failed) must be tracked... not just fired-and-forgotten."
    Not unique per proposal_id: unlike DocumentArtifact (generated exactly
    once), a delivery can fail and be retried (DELIVERY_FAILED ->
    DELIVERING is a legal transition), so each attempt gets its own row —
    the most recent one is the current delivery state.
    """

    __tablename__ = "delivery_records"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, nullable=False
    )
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("proposals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[DeliveryStatus] = mapped_column(
        Enum(DeliveryStatus, native_enum=False), nullable=False
    )
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    proposal = relationship("Proposal")
