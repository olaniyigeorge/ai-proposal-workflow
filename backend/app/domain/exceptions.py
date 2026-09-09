from app.models.proposal import ProposalStatus, SectionKey


class DomainError(Exception):
    """Base class for violations of a proposal/section business rule."""


class InvalidTransitionError(DomainError):
    def __init__(self, current: ProposalStatus, target: ProposalStatus) -> None:
        self.current = current
        self.target = target
        super().__init__(
            f"Cannot transition Proposal from {current.value} to {target.value}"
        )


class ApprovalGuardError(DomainError):
    """Raised when PENDING_APPROVAL -> APPROVED is attempted with sections still pending."""

    def __init__(self, pending_sections: list[SectionKey]) -> None:
        self.pending_sections = pending_sections
        keys = ", ".join(s.value for s in pending_sections)
        super().__init__(
            f"Cannot approve proposal: section(s) still pending approval: {keys}"
        )


class RegenerationCapExceededError(DomainError):
    """Raised on a 4th+ regeneration attempt for the same section."""

    def __init__(self, section_key: SectionKey, attempts: int) -> None:
        self.section_key = section_key
        self.attempts = attempts
        super().__init__(
            f"Section '{section_key.value}' has reached the maximum of "
            f"{attempts} regeneration attempts"
        )


class RegenerationInstructionRequiredError(DomainError):
    """Raised when a regeneration call is missing the mandatory instruction."""

    def __init__(self, section_key: SectionKey) -> None:
        self.section_key = section_key
        super().__init__(
            f"A regeneration instruction is required to regenerate section '{section_key.value}'"
        )


class SectionGenerationError(DomainError):
    """Raised when a Claude call for a section fails during a generation job.

    Caller (services/generation_service.py) must catch this, leave every
    section's content/version/origin untouched, and transition the Proposal to
    GENERATION_FAILED instead of committing a partial/blank section — see
    CLAUDE.md "A failed call must leave the prior state intact".
    """

    def __init__(self, section_key: SectionKey, reason: str) -> None:
        self.section_key = section_key
        self.reason = reason
        super().__init__(
            f"Generation failed for section '{section_key.value}': {reason}"
        )
