import enum
import uuid
from typing import Optional
from sqlalchemy import Enum, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class ActivityEventType(str, enum.Enum):
    CREATED = "created"
    GENERATED = "generated"
    GENERATION_FAILED = "generation_failed"
    SECTION_EDITED = "section_edited"
    SECTION_REGENERATED = "section_regenerated"
    REGENERATION_FAILED = "regeneration_failed"
    SECTION_APPROVED = "section_approved"
    SUBMITTED_FOR_APPROVAL = "submitted_for_approval"
    PROPOSAL_APPROVED = "proposal_approved"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"
    DOCUMENT_GENERATED = "document_generated"
    DOCUMENT_GENERATION_FAILED = "document_generation_failed"
    DELIVERED = "delivered"
    DELIVERY_FAILED = "delivery_failed"
    PROPOSAL_CLAIMED = "proposal_claimed"


class ActivityLogEntry(Base, TimestampMixin):
    """Phase 8: append-only audit trail of every state-relevant action across
    a proposal's lifecycle — CLAUDE.md: "required for every state-relevant
    action (created, edited, regenerated, section approved, proposal
    approved, rejected, document generated, delivered)... must be viewable in
    the dashboard and must be exportable for compliance." `*_FAILED` variants
    are included too, matching the rest of the system's "a *_FAILED substate
    for every async step" pattern (system-flow.md) and giving the audit trail
    the same failure visibility the state machine itself has.

    Deliberately references entities rather than embedding full content —
    architecture.md §1: "logs should generally reference entities and diffs,
    not always embed full content" is a compliance-liability concern, not
    just a style preference. `event_metadata` holds small structured fields
    (section_key, version, instruction, reason, error message) — callers
    must never put a section's full body text in here.

    Written by `record_activity()` (services/activity_log_service.py), which
    only calls `db.add()` and never commits on its own — the entry is always
    persisted in the SAME commit as the action it documents, so an audit row
    can never exist for an action that didn't commit, or vice versa. This is
    a deliberate departure from ClaudeCallLog, which commits independently as
    pure observability.

    Note (architecture.md §1, "Audit log integrity"): this is still just a
    normal table with normal CRUD permissions at the DB level — nothing here
    stops direct DB access from editing/deleting a row. The application layer
    exposes no update/delete path (only insert via record_activity and read
    via the list/export endpoints), which is as far as this phase goes;
    genuine tamper-resistance (DB-level permissions/triggers, a WORM store)
    is flagged as an open follow-up in docs/edge-cases.md, not solved here.
    """

    __tablename__ = "activity_log_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, nullable=False
    )
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("proposals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[ActivityEventType] = mapped_column(
        Enum(ActivityEventType, native_enum=False), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # Who did it — a salesperson's email from CurrentSalesperson, threaded
    # through from the request that triggered this event (including into the
    # background job for an async outcome). None for a system-originated
    # action with no request-context actor (n8n intake creating a Proposal).
    actor: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    event_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    proposal = relationship("Proposal")
