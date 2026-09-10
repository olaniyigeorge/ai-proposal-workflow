import enum
import uuid
from typing import Optional
from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class ClaudeCallType(str, enum.Enum):
    FULL_GENERATION = "full_generation"
    REGENERATION = "regeneration"


class ClaudeCallStatus(str, enum.Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ClaudeCallLog(Base, TimestampMixin):
    """One row per Claude API call — full-generation (one per generated
    section, since each section is its own call) or regeneration.
    Observability only: prompts/response/token usage/latency, so the team can
    see what's actually being sent and spent, not something any other part of
    the system reads back. See docs/decisions.md and CLAUDE.md's "Activity
    logging is required" — this is the AI-call-specific complement to the
    still-unbuilt general ActivityLogEntry trail (Phase 8), scoped to Claude
    calls only.
    """

    __tablename__ = "claude_call_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, nullable=False
    )
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("proposals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_key: Mapped[str] = mapped_column(String(64), nullable=False)
    call_type: Mapped[ClaudeCallType] = mapped_column(
        Enum(ClaudeCallType, native_enum=False), nullable=False
    )
    status: Mapped[ClaudeCallStatus] = mapped_column(
        Enum(ClaudeCallStatus, native_enum=False), nullable=False
    )
    instruction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    response_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    input_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    stop_reason: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    proposal = relationship("Proposal")
