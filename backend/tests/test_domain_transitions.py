"""Pure unit tests for app.domain — no DB, no HTTP. Every edge in
docs/system-flow.md §3 plus its guard rules must be exercised here per
CLAUDE.md's testing requirements (illegal transitions rejected, not just legal
ones accepted).
"""

import pytest

from app.domain.exceptions import (
    ApprovalGuardError,
    InvalidTransitionError,
    RegenerationCapExceededError,
    RegenerationInstructionRequiredError,
)
from app.domain.proposal_transitions import (
    ALLOWED_TRANSITIONS,
    all_sections_approved,
    pending_section_keys,
    transition_proposal,
)
from app.domain.regeneration import (
    MAX_REGENERATION_ATTEMPTS,
    assert_can_regenerate_section,
    regeneration_invalidates_approval,
)
from app.models.proposal import (
    ContentOrigin,
    Proposal,
    ProposalSection,
    ProposalStatus,
    SectionApprovalStatus,
    SectionKey,
)


def make_proposal(
    status: ProposalStatus, section_statuses: list[SectionApprovalStatus] | None = None
) -> Proposal:
    proposal = Proposal(
        status=status,
        client_name="Alice",
        client_email="alice@acme.com",
        company_name="Acme",
        salesperson_name="Bob",
        date_of_call="2026-09-08",
        client_needs_summary="needs",
        project_scope="scope",
        goals_and_objectives="goals",
        recommended_services="services",
        proposed_timeline="timeline",
        estimated_pricing="$1",
    )
    statuses = section_statuses if section_statuses is not None else [
        SectionApprovalStatus.APPROVED
    ] * 6
    proposal.sections = [
        ProposalSection(
            section_key=key,
            title=key.value,
            order_index=i,
            content="x",
            content_origin=ContentOrigin.AI_GENERATED,
            approval_status=statuses[i],
            regeneration_count=0,
            version=1,
        )
        for i, key in enumerate(list(SectionKey)[: len(statuses)])
    ]
    return proposal


# ---------------------------------------------------------------------------
# Legal transitions succeed
# ---------------------------------------------------------------------------

LEGAL_EDGES = [
    (ProposalStatus.DRAFT, ProposalStatus.GENERATING),
    (ProposalStatus.GENERATING, ProposalStatus.IN_REVIEW),
    (ProposalStatus.GENERATING, ProposalStatus.GENERATION_FAILED),
    (ProposalStatus.GENERATION_FAILED, ProposalStatus.GENERATING),
    (ProposalStatus.IN_REVIEW, ProposalStatus.GENERATING),
    (ProposalStatus.IN_REVIEW, ProposalStatus.PENDING_APPROVAL),
    (ProposalStatus.PENDING_APPROVAL, ProposalStatus.IN_REVIEW),
    (ProposalStatus.PENDING_APPROVAL, ProposalStatus.APPROVED),
    (ProposalStatus.PENDING_APPROVAL, ProposalStatus.REJECTED),
    (ProposalStatus.REJECTED, ProposalStatus.IN_REVIEW),
    (ProposalStatus.APPROVED, ProposalStatus.DOCUMENT_GENERATING),
    (ProposalStatus.APPROVED, ProposalStatus.IN_REVIEW),
    (ProposalStatus.DOCUMENT_GENERATING, ProposalStatus.DOCUMENT_READY),
    (ProposalStatus.DOCUMENT_GENERATING, ProposalStatus.DOCUMENT_GENERATION_FAILED),
    (ProposalStatus.DOCUMENT_GENERATION_FAILED, ProposalStatus.DOCUMENT_GENERATING),
    (ProposalStatus.DOCUMENT_READY, ProposalStatus.DELIVERING),
    (ProposalStatus.DELIVERING, ProposalStatus.DELIVERED),
    (ProposalStatus.DELIVERING, ProposalStatus.DELIVERY_FAILED),
    (ProposalStatus.DELIVERY_FAILED, ProposalStatus.DELIVERING),
    (ProposalStatus.DELIVERED, ProposalStatus.CLOSED),
]


@pytest.mark.parametrize("current,target", LEGAL_EDGES)
def test_legal_transition_succeeds(current, target) -> None:
    proposal = make_proposal(current)
    transition_proposal(proposal, target)
    assert proposal.status == target


# ---------------------------------------------------------------------------
# Illegal transitions rejected — every (current, target) pair not in the legal
# set, for every status, must raise.
# ---------------------------------------------------------------------------

ALL_STATUSES = list(ProposalStatus)
LEGAL_SET = set(LEGAL_EDGES)
ILLEGAL_EDGES = [
    (current, target)
    for current in ALL_STATUSES
    for target in ALL_STATUSES
    if current != target and (current, target) not in LEGAL_SET
]


@pytest.mark.parametrize("current,target", ILLEGAL_EDGES)
def test_illegal_transition_rejected(current, target) -> None:
    proposal = make_proposal(current)
    with pytest.raises(InvalidTransitionError) as exc_info:
        transition_proposal(proposal, target)
    assert exc_info.value.current == current
    assert exc_info.value.target == target
    # Rejected transition must not mutate state.
    assert proposal.status == current


def test_closed_is_terminal() -> None:
    assert ALLOWED_TRANSITIONS[ProposalStatus.CLOSED] == frozenset()


# ---------------------------------------------------------------------------
# Approval guard: APPROVED is unreachable with any section still pending.
# ---------------------------------------------------------------------------


def test_approve_rejected_with_one_section_pending() -> None:
    statuses = [SectionApprovalStatus.APPROVED] * 5 + [SectionApprovalStatus.PENDING]
    proposal = make_proposal(ProposalStatus.PENDING_APPROVAL, statuses)

    with pytest.raises(ApprovalGuardError) as exc_info:
        transition_proposal(proposal, ProposalStatus.APPROVED)

    assert exc_info.value.pending_sections == [SectionKey.NEXT_STEPS]
    assert proposal.status == ProposalStatus.PENDING_APPROVAL  # unchanged


def test_approve_rejected_with_all_sections_pending() -> None:
    statuses = [SectionApprovalStatus.PENDING] * 6
    proposal = make_proposal(ProposalStatus.PENDING_APPROVAL, statuses)

    with pytest.raises(ApprovalGuardError):
        transition_proposal(proposal, ProposalStatus.APPROVED)


def test_approve_succeeds_when_all_sections_approved() -> None:
    proposal = make_proposal(
        ProposalStatus.PENDING_APPROVAL, [SectionApprovalStatus.APPROVED] * 6
    )
    transition_proposal(proposal, ProposalStatus.APPROVED)
    assert proposal.status == ProposalStatus.APPROVED


def test_all_sections_approved_helper() -> None:
    approved = make_proposal(ProposalStatus.IN_REVIEW, [SectionApprovalStatus.APPROVED] * 6)
    assert all_sections_approved(approved) is True

    mixed = make_proposal(
        ProposalStatus.IN_REVIEW,
        [SectionApprovalStatus.APPROVED] * 5 + [SectionApprovalStatus.PENDING],
    )
    assert all_sections_approved(mixed) is False
    assert pending_section_keys(mixed) == [SectionKey.NEXT_STEPS]


# ---------------------------------------------------------------------------
# Document/delivery unreachable from IN_REVIEW / PENDING_APPROVAL (structural,
# not just an unlisted edge — asserted explicitly since it's a named guard rule).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "current", [ProposalStatus.IN_REVIEW, ProposalStatus.PENDING_APPROVAL]
)
@pytest.mark.parametrize(
    "target",
    [
        ProposalStatus.DOCUMENT_GENERATING,
        ProposalStatus.DOCUMENT_READY,
        ProposalStatus.DELIVERING,
        ProposalStatus.DELIVERED,
    ],
)
def test_document_and_delivery_unreachable_before_approval(current, target) -> None:
    proposal = make_proposal(current)
    with pytest.raises(InvalidTransitionError):
        transition_proposal(proposal, target)


# ---------------------------------------------------------------------------
# Regeneration rules
# ---------------------------------------------------------------------------


def test_regeneration_rejected_without_instruction() -> None:
    section = ProposalSection(
        section_key=SectionKey.INTRODUCTION,
        title="Introduction",
        order_index=0,
        content="x",
        content_origin=ContentOrigin.AI_GENERATED,
        approval_status=SectionApprovalStatus.PENDING,
        regeneration_count=0,
        version=1,
    )
    with pytest.raises(RegenerationInstructionRequiredError):
        assert_can_regenerate_section(section, "")
    with pytest.raises(RegenerationInstructionRequiredError):
        assert_can_regenerate_section(section, "   ")


def test_fourth_regeneration_attempt_rejected() -> None:
    section = ProposalSection(
        section_key=SectionKey.INTRODUCTION,
        title="Introduction",
        order_index=0,
        content="x",
        content_origin=ContentOrigin.AI_GENERATED,
        approval_status=SectionApprovalStatus.PENDING,
        regeneration_count=MAX_REGENERATION_ATTEMPTS,
        version=1,
    )
    with pytest.raises(RegenerationCapExceededError) as exc_info:
        assert_can_regenerate_section(section, "make it more formal")
    assert exc_info.value.attempts == MAX_REGENERATION_ATTEMPTS


def test_regeneration_allowed_within_cap() -> None:
    section = ProposalSection(
        section_key=SectionKey.INTRODUCTION,
        title="Introduction",
        order_index=0,
        content="x",
        content_origin=ContentOrigin.AI_GENERATED,
        approval_status=SectionApprovalStatus.PENDING,
        regeneration_count=MAX_REGENERATION_ATTEMPTS - 1,
        version=1,
    )
    assert_can_regenerate_section(section, "make it more formal")  # does not raise


@pytest.mark.parametrize(
    "status,expected",
    [
        (ProposalStatus.IN_REVIEW, False),
        (ProposalStatus.PENDING_APPROVAL, True),
        (ProposalStatus.APPROVED, True),
        (ProposalStatus.DOCUMENT_READY, False),
        (ProposalStatus.DELIVERED, False),
    ],
)
def test_regeneration_invalidates_approval(status, expected) -> None:
    assert regeneration_invalidates_approval(status) is expected
