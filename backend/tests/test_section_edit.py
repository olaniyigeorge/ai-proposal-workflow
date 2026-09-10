"""Tests for section-level manual editing (Phase 3): edit persistence,
content-origin tracking, and the guard that only edits the targeted section
while leaving siblings untouched — plus the approval-invalidation rule shared
with regeneration (docs/decisions.md #9).
"""

import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.domain.exceptions import SectionNotEditableError
from app.domain.proposal_transitions import transition_proposal
from app.models.proposal import (
    ContentOrigin,
    Proposal,
    ProposalSection,
    ProposalStatus,
    SectionApprovalStatus,
    SectionKey,
)
from app.services.proposal_service import get_proposal_by_id, update_section_content
from tests.conftest import TestAsyncSessionLocal

AUTH_HEADERS = {"Authorization": "Bearer dev-salesperson-token"}


def _make_in_review_proposal() -> Proposal:
    proposal = Proposal(
        status=ProposalStatus.IN_REVIEW,
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
    proposal.sections = [
        ProposalSection(
            section_key=key,
            title=key.value,
            order_index=i,
            content=f"original {key.value}",
            content_origin=ContentOrigin.AI_GENERATED,
            approval_status=SectionApprovalStatus.APPROVED,
            regeneration_count=0,
            version=1,
        )
        for i, key in enumerate(SectionKey)
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
# Service-level tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edit_of_ai_generated_section_marks_human_edited_after_generation(
    db_session,
) -> None:
    """Editing a section that was already AI-touched keeps that history
    (docs/decisions.md #13b) rather than collapsing to the plainer
    `human_edited` — the fixture's sections all start `ai_generated`.
    """
    proposal = await _persist(db_session, _make_in_review_proposal())

    updated = await update_section_content(
        db_session, proposal, SectionKey.INTRODUCTION, "New introduction text."
    )

    edited = next(s for s in updated.sections if s.section_key == SectionKey.INTRODUCTION)
    assert edited.content == "New introduction text."
    assert edited.content_origin == ContentOrigin.HUMAN_EDITED_AFTER_GENERATION
    assert edited.version == 2


@pytest.mark.asyncio
async def test_edit_of_template_default_section_marks_human_edited(db_session) -> None:
    """Editing a section with no AI history at all (never generated) is
    plain `human_edited`, not `human_edited_after_generation`.
    """
    proposal = _make_in_review_proposal()
    for section in proposal.sections:
        if section.section_key == SectionKey.NEXT_STEPS:
            section.content_origin = ContentOrigin.TEMPLATE_DEFAULT
    proposal = await _persist(db_session, proposal)

    updated = await update_section_content(
        db_session, proposal, SectionKey.NEXT_STEPS, "New next steps text."
    )

    edited = next(s for s in updated.sections if s.section_key == SectionKey.NEXT_STEPS)
    assert edited.content_origin == ContentOrigin.HUMAN_EDITED


@pytest.mark.asyncio
async def test_edit_resets_section_approval_to_pending(db_session) -> None:
    proposal = await _persist(db_session, _make_in_review_proposal())

    updated = await update_section_content(
        db_session, proposal, SectionKey.PRICING, "New pricing text."
    )

    edited = next(s for s in updated.sections if s.section_key == SectionKey.PRICING)
    assert edited.approval_status == SectionApprovalStatus.PENDING


@pytest.mark.asyncio
async def test_edit_only_touches_targeted_section(db_session) -> None:
    proposal = await _persist(db_session, _make_in_review_proposal())

    updated = await update_section_content(
        db_session, proposal, SectionKey.INTRODUCTION, "New introduction text."
    )

    for section in updated.sections:
        if section.section_key == SectionKey.INTRODUCTION:
            continue
        assert section.content == f"original {section.section_key.value}"
        assert section.content_origin == ContentOrigin.AI_GENERATED
        assert section.approval_status == SectionApprovalStatus.APPROVED
        assert section.version == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status", [ProposalStatus.PENDING_APPROVAL, ProposalStatus.APPROVED]
)
async def test_edit_while_pending_or_approved_forces_back_to_in_review(
    db_session, status
) -> None:
    proposal = _make_in_review_proposal()
    if status == ProposalStatus.PENDING_APPROVAL:
        transition_proposal(proposal, ProposalStatus.PENDING_APPROVAL)
    else:
        transition_proposal(proposal, ProposalStatus.PENDING_APPROVAL)
        transition_proposal(proposal, ProposalStatus.APPROVED)
    proposal = await _persist(db_session, proposal)

    updated = await update_section_content(
        db_session, proposal, SectionKey.TIMELINE, "New timeline text."
    )

    assert updated.status == ProposalStatus.IN_REVIEW


@pytest.mark.asyncio
async def test_edit_while_in_review_does_not_change_proposal_status(db_session) -> None:
    proposal = await _persist(db_session, _make_in_review_proposal())

    updated = await update_section_content(
        db_session, proposal, SectionKey.TIMELINE, "New timeline text."
    )

    assert updated.status == ProposalStatus.IN_REVIEW


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [
        ProposalStatus.DRAFT,
        ProposalStatus.GENERATING,
        ProposalStatus.DOCUMENT_READY,
        ProposalStatus.DELIVERED,
    ],
)
async def test_edit_rejected_outside_editable_statuses(db_session, status) -> None:
    proposal = _make_in_review_proposal()
    proposal.status = status  # direct set: reaching these via legal transitions is
    # exercised elsewhere; here we only need the guard under test.
    proposal = await _persist(db_session, proposal)

    with pytest.raises(SectionNotEditableError):
        await update_section_content(
            db_session, proposal, SectionKey.TIMELINE, "New timeline text."
        )


# ---------------------------------------------------------------------------
# HTTP-level tests
# ---------------------------------------------------------------------------


async def _seed_proposal_via_db() -> uuid.UUID:
    async with TestAsyncSessionLocal() as db:
        proposal = _make_in_review_proposal()
        db.add(proposal)
        await db.commit()
        await db.refresh(proposal)
        return proposal.id


@pytest.mark.asyncio
async def test_patch_section_requires_auth(async_client: AsyncClient) -> None:
    proposal_id = await _seed_proposal_via_db()
    response = await async_client.patch(
        f"/api/v1/proposals/{proposal_id}/sections/introduction",
        json={"content": "New text."},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_patch_section_success(async_client: AsyncClient) -> None:
    proposal_id = await _seed_proposal_via_db()
    response = await async_client.patch(
        f"/api/v1/proposals/{proposal_id}/sections/introduction",
        json={"content": "New introduction text."},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    body = response.json()
    section = next(s for s in body["sections"] if s["section_key"] == "introduction")
    assert section["content"] == "New introduction text."
    assert section["content_origin"] == "human_edited_after_generation"
    assert section["approval_status"] == "pending"
    assert section["version"] == 2


@pytest.mark.asyncio
async def test_patch_section_rejects_blank_content(async_client: AsyncClient) -> None:
    proposal_id = await _seed_proposal_via_db()
    response = await async_client.patch(
        f"/api/v1/proposals/{proposal_id}/sections/introduction",
        json={"content": "   "},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_section_unknown_section_key_is_422(async_client: AsyncClient) -> None:
    proposal_id = await _seed_proposal_via_db()
    response = await async_client.patch(
        f"/api/v1/proposals/{proposal_id}/sections/not-a-real-section",
        json={"content": "New text."},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_section_unknown_proposal_is_404(async_client: AsyncClient) -> None:
    response = await async_client.patch(
        f"/api/v1/proposals/{uuid.uuid4()}/sections/introduction",
        json={"content": "New text."},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_patch_section_outside_editable_status_is_409(
    async_client: AsyncClient,
) -> None:
    async with TestAsyncSessionLocal() as db:
        proposal = _make_in_review_proposal()
        proposal.status = ProposalStatus.DRAFT
        db.add(proposal)
        await db.commit()
        await db.refresh(proposal)
        proposal_id = proposal.id

    response = await async_client.patch(
        f"/api/v1/proposals/{proposal_id}/sections/introduction",
        json={"content": "New text."},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 409
