import enum
import uuid
from typing import List, Optional
from sqlalchemy import (
    Enum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class ProposalStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    GENERATING = "GENERATING"
    GENERATION_FAILED = "GENERATION_FAILED"
    IN_REVIEW = "IN_REVIEW"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    DOCUMENT_GENERATING = "DOCUMENT_GENERATING"
    DOCUMENT_GENERATION_FAILED = "DOCUMENT_GENERATION_FAILED"
    DOCUMENT_READY = "DOCUMENT_READY"
    DELIVERING = "DELIVERING"
    DELIVERY_FAILED = "DELIVERY_FAILED"
    DELIVERED = "DELIVERED"
    REJECTED = "REJECTED"
    CLOSED = "CLOSED"


class SectionKey(str, enum.Enum):
    INTRODUCTION = "introduction"
    PROPOSED_SOLUTION = "proposed_solution"
    DELIVERABLES = "deliverables"
    TIMELINE = "timeline"
    PRICING = "pricing"
    NEXT_STEPS = "next_steps"


class ContentOrigin(str, enum.Enum):
    TEMPLATE_DEFAULT = "template_default"
    AI_GENERATED = "ai_generated"
    HUMAN_EDITED = "human_edited"
    HUMAN_EDITED_AFTER_GENERATION = "human_edited_after_generation"


class SectionApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"


class Proposal(Base, TimestampMixin):
    __tablename__ = "proposals"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, nullable=False
    )
    status: Mapped[ProposalStatus] = mapped_column(
        Enum(ProposalStatus, native_enum=False),
        default=ProposalStatus.DRAFT,
        nullable=False,
    )
    client_name: Mapped[str] = mapped_column(String(255), nullable=False)
    client_email: Mapped[str] = mapped_column(String(255), nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    salesperson_name: Mapped[str] = mapped_column(String(255), nullable=False)
    date_of_call: Mapped[str] = mapped_column(String(100), nullable=False)
    client_needs_summary: Mapped[str] = mapped_column(Text, nullable=False)
    project_scope: Mapped[str] = mapped_column(Text, nullable=False)
    goals_and_objectives: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_services: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_timeline: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_pricing: Mapped[str] = mapped_column(String(255), nullable=False)

    sections: Mapped[List["ProposalSection"]] = relationship(
        "ProposalSection",
        back_populates="proposal",
        cascade="all, delete-orphan",
        order_by="ProposalSection.order_index",
        lazy="selectin",
    )
    intake_submission: Mapped[Optional["IntakeSubmission"]] = relationship(
        "IntakeSubmission",
        back_populates="proposal",
        uselist=False,
        lazy="selectin",
    )


class ProposalSection(Base, TimestampMixin):
    __tablename__ = "proposal_sections"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, nullable=False
    )
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("proposals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_key: Mapped[SectionKey] = mapped_column(
        Enum(SectionKey, native_enum=False), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_origin: Mapped[ContentOrigin] = mapped_column(
        Enum(ContentOrigin, native_enum=False),
        default=ContentOrigin.TEMPLATE_DEFAULT,
        nullable=False,
    )
    approval_status: Mapped[SectionApprovalStatus] = mapped_column(
        Enum(SectionApprovalStatus, native_enum=False),
        default=SectionApprovalStatus.PENDING,
        nullable=False,
    )
    regeneration_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    proposal: Mapped["Proposal"] = relationship("Proposal", back_populates="sections")


class IntakeSubmission(Base, TimestampMixin):
    __tablename__ = "intake_submissions"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, nullable=False
    )
    intake_key: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("proposals.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    proposal: Mapped["Proposal"] = relationship(
        "Proposal", back_populates="intake_submission"
    )
