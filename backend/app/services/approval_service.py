"""Internal approval workflow (Phase 5): section-level approval, submitting a
proposal for approval, approving the whole proposal in one action, and the
two ways a proposal can land back in IN_REVIEW from PENDING_APPROVAL
(requesting changes vs. a formal reject) — see docs/system-flow.md §3.

Self-approval is the expected path (decisions #14) — any authenticated
salesperson may approve their own proposal. But once a proposal is claimed,
ownership enforcement (resolved 2026-09-11,
docs/design-system-redesign-and-ownership-concerns.md §1) means only the
claiming owner may act on it at all, approval included — every entry point
below calls assert_owns_proposal first. An unclaimed proposal has no owner
to enforce against and stays open to any salesperson (decisions #21).
"""

import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exceptions import InvalidTransitionError, SectionNotFoundError
from app.domain.ownership import assert_owns_proposal
from app.domain.proposal_transitions import assert_section_approvable, transition_proposal
from app.models.activity_log import ActivityEventType
from app.models.proposal import Proposal, ProposalStatus, SectionApprovalStatus, SectionKey
from app.services.activity_log_service import record_activity
from app.utils.logger import logger


async def approve_section(
    db: AsyncSession,
    proposal: Proposal,
    section_key: SectionKey,
    actor: Optional[str] = None,
    actor_account_id: Optional[uuid.UUID] = None,
) -> Proposal:
    """Approve a single section. Only valid during IN_REVIEW — per
    system-flow.md §3, individual approval isn't defined for any other
    status; once PENDING_APPROVAL, use approve_entire_proposal instead.
    """
    assert_owns_proposal(proposal, actor_account_id)

    section = next((s for s in proposal.sections if s.section_key == section_key), None)
    if section is None:
        raise SectionNotFoundError(section_key)

    assert_section_approvable(section_key, proposal.status)

    section.approval_status = SectionApprovalStatus.APPROVED
    record_activity(
        db,
        proposal_id=proposal.id,
        event_type=ActivityEventType.SECTION_APPROVED,
        description=f"Section '{section_key.value}' approved",
        actor=actor,
        metadata={"section_key": section_key.value},
    )
    await db.commit()
    await db.refresh(proposal)
    logger.info("Section '%s' approved on proposal %s", section_key.value, proposal.id)
    return proposal


async def submit_for_approval(
    db: AsyncSession,
    proposal: Proposal,
    actor: Optional[str] = None,
    actor_account_id: Optional[uuid.UUID] = None,
) -> Proposal:
    """IN_REVIEW -> PENDING_APPROVAL. Not gated on every section already
    being approved — PENDING_APPROVAL is a "final look" checkpoint, and the
    APPROVED transition itself is what enforces "no section left pending"
    (ApprovalGuardError).
    """
    assert_owns_proposal(proposal, actor_account_id)
    transition_proposal(proposal, ProposalStatus.PENDING_APPROVAL)
    record_activity(
        db,
        proposal_id=proposal.id,
        event_type=ActivityEventType.SUBMITTED_FOR_APPROVAL,
        description="Proposal submitted for approval",
        actor=actor,
    )
    await db.commit()
    await db.refresh(proposal)
    logger.info("Proposal %s submitted for approval", proposal.id)
    return proposal


async def approve_entire_proposal(
    db: AsyncSession,
    proposal: Proposal,
    actor: Optional[str] = None,
    actor_account_id: Optional[uuid.UUID] = None,
) -> Proposal:
    """The single "approve entire proposal" action (system-flow.md §3):
    approves every still-pending section and takes the Proposal all the way
    to APPROVED in one call — from IN_REVIEW (skipping an explicit submit
    step) or from PENDING_APPROVAL. Sections are marked approved before the
    state transition so the transition's own ApprovalGuardError check never
    fires for sections this same call just approved.
    """
    assert_owns_proposal(proposal, actor_account_id)

    if proposal.status not in (ProposalStatus.IN_REVIEW, ProposalStatus.PENDING_APPROVAL):
        raise InvalidTransitionError(proposal.status, ProposalStatus.APPROVED)

    pending_before = [
        s.section_key.value
        for s in proposal.sections
        if s.approval_status != SectionApprovalStatus.APPROVED
    ]
    for section in proposal.sections:
        section.approval_status = SectionApprovalStatus.APPROVED

    if proposal.status == ProposalStatus.IN_REVIEW:
        transition_proposal(proposal, ProposalStatus.PENDING_APPROVAL)
    transition_proposal(proposal, ProposalStatus.APPROVED)

    record_activity(
        db,
        proposal_id=proposal.id,
        event_type=ActivityEventType.PROPOSAL_APPROVED,
        description="Proposal approved (all sections)",
        actor=actor,
        metadata={"sections_approved_by_this_action": pending_before},
    )
    await db.commit()
    await db.refresh(proposal)
    logger.info("Proposal %s approved (all sections)", proposal.id)
    return proposal


async def request_changes(
    db: AsyncSession,
    proposal: Proposal,
    reason: Optional[str] = None,
    actor: Optional[str] = None,
    actor_account_id: Optional[uuid.UUID] = None,
) -> Proposal:
    """PENDING_APPROVAL -> IN_REVIEW: "not ready yet, more to do" — distinct
    from reject_proposal below in that it never touches REJECTED at all.
    """
    assert_owns_proposal(proposal, actor_account_id)
    transition_proposal(proposal, ProposalStatus.IN_REVIEW)
    record_activity(
        db,
        proposal_id=proposal.id,
        event_type=ActivityEventType.CHANGES_REQUESTED,
        description=f"Changes requested{f': {reason}' if reason else ''}",
        actor=actor,
        metadata={"reason": reason} if reason else {},
    )
    await db.commit()
    await db.refresh(proposal)
    logger.info(
        "Changes requested on proposal %s%s",
        proposal.id,
        f": {reason}" if reason else "",
    )
    return proposal


async def reject_proposal(
    db: AsyncSession,
    proposal: Proposal,
    reason: Optional[str] = None,
    actor: Optional[str] = None,
    actor_account_id: Optional[uuid.UUID] = None,
) -> Proposal:
    """PENDING_APPROVAL -> REJECTED -> IN_REVIEW, chained in one call.
    REJECTED has no dedicated UI/resting behavior of its own — it exists as
    an audit-trail marker that a proposal was explicitly reviewed and turned
    down (vs. request_changes' more casual "not ready yet"), then always
    lands back in IN_REVIEW immediately.
    """
    assert_owns_proposal(proposal, actor_account_id)
    transition_proposal(proposal, ProposalStatus.REJECTED)
    transition_proposal(proposal, ProposalStatus.IN_REVIEW)
    record_activity(
        db,
        proposal_id=proposal.id,
        event_type=ActivityEventType.REJECTED,
        description=f"Proposal rejected{f': {reason}' if reason else ''}",
        actor=actor,
        metadata={"reason": reason} if reason else {},
    )
    await db.commit()
    await db.refresh(proposal)
    logger.info(
        "Proposal %s rejected%s",
        proposal.id,
        f": {reason}" if reason else "",
    )
    return proposal
