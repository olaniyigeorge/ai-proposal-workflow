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


class SectionNotFoundError(DomainError):
    """Raised when a section_key doesn't correspond to a section on the proposal."""

    def __init__(self, section_key: SectionKey) -> None:
        self.section_key = section_key
        super().__init__(f"Section '{section_key.value}' not found on this proposal")


class SectionNotEditableError(DomainError):
    """Raised when a manual edit is attempted while the Proposal is in a status
    that has no defined edit path (e.g. GENERATING, DOCUMENT_READY, DELIVERED).
    """

    def __init__(self, section_key: SectionKey, status: ProposalStatus) -> None:
        self.section_key = section_key
        self.status = status
        super().__init__(
            f"Section '{section_key.value}' cannot be edited while the proposal "
            f"is {status.value}"
        )


class SectionNotApprovableError(DomainError):
    """Raised when a single-section approve is attempted outside IN_REVIEW.

    docs/system-flow.md §3: "each ProposalSection carries its own
    pending/approved flag that a salesperson can set at any point during
    IN_REVIEW" — individual approval is not defined for any other status;
    use the bulk "approve entire proposal" action instead once PENDING_APPROVAL.
    """

    def __init__(self, section_key: SectionKey, status: ProposalStatus) -> None:
        self.section_key = section_key
        self.status = status
        super().__init__(
            f"Section '{section_key.value}' cannot be approved while the "
            f"proposal is {status.value}"
        )


class SectionNotRegenerableError(DomainError):
    """Raised when regeneration is attempted on a section that has no
    AI-generated content to regenerate — a template-pinned section
    (Introduction, Timeline, Pricing, Next Steps; see
    domain/generation.py GENERATED_SECTION_KEYS and architecture.md §4 point 4).
    """

    def __init__(self, section_key: SectionKey) -> None:
        self.section_key = section_key
        super().__init__(
            f"Section '{section_key.value}' has no AI-generated content and "
            "cannot be regenerated"
        )


class DocumentNotReadyError(DomainError):
    """Raised when the document/delivery-link is requested before DOCUMENT_READY."""

    def __init__(self, proposal_id, status: ProposalStatus) -> None:
        self.proposal_id = proposal_id
        self.status = status
        super().__init__(
            f"Proposal {proposal_id} has no document yet (status: {status.value})"
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
