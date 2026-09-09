"""Proposal state machine — see docs/system-flow.md §3 for the diagram this encodes.

Pure domain logic: no I/O. Callers (services/) pass in already-loaded ORM entities
and are responsible for persisting the mutations these functions make.
"""

from app.domain.exceptions import ApprovalGuardError, InvalidTransitionError
from app.models.proposal import Proposal, ProposalStatus, SectionApprovalStatus, SectionKey

# Every legal edge in docs/system-flow.md §3, plus the *_FAILED substates and their
# retry-back-into-preceding-state edges (mentioned in the diagram's note but omitted
# from the ASCII art for readability). Do not add an edge here without updating that
# diagram first (per CLAUDE.md).
ALLOWED_TRANSITIONS: dict[ProposalStatus, frozenset[ProposalStatus]] = {
    ProposalStatus.DRAFT: frozenset({ProposalStatus.GENERATING}),
    ProposalStatus.GENERATING: frozenset(
        {ProposalStatus.IN_REVIEW, ProposalStatus.GENERATION_FAILED}
    ),
    ProposalStatus.GENERATION_FAILED: frozenset({ProposalStatus.GENERATING}),
    ProposalStatus.IN_REVIEW: frozenset(
        {ProposalStatus.GENERATING, ProposalStatus.PENDING_APPROVAL}
    ),
    ProposalStatus.PENDING_APPROVAL: frozenset(
        {
            ProposalStatus.IN_REVIEW,  # "changes requested" / regeneration invalidation
            ProposalStatus.APPROVED,
            ProposalStatus.REJECTED,
        }
    ),
    ProposalStatus.REJECTED: frozenset({ProposalStatus.IN_REVIEW}),
    ProposalStatus.APPROVED: frozenset(
        {
            ProposalStatus.DOCUMENT_GENERATING,
            # Post-approval regeneration invalidates the approval (default rule,
            # docs/decisions.md #9 — not yet fully confirmed).
            ProposalStatus.IN_REVIEW,
        }
    ),
    ProposalStatus.DOCUMENT_GENERATING: frozenset(
        {ProposalStatus.DOCUMENT_READY, ProposalStatus.DOCUMENT_GENERATION_FAILED}
    ),
    ProposalStatus.DOCUMENT_GENERATION_FAILED: frozenset(
        {ProposalStatus.DOCUMENT_GENERATING}
    ),
    ProposalStatus.DOCUMENT_READY: frozenset({ProposalStatus.DELIVERING}),
    ProposalStatus.DELIVERING: frozenset(
        {ProposalStatus.DELIVERED, ProposalStatus.DELIVERY_FAILED}
    ),
    ProposalStatus.DELIVERY_FAILED: frozenset({ProposalStatus.DELIVERING}),
    ProposalStatus.DELIVERED: frozenset({ProposalStatus.CLOSED}),
    ProposalStatus.CLOSED: frozenset(),
}


def assert_transition_allowed(current: ProposalStatus, target: ProposalStatus) -> None:
    if target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise InvalidTransitionError(current, target)


def pending_section_keys(proposal: Proposal) -> list[SectionKey]:
    return [
        section.section_key
        for section in proposal.sections
        if section.approval_status != SectionApprovalStatus.APPROVED
    ]


def all_sections_approved(proposal: Proposal) -> bool:
    return len(pending_section_keys(proposal)) == 0


def transition_proposal(proposal: Proposal, target: ProposalStatus) -> None:
    """Validate and apply a single Proposal state transition.

    Raises InvalidTransitionError for any edge not in ALLOWED_TRANSITIONS, and
    ApprovalGuardError for PENDING_APPROVAL -> APPROVED while any section is still
    pending (never a silent partial-approve — docs/system-flow.md §3 guard rules).
    Does not commit; the caller's service layer owns the DB session.
    """
    assert_transition_allowed(proposal.status, target)

    if target == ProposalStatus.APPROVED:
        pending = pending_section_keys(proposal)
        if pending:
            raise ApprovalGuardError(pending)

    proposal.status = target
