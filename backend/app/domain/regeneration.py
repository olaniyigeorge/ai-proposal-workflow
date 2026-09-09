"""Section-regeneration business rules — see CLAUDE.md "Important Architectural
Constraints" (regeneration cap, mandatory instruction, approval invalidation).
"""

from app.domain.exceptions import (
    RegenerationCapExceededError,
    RegenerationInstructionRequiredError,
)
from app.models.proposal import ProposalSection, ProposalStatus

MAX_REGENERATION_ATTEMPTS = 3


def assert_can_regenerate_section(section: ProposalSection, instruction: str) -> None:
    """Raises if the instruction is missing/blank, or the section has already
    used its 3 regeneration attempts. Callers must reject the 4th attempt with a
    clear error, never silently no-op.
    """
    if not instruction or not instruction.strip():
        raise RegenerationInstructionRequiredError(section.section_key)

    if section.regeneration_count >= MAX_REGENERATION_ATTEMPTS:
        raise RegenerationCapExceededError(section.section_key, section.regeneration_count)


def regeneration_invalidates_approval(status: ProposalStatus) -> bool:
    """Whether regenerating a section while the Proposal is in `status` must force
    the Proposal back to IN_REVIEW and reset that section's approval status.

    True for PENDING_APPROVAL and APPROVED (docs/system-flow.md §3 guard rules;
    the APPROVED case is a default per docs/decisions.md #9, not yet fully
    confirmed). False for IN_REVIEW, where no proposal-level transition is needed.
    Any other status (e.g. DOCUMENT_READY, DELIVERED) has no defined regeneration
    path yet — callers must reject those with InvalidTransitionError rather than
    guessing.
    """
    return status in (ProposalStatus.PENDING_APPROVAL, ProposalStatus.APPROVED)
