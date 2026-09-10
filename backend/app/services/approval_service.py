"""Internal approval workflow (Phase 5): section-level approval, submitting a
proposal for approval, approving the whole proposal in one action, and the
two ways a proposal can land back in IN_REVIEW from PENDING_APPROVAL
(requesting changes vs. a formal reject) — see docs/system-flow.md §3.

Self-approval is the expected path (decisions #14) and any authenticated
salesperson may act on any proposal (decisions #21 working default) — no
actor/owner check here, consistent with the rest of the codebase.
"""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exceptions import InvalidTransitionError, SectionNotFoundError
from app.domain.proposal_transitions import assert_section_approvable, transition_proposal
from app.models.proposal import Proposal, ProposalStatus, SectionApprovalStatus, SectionKey
from app.utils.logger import logger


async def approve_section(
    db: AsyncSession, proposal: Proposal, section_key: SectionKey
) -> Proposal:
    """Approve a single section. Only valid during IN_REVIEW — per
    system-flow.md §3, individual approval isn't defined for any other
    status; once PENDING_APPROVAL, use approve_entire_proposal instead.
    """
    section = next((s for s in proposal.sections if s.section_key == section_key), None)
    if section is None:
        raise SectionNotFoundError(section_key)

    assert_section_approvable(section_key, proposal.status)

    section.approval_status = SectionApprovalStatus.APPROVED
    await db.commit()
    await db.refresh(proposal)
    logger.info("Section '%s' approved on proposal %s", section_key.value, proposal.id)
    return proposal


async def submit_for_approval(db: AsyncSession, proposal: Proposal) -> Proposal:
    """IN_REVIEW -> PENDING_APPROVAL. Not gated on every section already
    being approved — PENDING_APPROVAL is a "final look" checkpoint, and the
    APPROVED transition itself is what enforces "no section left pending"
    (ApprovalGuardError).
    """
    transition_proposal(proposal, ProposalStatus.PENDING_APPROVAL)
    await db.commit()
    await db.refresh(proposal)
    logger.info("Proposal %s submitted for approval", proposal.id)
    return proposal


async def approve_entire_proposal(db: AsyncSession, proposal: Proposal) -> Proposal:
    """The single "approve entire proposal" action (system-flow.md §3):
    approves every still-pending section and takes the Proposal all the way
    to APPROVED in one call — from IN_REVIEW (skipping an explicit submit
    step) or from PENDING_APPROVAL. Sections are marked approved before the
    state transition so the transition's own ApprovalGuardError check never
    fires for sections this same call just approved.
    """
    if proposal.status not in (ProposalStatus.IN_REVIEW, ProposalStatus.PENDING_APPROVAL):
        raise InvalidTransitionError(proposal.status, ProposalStatus.APPROVED)

    for section in proposal.sections:
        section.approval_status = SectionApprovalStatus.APPROVED

    if proposal.status == ProposalStatus.IN_REVIEW:
        transition_proposal(proposal, ProposalStatus.PENDING_APPROVAL)
    transition_proposal(proposal, ProposalStatus.APPROVED)

    await db.commit()
    await db.refresh(proposal)
    logger.info("Proposal %s approved (all sections)", proposal.id)
    return proposal


async def request_changes(
    db: AsyncSession, proposal: Proposal, reason: Optional[str] = None
) -> Proposal:
    """PENDING_APPROVAL -> IN_REVIEW: "not ready yet, more to do" — distinct
    from reject_proposal below in that it never touches REJECTED at all.
    `reason` is logged only (no durable storage yet — no activity-log table
    exists until Phase 8; see docs/edge-cases.md).
    """
    transition_proposal(proposal, ProposalStatus.IN_REVIEW)
    await db.commit()
    await db.refresh(proposal)
    logger.info(
        "Changes requested on proposal %s%s",
        proposal.id,
        f": {reason}" if reason else "",
    )
    return proposal


async def reject_proposal(
    db: AsyncSession, proposal: Proposal, reason: Optional[str] = None
) -> Proposal:
    """PENDING_APPROVAL -> REJECTED -> IN_REVIEW, chained in one call.
    REJECTED has no dedicated UI/resting behavior of its own — it exists as
    an audit-trail marker that a proposal was explicitly reviewed and turned
    down (vs. request_changes' more casual "not ready yet"), then always
    lands back in IN_REVIEW immediately. `reason` is logged only (see
    request_changes' note on durable storage).
    """
    transition_proposal(proposal, ProposalStatus.REJECTED)
    transition_proposal(proposal, ProposalStatus.IN_REVIEW)
    await db.commit()
    await db.refresh(proposal)
    logger.info(
        "Proposal %s rejected%s",
        proposal.id,
        f": {reason}" if reason else "",
    )
    return proposal
