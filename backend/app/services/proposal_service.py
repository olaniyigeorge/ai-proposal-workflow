import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.content_origin import content_origin_after_manual_edit
from app.domain.exceptions import (
    ProposalAlreadyAssignedError,
    ProposalNotClaimedError,
    SectionNotFoundError,
    TransferTargetInvalidError,
)
from app.domain.ownership import assert_owns_proposal
from app.domain.proposal_transitions import assert_section_editable, transition_proposal
from app.domain.regeneration import regeneration_invalidates_approval
from app.models.activity_log import ActivityEventType
from app.models.proposal import (
    Proposal,
    ProposalStatus,
    SectionApprovalStatus,
    SectionKey,
)
from app.models.salesperson_account import SalespersonAccount, SalespersonAccountStatus
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
    actor_account_id: Optional[uuid.UUID] = None,
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
    assert_owns_proposal(proposal, actor_account_id)

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
    db: AsyncSession,
    proposal: Proposal,
    display_name: str,
    account_id: uuid.UUID,
    actor: Optional[str] = None,
) -> Proposal:
    """Manual self-claim of a genuinely unassigned proposal (decisions #20's
    review-queue claim step, resolved 2026-09-11) — never automatic, never a
    string-match against the free-text salesperson_name a client or another
    salesperson might have typed at intake (CLAUDE.md explicitly forbids
    that). Only applies while salesperson_name is NULL/blank; a proposal
    that already has an owner (however it got one) is not reassignable
    through this endpoint — use unclaim_proposal/transfer_proposal instead
    (ownership enforcement, resolved 2026-09-11).

    Sets both the display label (salesperson_name) and the stable owner
    (salesperson_account_id) — see app/domain/ownership.py for why
    enforcement compares against the latter, not the former.
    """
    if proposal.salesperson_name and proposal.salesperson_name.strip():
        raise ProposalAlreadyAssignedError(proposal.id, proposal.salesperson_name)

    proposal.salesperson_name = display_name
    proposal.salesperson_account_id = account_id
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


async def unclaim_proposal(
    db: AsyncSession,
    proposal: Proposal,
    actor_account_id: Optional[uuid.UUID],
    actor: Optional[str] = None,
) -> Proposal:
    """The owner releases a claimed proposal back to unassigned. Strict
    ownership (resolved 2026-09-11) means only the current owner may do
    this — there's no admin override and no other salesperson can unclaim
    someone else's proposal.
    """
    if proposal.salesperson_account_id is None:
        raise ProposalNotClaimedError(proposal.id)

    assert_owns_proposal(proposal, actor_account_id)

    previous_owner = proposal.salesperson_name
    proposal.salesperson_name = None
    proposal.salesperson_account_id = None
    record_activity(
        db,
        proposal_id=proposal.id,
        event_type=ActivityEventType.PROPOSAL_UNCLAIMED,
        description=f"Proposal unclaimed by {previous_owner}",
        actor=actor,
        metadata={"previous_owner": previous_owner},
    )
    await db.commit()
    await db.refresh(proposal)
    logger.info("Proposal %s unclaimed by %s", proposal.id, previous_owner)
    return proposal


async def transfer_proposal(
    db: AsyncSession,
    proposal: Proposal,
    target_account: SalespersonAccount,
    actor_account_id: Optional[uuid.UUID],
    actor: Optional[str] = None,
) -> Proposal:
    """The owner hands a claimed proposal directly to a named colleague.
    Strict ownership (resolved 2026-09-11): only the current owner may
    transfer it — there's no admin override. The target must be an
    APPROVED account with a display_name set (the same precondition
    claim_proposal enforces on a self-claim), since transferring to an
    account that can't itself claim anything would just recreate the
    "labeled but not really owned" problem this whole model exists to fix.
    """
    if proposal.salesperson_account_id is None:
        raise ProposalNotClaimedError(proposal.id)

    assert_owns_proposal(proposal, actor_account_id)

    if target_account.status != SalespersonAccountStatus.APPROVED:
        raise TransferTargetInvalidError("target account is not an approved salesperson")
    if not target_account.display_name or not target_account.display_name.strip():
        raise TransferTargetInvalidError("target account has not set a display name")

    previous_owner = proposal.salesperson_name
    proposal.salesperson_name = target_account.display_name
    proposal.salesperson_account_id = target_account.id
    record_activity(
        db,
        proposal_id=proposal.id,
        event_type=ActivityEventType.PROPOSAL_TRANSFERRED,
        description=f"Proposal transferred from {previous_owner} to {target_account.display_name}",
        actor=actor,
        metadata={"from": previous_owner, "to": target_account.display_name},
    )
    await db.commit()
    await db.refresh(proposal)
    logger.info(
        "Proposal %s transferred from %s to %s",
        proposal.id,
        previous_owner,
        target_account.display_name,
    )
    return proposal
