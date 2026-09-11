import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.content_origin import content_origin_after_manual_edit
from app.domain.exceptions import (
    ProposalAlreadyAssignedError,
    SectionNotFoundError,
)
from app.domain.proposal_transitions import assert_section_editable, transition_proposal
from app.domain.regeneration import regeneration_invalidates_approval
from app.models.activity_log import ActivityEventType
from app.models.proposal import (
    Proposal,
    ProposalStatus,
    SectionApprovalStatus,
    SectionKey,
)
from app.services.activity_log_service import record_activity
from app.utils.logger import logger


async def list_proposals(
    db: AsyncSession, skip: int = 0, limit: int = 50
) -> List[Proposal]:
    stmt = (
        select(Proposal)
        .order_by(Proposal.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_proposal_by_id(
    db: AsyncSession, proposal_id: uuid.UUID
) -> Optional[Proposal]:
    stmt = (
        select(Proposal)
        .where(Proposal.id == proposal_id)
        .options(selectinload(Proposal.sections))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def update_section_content(
    db: AsyncSession,
    proposal: Proposal,
    section_key: SectionKey,
    content: str,
    actor: Optional[str] = None,
) -> Proposal:
    """Persist a salesperson's manual edit to a single section.

    Only touches the targeted section (CLAUDE.md: sibling content/version/origin
    must remain untouched). Marks the section `human_edited` or
    `human_edited_after_generation` (see domain/content_origin.py) and resets
    its approval status to `pending` — an edit is a content change, so a prior
    per-section approval no longer applies to what's on screen now. If the
    Proposal itself was PENDING_APPROVAL or APPROVED, that approval is likewise
    invalidated and the Proposal is forced back to IN_REVIEW (same rule as
    regeneration — docs/decisions.md #9).
    """
    section = next(
        (s for s in proposal.sections if s.section_key == section_key), None
    )
    if section is None:
        raise SectionNotFoundError(section_key)

    assert_section_editable(section_key, proposal.status)

    section.content = content
    section.content_origin = content_origin_after_manual_edit(section.content_origin)
    section.approval_status = SectionApprovalStatus.PENDING
    section.version += 1

    if regeneration_invalidates_approval(proposal.status):
        transition_proposal(proposal, ProposalStatus.IN_REVIEW)

    record_activity(
        db,
        proposal_id=proposal.id,
        event_type=ActivityEventType.SECTION_EDITED,
        description=f"Section '{section_key.value}' manually edited (version {section.version})",
        actor=actor,
        metadata={"section_key": section_key.value, "version": section.version},
    )
    await db.commit()
    await db.refresh(proposal)
    logger.info(
        "Section '%s' manually edited on proposal %s (version %s)",
        section_key.value,
        proposal.id,
        section.version,
    )
    return proposal


async def claim_proposal(
    db: AsyncSession, proposal: Proposal, display_name: str, actor: Optional[str] = None
) -> Proposal:
    """Manual self-claim of a genuinely unassigned proposal (decisions #20's
    review-queue claim step, resolved 2026-09-11) — never automatic, never a
    string-match against the free-text salesperson_name a client or another
    salesperson might have typed at intake (CLAUDE.md explicitly forbids
    that). Only applies while salesperson_name is NULL/blank; a proposal
    that already has an owner (however it got one) is not reassignable
    through this endpoint.
    """
    if proposal.salesperson_name and proposal.salesperson_name.strip():
        raise ProposalAlreadyAssignedError(proposal.id, proposal.salesperson_name)

    proposal.salesperson_name = display_name
    record_activity(
        db,
        proposal_id=proposal.id,
        event_type=ActivityEventType.PROPOSAL_CLAIMED,
        description=f"Proposal claimed by {display_name}",
        actor=actor,
        metadata={"salesperson_name": display_name},
    )
    await db.commit()
    await db.refresh(proposal)
    logger.info("Proposal %s claimed by %s", proposal.id, display_name)
    return proposal
