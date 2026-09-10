"""Tests for full-proposal generation (Phase 2): domain prompt assembly and
the generation service's DRAFT -> GENERATING -> IN_REVIEW/GENERATION_FAILED
flow. Per CLAUDE.md testing requirements: a failed Claude call must leave
every section's prior content/version/origin untouched, not half-written.
"""

import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

import app.services.generation_service as generation_service
from app.adapters.claude_client import ClaudeCallResult, ClaudeGenerationError
from app.domain.exceptions import InvalidTransitionError, SectionGenerationError
from app.domain.generation import assemble_section_content, build_user_prompt
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


def _fake_result(text: str) -> ClaudeCallResult:
    return ClaudeCallResult(
        text=text, model="claude-test", input_tokens=10, output_tokens=20, stop_reason="end_turn"
    )


# ---------------------------------------------------------------------------
# Pure domain tests — no DB, no HTTP.
# ---------------------------------------------------------------------------


def make_proposal() -> Proposal:
    return Proposal(
        status=ProposalStatus.DRAFT,
        client_name="Alice",
        client_email="alice@acme.com",
        company_name="Acme",
        salesperson_name="Bob",
        date_of_call="2026-09-08",
        client_needs_summary="needs",
        project_scope="Build a widget factory",
        goals_and_objectives="goals",
        recommended_services="services",
        proposed_timeline="timeline",
        estimated_pricing="$1",
    )


def test_build_user_prompt_rejects_non_generated_section() -> None:
    proposal = make_proposal()
    with pytest.raises(ValueError):
        build_user_prompt(proposal, SectionKey.TIMELINE)


def test_assemble_section_content_keeps_pinned_scope_for_proposed_solution() -> None:
    result = assemble_section_content(
        SectionKey.PROPOSED_SOLUTION, "Scope:\nBuild a widget factory", "  Here is the approach.  "
    )
    assert result == "Scope:\nBuild a widget factory\n\nHere is the approach."


def test_assemble_section_content_is_pure_generated_for_deliverables() -> None:
    assert (
        assemble_section_content(SectionKey.DELIVERABLES, "old pinned text", "  A list.  ")
        == "A list."
    )


def test_assemble_section_content_is_pure_generated_for_introduction() -> None:
    assert (
        assemble_section_content(SectionKey.INTRODUCTION, "Needs: x\nGoals: y", "  Thanks.  ")
        == "Thanks."
    )


def test_build_user_prompt_for_introduction_instructs_paraphrase_not_invention() -> None:
    proposal = make_proposal()
    prompt = build_user_prompt(proposal, SectionKey.INTRODUCTION)
    assert "paraphrase" in prompt.lower()
    assert "do not add any need" in prompt.lower()
    assert "Client's stated needs: needs" in prompt
    assert "Goals and objectives: goals" in prompt


# ---------------------------------------------------------------------------
# Service-level tests — real (in-memory) DB session, Claude call monkeypatched.
# ---------------------------------------------------------------------------


def _make_full_proposal() -> Proposal:
    proposal = make_proposal()
    sections_defs = [
        (SectionKey.INTRODUCTION, "Introduction", 0, "Needs: needs\nGoals: goals"),
        (SectionKey.PROPOSED_SOLUTION, "Proposed Solution", 1, "Scope:\nBuild a widget factory"),
        (SectionKey.DELIVERABLES, "Deliverables", 2, "Services & Deliverables:\nservices"),
        (SectionKey.TIMELINE, "Timeline", 3, "timeline"),
        (SectionKey.PRICING, "Pricing", 4, "$1"),
        (SectionKey.NEXT_STEPS, "Next Steps", 5, "1. Review.\n2. Sign.\n3. Kickoff."),
    ]
    proposal.sections = [
        ProposalSection(
            section_key=key,
            title=title,
            order_index=order,
            content=content,
            content_origin=ContentOrigin.TEMPLATE_DEFAULT,
            approval_status=SectionApprovalStatus.PENDING,
            regeneration_count=0,
            version=1,
        )
        for key, title, order, content in sections_defs
    ]
    return proposal


@pytest_asyncio.fixture
async def db_session():
    async with TestAsyncSessionLocal() as session:
        yield session


async def _persist_proposal(db) -> Proposal:
    proposal = _make_full_proposal()
    db.add(proposal)
    await db.flush()
    await db.commit()
    await db.refresh(proposal)
    return proposal


@pytest.mark.asyncio
async def test_start_generation_from_draft_succeeds(db_session) -> None:
    proposal = await _persist_proposal(db_session)
    result = await generation_service.start_generation(db_session, proposal)
    assert result.status == ProposalStatus.GENERATING


@pytest.mark.asyncio
async def test_start_generation_rejects_wrong_state(db_session) -> None:
    # IN_REVIEW -> GENERATING is legal (re-running full generation while still
    # in review), so use PENDING_APPROVAL — generation has no defined path
    # from there per docs/system-flow.md §3.
    proposal = await _persist_proposal(db_session)
    transition_proposal(proposal, ProposalStatus.GENERATING)
    transition_proposal(proposal, ProposalStatus.IN_REVIEW)
    transition_proposal(proposal, ProposalStatus.PENDING_APPROVAL)
    db_session.add(proposal)
    await db_session.commit()

    with pytest.raises(InvalidTransitionError):
        await generation_service.start_generation(db_session, proposal)


@pytest.mark.asyncio
async def test_generate_all_sections_success_updates_only_generated_sections(
    db_session, monkeypatch
) -> None:
    proposal = await _persist_proposal(db_session)
    transition_proposal(proposal, ProposalStatus.GENERATING)
    await db_session.commit()

    async def fake_generate_text(system_prompt: str, user_prompt: str) -> ClaudeCallResult:
        return _fake_result("Generated text.")

    monkeypatch.setattr(generation_service, "generate_text", fake_generate_text)

    await generation_service.generate_all_sections(db_session, proposal)

    assert proposal.status == ProposalStatus.IN_REVIEW
    by_key = {s.section_key: s for s in proposal.sections}

    assert by_key[SectionKey.INTRODUCTION].content == "Generated text."
    assert by_key[SectionKey.INTRODUCTION].content_origin == ContentOrigin.AI_GENERATED

    assert by_key[SectionKey.PROPOSED_SOLUTION].content == (
        "Scope:\nBuild a widget factory\n\nGenerated text."
    )
    assert by_key[SectionKey.PROPOSED_SOLUTION].content_origin == ContentOrigin.AI_GENERATED

    assert by_key[SectionKey.DELIVERABLES].content == "Generated text."
    assert by_key[SectionKey.DELIVERABLES].content_origin == ContentOrigin.AI_GENERATED

    # Sibling sections never touched by generation — content, version, and
    # origin flag must remain exactly as intake wrote them.
    assert by_key[SectionKey.TIMELINE].content == "timeline"
    assert by_key[SectionKey.TIMELINE].content_origin == ContentOrigin.TEMPLATE_DEFAULT
    assert by_key[SectionKey.TIMELINE].version == 1
    assert by_key[SectionKey.PRICING].content == "$1"
    assert by_key[SectionKey.PRICING].content_origin == ContentOrigin.TEMPLATE_DEFAULT
    assert by_key[SectionKey.NEXT_STEPS].content == "1. Review.\n2. Sign.\n3. Kickoff."
    assert by_key[SectionKey.NEXT_STEPS].content_origin == ContentOrigin.TEMPLATE_DEFAULT


@pytest.mark.asyncio
async def test_generate_all_sections_failure_leaves_every_section_untouched(
    db_session, monkeypatch
) -> None:
    proposal = await _persist_proposal(db_session)
    transition_proposal(proposal, ProposalStatus.GENERATING)
    await db_session.commit()

    original_contents = {s.section_key: s.content for s in proposal.sections}
    original_origins = {s.section_key: s.content_origin for s in proposal.sections}

    async def failing_generate_text(system_prompt: str, user_prompt: str) -> str:
        raise ClaudeGenerationError("rate limited")

    monkeypatch.setattr(generation_service, "generate_text", failing_generate_text)

    await generation_service.generate_all_sections(db_session, proposal)

    assert proposal.status == ProposalStatus.GENERATION_FAILED
    for section in proposal.sections:
        assert section.content == original_contents[section.section_key]
        assert section.content_origin == original_origins[section.section_key]
        assert section.version == 1


@pytest.mark.asyncio
async def test_generate_all_sections_can_retry_after_failure(db_session, monkeypatch) -> None:
    """GENERATION_FAILED -> GENERATING -> IN_REVIEW is a legal retry path."""
    proposal = await _persist_proposal(db_session)
    transition_proposal(proposal, ProposalStatus.GENERATING)
    await db_session.commit()

    async def failing_generate_text(system_prompt: str, user_prompt: str) -> str:
        raise ClaudeGenerationError("boom")

    monkeypatch.setattr(generation_service, "generate_text", failing_generate_text)
    await generation_service.generate_all_sections(db_session, proposal)
    assert proposal.status == ProposalStatus.GENERATION_FAILED

    # Retry: salesperson triggers generation again.
    result = await generation_service.start_generation(db_session, proposal)
    assert result.status == ProposalStatus.GENERATING

    async def succeeding_generate_text(system_prompt: str, user_prompt: str) -> ClaudeCallResult:
        return _fake_result("Recovered text.")

    monkeypatch.setattr(generation_service, "generate_text", succeeding_generate_text)
    await generation_service.generate_all_sections(db_session, proposal)
    assert proposal.status == ProposalStatus.IN_REVIEW


# ---------------------------------------------------------------------------
# Endpoint-level tests.
# ---------------------------------------------------------------------------

INTAKE_HEADERS = {"X-Webhook-Secret": "dev-webhook-secret"}
AUTH_HEADERS = {"Authorization": "Bearer dev-salesperson-token"}

INTAKE_PAYLOAD = {
    "timestamp": "2026-09-09 15:00:00",
    "respondent_email": "gen-test@example.com",
    "client_name": "Carol",
    "client_email": "carol@example.com",
    "company_name": "Widget Co",
    "date_of_call": "2026-09-08",
    "salesperson_name": "Dave",
    "client_needs_summary": "needs widgets",
    "project_scope": "Build a widget factory",
    "goals_and_objectives": "Ship widgets faster",
    "recommended_services": "Factory automation and staff training",
    "proposed_timeline": "8 weeks",
    "estimated_pricing": "$20,000",
}


@pytest.mark.asyncio
async def test_generate_endpoint_requires_auth(async_client: AsyncClient) -> None:
    fake_id = uuid.uuid4()
    response = await async_client.post(f"/api/v1/proposals/{fake_id}/generate")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_generate_endpoint_404_for_unknown_proposal(async_client: AsyncClient) -> None:
    fake_id = uuid.uuid4()
    response = await async_client.post(
        f"/api/v1/proposals/{fake_id}/generate", headers=AUTH_HEADERS
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_generate_endpoint_happy_path(
    async_client: AsyncClient, monkeypatch
) -> None:
    monkeypatch.setattr(generation_service, "AsyncSessionLocal", TestAsyncSessionLocal)

    async def fake_generate_text(system_prompt: str, user_prompt: str) -> ClaudeCallResult:
        return _fake_result("Generated section text.")

    monkeypatch.setattr(generation_service, "generate_text", fake_generate_text)

    create_resp = await async_client.post(
        "/api/v1/intake", json=INTAKE_PAYLOAD, headers=INTAKE_HEADERS
    )
    assert create_resp.status_code == 201
    proposal_id = create_resp.json()["proposal_id"]

    response = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/generate", headers=AUTH_HEADERS
    )
    assert response.status_code == 202

    # Background task runs in-process under the test ASGI transport, so by
    # the time the response is back the job has already completed.
    detail_resp = await async_client.get(
        f"/api/v1/proposals/{proposal_id}", headers=AUTH_HEADERS
    )
    detail = detail_resp.json()
    assert detail["status"] == "IN_REVIEW"
    sections = {s["section_key"]: s for s in detail["sections"]}
    # Introduction is generated too (as of 2026-09-10) — it must not be left
    # as the raw pre-generation placeholder of the client's unedited wording.
    assert sections["introduction"]["content_origin"] == "ai_generated"
    assert sections["introduction"]["content"] == "Generated section text."
    assert sections["deliverables"]["content"] == "Generated section text."
    assert sections["deliverables"]["content_origin"] == "ai_generated"
    assert "Build a widget factory" in sections["proposed_solution"]["content"]
    assert sections["timeline"]["content"] == "8 weeks"
    assert sections["timeline"]["content_origin"] == "template_default"


@pytest.mark.asyncio
async def test_generate_endpoint_allows_rerun_while_in_review(
    async_client: AsyncClient, monkeypatch
) -> None:
    """IN_REVIEW -> GENERATING is a legal edge in the state machine (a
    salesperson re-running full generation while still reviewing) — the
    endpoint must allow a second call, not reject it."""
    monkeypatch.setattr(generation_service, "AsyncSessionLocal", TestAsyncSessionLocal)

    async def fake_generate_text(system_prompt: str, user_prompt: str) -> ClaudeCallResult:
        return _fake_result("text")

    monkeypatch.setattr(generation_service, "generate_text", fake_generate_text)

    payload = INTAKE_PAYLOAD.copy()
    payload["timestamp"] = "2026-09-09 16:00:00"
    payload["respondent_email"] = "gen-test-2@example.com"
    create_resp = await async_client.post(
        "/api/v1/intake", json=payload, headers=INTAKE_HEADERS
    )
    proposal_id = create_resp.json()["proposal_id"]

    first = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/generate", headers=AUTH_HEADERS
    )
    assert first.status_code == 202

    second = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/generate", headers=AUTH_HEADERS
    )
    assert second.status_code == 202


@pytest.mark.asyncio
async def test_generate_endpoint_rejects_wrong_state(
    async_client: AsyncClient, monkeypatch
) -> None:
    """No defined path into GENERATING from PENDING_APPROVAL (docs/system-flow.md
    §3) — the endpoint must reject it with 409, not silently re-run generation."""
    monkeypatch.setattr(generation_service, "AsyncSessionLocal", TestAsyncSessionLocal)

    payload = INTAKE_PAYLOAD.copy()
    payload["timestamp"] = "2026-09-09 16:30:00"
    payload["respondent_email"] = "gen-test-3@example.com"
    create_resp = await async_client.post(
        "/api/v1/intake", json=payload, headers=INTAKE_HEADERS
    )
    proposal_id = uuid.UUID(create_resp.json()["proposal_id"])

    async with TestAsyncSessionLocal() as db:
        proposal = await get_proposal_by_id(db, proposal_id)
        transition_proposal(proposal, ProposalStatus.GENERATING)
        transition_proposal(proposal, ProposalStatus.IN_REVIEW)
        transition_proposal(proposal, ProposalStatus.PENDING_APPROVAL)
        await db.commit()

    response = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/generate", headers=AUTH_HEADERS
    )
    assert response.status_code == 409
