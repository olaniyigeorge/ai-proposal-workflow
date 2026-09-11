from app.domain.exceptions import (
    ApprovalGuardError,
    ClientResponseError,
    DomainError,
    FeedbackError,
    InvalidTransitionError,
    RegenerationCapExceededError,
    RegenerationInstructionRequiredError,
)
from app.domain.proposal_transitions import (
    ALLOWED_TRANSITIONS,
    all_sections_approved,
    assert_transition_allowed,
    pending_section_keys,
    transition_proposal,
)
from app.domain.regeneration import (
    MAX_REGENERATION_ATTEMPTS,
    assert_can_regenerate_section,
    regeneration_invalidates_approval,
)

__all__ = [
    "DomainError",
    "InvalidTransitionError",
    "ApprovalGuardError",
    "RegenerationCapExceededError",
    "RegenerationInstructionRequiredError",
    "ALLOWED_TRANSITIONS",
    "assert_transition_allowed",
    "transition_proposal",
    "all_sections_approved",
    "pending_section_keys",
    "MAX_REGENERATION_ATTEMPTS",
    "assert_can_regenerate_section",
    "regeneration_invalidates_approval",
]
