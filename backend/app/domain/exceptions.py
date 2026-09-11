from typing import Optional

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


class DisplayNameTakenError(DomainError):
    """Raised when a salesperson tries to set a display_name another account
    already has — enforced at the DB level (unique constraint), this just
    turns that IntegrityError into a clear, expected 409 instead of a 500.
    """

    def __init__(self, display_name: str) -> None:
        self.display_name = display_name
        super().__init__(f"'{display_name}' is already in use by another account")


class DisplayNameNotSetError(DomainError):
    """Raised when a salesperson tries to claim a proposal before setting
    their own display_name — claiming writes that name into the proposal's
    salesperson_name field, so there must be something to write.
    """

    def __init__(self) -> None:
        super().__init__("Set your display name (in Team) before claiming a proposal")


class ProposalAlreadyAssignedError(DomainError):
    """Raised when claiming a proposal that already has a salesperson_name —
    self-claim only ever applies to a genuinely unassigned proposal
    (decisions #20); reassigning someone else's proposal is out of scope.
    """

    def __init__(self, proposal_id, current_owner: str) -> None:
        self.proposal_id = proposal_id
        self.current_owner = current_owner
        super().__init__(
            f"Proposal {proposal_id} is already assigned to '{current_owner}'"
        )


class NotProposalOwnerError(DomainError):
    """Raised when a salesperson who isn't the claiming owner attempts a
    state-changing action (edit/regenerate/approve/generate-document/deliver)
    on a claimed proposal — ownership enforcement, strict/no-override
    (docs/design-system-redesign-and-ownership-concerns.md §1, resolved
    2026-09-11): once claimed, only the owner may act on it. An unclaimed
    proposal (salesperson_account_id IS NULL) has no owner to enforce against
    and remains open to any authenticated salesperson, unchanged from the
    prior default (decisions #21).
    """

    def __init__(self, proposal_id, current_owner: Optional[str]) -> None:
        self.proposal_id = proposal_id
        self.current_owner = current_owner
        owner_desc = f"'{current_owner}'" if current_owner else "another salesperson"
        super().__init__(
            f"Proposal {proposal_id} is owned by {owner_desc}; only the owner may act on it"
        )


class ProposalNotClaimedError(DomainError):
    """Raised on unclaim/transfer of a proposal that has no owner to release."""

    def __init__(self, proposal_id) -> None:
        self.proposal_id = proposal_id
        super().__init__(f"Proposal {proposal_id} is not currently claimed by anyone")


class TransferTargetInvalidError(DomainError):
    """Raised when transferring a proposal to an account that can't own one —
    not APPROVED, or has never set a display_name (the same precondition
    claim_proposal enforces on the claimer via DisplayNameNotSetError).
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Cannot transfer proposal: {reason}")


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
