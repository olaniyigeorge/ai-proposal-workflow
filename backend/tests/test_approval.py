"""Tests for the internal approval workflow (Phase 5): section-level approve,
submit-for-approval, bulk approve, request-changes, and reject — guard rules
from docs/system-flow.md §3. Per CLAUDE.md testing requirements: illegal
transitions rejected, APPROVED unreachable with any section pending, and
self-approval succeeds (it's the expected path, not a rejection case).
"""

import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient

import app.services.approval_service as approval_service
from app.domain.exceptions import (
    ApprovalGuardError,
    InvalidTransitionError,
    SectionNotApprovableError,
)
from app.domain.proposal_transitions import transition_proposal
from app.models.proposal import (
    ContentOrigin,
    Proposal,
    ProposalSection,
    ProposalStatus,
    SectionApprovalStatus,
    SectionKey,
)
from app.services.proposal_service import get_proposal_by_id
from tests.conftest import TestAsyncSessionLocal

AUTH_HEADERS = {"Authorization": "Bearer dev-salesperson-token"}


def _make_proposal(
    status: ProposalStatus = ProposalStatus.IN_REVIEW,
    section_statuses: list[SectionApprovalStatus] | None = None,
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
        SectionApprovalStatus.PENDING
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


@pytest_asyncio.fixture
async def db_session():
    async with TestAsyncSessionLocal() as session:
        yield session


async def _persist(db, proposal: Proposal) -> Proposal:
    db.add(proposal)
    await db.flush()
    await db.commit()
    await db.refresh(proposal)
    return await get_proposal_by_id(db, proposal.id)


# ---------------------------------------------------------------------------
# Section-level approve
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_section_succeeds_during_in_review(db_session) -> None:
    proposal = await _persist(db_session, _make_proposal(ProposalStatus.IN_REVIEW))

    updated = await approval_service.approve_section(
        db_session, proposal, SectionKey.INTRODUCTION
    )

    section = next(s for s in updated.sections if s.section_key == SectionKey.INTRODUCTION)
    assert section.approval_status == SectionApprovalStatus.APPROVED


@pytest.mark.asyncio
async def test_approve_section_only_touches_targeted_section(db_session) -> None:
    proposal = await _persist(db_session, _make_proposal(ProposalStatus.IN_REVIEW))

    updated = await approval_service.approve_section(
        db_session, proposal, SectionKey.INTRODUCTION
    )

    for section in updated.sections:
        if section.section_key == SectionKey.INTRODUCTION:
            continue
        assert section.approval_status == SectionApprovalStatus.PENDING


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [
        ProposalStatus.DRAFT,
        ProposalStatus.GENERATING,
        ProposalStatus.PENDING_APPROVAL,
        ProposalStatus.APPROVED,
        ProposalStatus.DOCUMENT_READY,
    ],
)
async def test_approve_section_rejected_outside_in_review(db_session, status) -> None:
    proposal = _make_proposal(ProposalStatus.IN_REVIEW)
    proposal.status = status
    proposal = await _persist(db_session, proposal)

    with pytest.raises(SectionNotApprovableError):
        await approval_service.approve_section(db_session, proposal, SectionKey.INTRODUCTION)


# ---------------------------------------------------------------------------
# Submit for approval
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_for_approval_transitions_to_pending(db_session) -> None:
    proposal = await _persist(db_session, _make_proposal(ProposalStatus.IN_REVIEW))
    updated = await approval_service.submit_for_approval(db_session, proposal)
    assert updated.status == ProposalStatus.PENDING_APPROVAL


@pytest.mark.asyncio
async def test_submit_for_approval_does_not_require_all_sections_approved(db_session) -> None:
    """PENDING_APPROVAL is a checkpoint, not a completion gate — the
    ApprovalGuardError only fires on the PENDING_APPROVAL -> APPROVED edge.
    """
    proposal = await _persist(
        db_session,
        _make_proposal(ProposalStatus.IN_REVIEW, [SectionApprovalStatus.PENDING] * 6),
    )
    updated = await approval_service.submit_for_approval(db_session, proposal)
    assert updated.status == ProposalStatus.PENDING_APPROVAL


@pytest.mark.asyncio
async def test_submit_for_approval_rejected_from_wrong_status(db_session) -> None:
    proposal = _make_proposal(ProposalStatus.DRAFT)
    proposal = await _persist(db_session, proposal)
    with pytest.raises(InvalidTransitionError):
        await approval_service.submit_for_approval(db_session, proposal)


# ---------------------------------------------------------------------------
# Approve entire proposal (bulk action)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_entire_proposal_from_in_review_approves_all_and_transitions(
    db_session,
) -> None:
    proposal = await _persist(
        db_session,
        _make_proposal(ProposalStatus.IN_REVIEW, [SectionApprovalStatus.PENDING] * 6),
    )

    updated = await approval_service.approve_entire_proposal(db_session, proposal)

    assert updated.status == ProposalStatus.APPROVED
    assert all(s.approval_status == SectionApprovalStatus.APPROVED for s in updated.sections)


@pytest.mark.asyncio
async def test_approve_entire_proposal_from_pending_approval(db_session) -> None:
    proposal = _make_proposal(
        ProposalStatus.IN_REVIEW,
        [SectionApprovalStatus.APPROVED] * 5 + [SectionApprovalStatus.PENDING],
    )
    transition_proposal(proposal, ProposalStatus.PENDING_APPROVAL)
    proposal = await _persist(db_session, proposal)

    updated = await approval_service.approve_entire_proposal(db_session, proposal)

    assert updated.status == ProposalStatus.APPROVED
    assert all(s.approval_status == SectionApprovalStatus.APPROVED for s in updated.sections)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [
        ProposalStatus.DRAFT,
        ProposalStatus.GENERATING,
        ProposalStatus.APPROVED,
        ProposalStatus.REJECTED,
    ],
)
async def test_approve_entire_proposal_rejected_from_wrong_status(db_session, status) -> None:
    proposal = _make_proposal(ProposalStatus.IN_REVIEW)
    proposal.status = status
    proposal = await _persist(db_session, proposal)

    with pytest.raises(InvalidTransitionError):
        await approval_service.approve_entire_proposal(db_session, proposal)


@pytest.mark.asyncio
async def test_approve_entire_proposal_self_approval_succeeds(db_session) -> None:
    """Self-approval is the expected path (decisions #14) — no actor check,
    no special-casing, no rejection.
    """
    proposal = await _persist(
        db_session,
        _make_proposal(ProposalStatus.IN_REVIEW, [SectionApprovalStatus.APPROVED] * 6),
    )
    updated = await approval_service.approve_entire_proposal(db_session, proposal)
    assert updated.status == ProposalStatus.APPROVED


# ---------------------------------------------------------------------------
# Request changes / reject
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_request_changes_returns_to_in_review(db_session) -> None:
    proposal = _make_proposal(ProposalStatus.IN_REVIEW)
    transition_proposal(proposal, ProposalStatus.PENDING_APPROVAL)
    proposal = await _persist(db_session, proposal)

    updated = await approval_service.request_changes(db_session, proposal, "needs more detail")
    assert updated.status == ProposalStatus.IN_REVIEW


@pytest.mark.asyncio
async def test_request_changes_rejected_from_wrong_status(db_session) -> None:
    proposal = await _persist(db_session, _make_proposal(ProposalStatus.IN_REVIEW))
    with pytest.raises(InvalidTransitionError):
        await approval_service.request_changes(db_session, proposal)


@pytest.mark.asyncio
async def test_reject_proposal_chains_to_in_review(db_session) -> None:
    proposal = _make_proposal(ProposalStatus.IN_REVIEW)
    transition_proposal(proposal, ProposalStatus.PENDING_APPROVAL)
    proposal = await _persist(db_session, proposal)

    updated = await approval_service.reject_proposal(db_session, proposal, "pricing needs work")
    assert updated.status == ProposalStatus.IN_REVIEW


@pytest.mark.asyncio
async def test_reject_proposal_rejected_from_wrong_status(db_session) -> None:
    proposal = await _persist(db_session, _make_proposal(ProposalStatus.IN_REVIEW))
    with pytest.raises(InvalidTransitionError):
        await approval_service.reject_proposal(db_session, proposal)


# ---------------------------------------------------------------------------
# HTTP-level tests
# ---------------------------------------------------------------------------


async def _seed_proposal_via_db(
    status: ProposalStatus = ProposalStatus.IN_REVIEW,
    section_statuses: list[SectionApprovalStatus] | None = None,
) -> uuid.UUID:
    async with TestAsyncSessionLocal() as db:
        proposal = _make_proposal(status, section_statuses)
        db.add(proposal)
        await db.commit()
        await db.refresh(proposal)
        return proposal.id


@pytest.mark.asyncio
async def test_approve_section_endpoint_requires_auth(async_client: AsyncClient) -> None:
    proposal_id = await _seed_proposal_via_db()
    response = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/sections/introduction/approve"
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_approve_section_endpoint_success(async_client: AsyncClient) -> None:
    proposal_id = await _seed_proposal_via_db()
    response = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/sections/introduction/approve",
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    section = next(
        s for s in response.json()["sections"] if s["section_key"] == "introduction"
    )
    assert section["approval_status"] == "approved"


@pytest.mark.asyncio
async def test_approve_entire_proposal_endpoint_rejects_with_guard_when_impossible(
    async_client: AsyncClient,
) -> None:
    proposal_id = await _seed_proposal_via_db(status=ProposalStatus.DRAFT)
    response = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/approve", headers=AUTH_HEADERS
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_approve_entire_proposal_endpoint_success(async_client: AsyncClient) -> None:
    proposal_id = await _seed_proposal_via_db()
    response = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/approve", headers=AUTH_HEADERS
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "APPROVED"
    assert all(s["approval_status"] == "approved" for s in body["sections"])


@pytest.mark.asyncio
async def test_submit_for_approval_endpoint_success(async_client: AsyncClient) -> None:
    proposal_id = await _seed_proposal_via_db()
    response = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/submit-for-approval", headers=AUTH_HEADERS
    )
    assert response.status_code == 200
    assert response.json()["status"] == "PENDING_APPROVAL"


@pytest.mark.asyncio
async def test_request_changes_endpoint_success(async_client: AsyncClient) -> None:
    proposal_id = await _seed_proposal_via_db(status=ProposalStatus.PENDING_APPROVAL)
    response = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/request-changes",
        json={"reason": "needs more detail"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "IN_REVIEW"


@pytest.mark.asyncio
async def test_reject_proposal_endpoint_success(async_client: AsyncClient) -> None:
    proposal_id = await _seed_proposal_via_db(status=ProposalStatus.PENDING_APPROVAL)
    response = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/reject",
        json={"reason": "pricing needs work"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "IN_REVIEW"


@pytest.mark.asyncio
async def test_reject_proposal_endpoint_accepts_no_reason(async_client: AsyncClient) -> None:
    proposal_id = await _seed_proposal_via_db(status=ProposalStatus.PENDING_APPROVAL)
    response = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/reject", json={}, headers=AUTH_HEADERS
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_approve_section_endpoint_unknown_proposal_is_404(
    async_client: AsyncClient,
) -> None:
    response = await async_client.post(
        f"/api/v1/proposals/{uuid.uuid4()}/sections/introduction/approve",
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 404
