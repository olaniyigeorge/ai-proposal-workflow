"""Tests for section-level regeneration (Phase 4): domain guards, prompt
assembly, and the regeneration service's request-time/job-time split. Per
CLAUDE.md testing requirements: sibling sections untouched by a single-section
regenerate, a 4th attempt rejected, a missing instruction rejected, and a
failed Claude call must not burn a cap attempt (docs/edge-cases.md).
"""

import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient

import app.services.regeneration_service as regeneration_service
from app.adapters.claude_client import ClaudeCallResult, ClaudeGenerationError
from app.domain.exceptions import (
    RegenerationCapExceededError,
    RegenerationInstructionRequiredError,
    SectionNotEditableError,
)
from app.domain.generation import build_regeneration_prompt
from app.domain.proposal_transitions import transition_proposal
from app.domain.regeneration import assert_section_is_regenerable
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


def _fake_result(text: str) -> ClaudeCallResult:
    return ClaudeCallResult(
        text=text, model="claude-test", input_tokens=10, output_tokens=20, stop_reason="end_turn"
    )


# ---------------------------------------------------------------------------
# Pure domain tests — no DB, no HTTP.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("section_key", list(SectionKey))
def test_all_sections_are_regenerable(section_key) -> None:
    """As of 2026-09-11 every section has some generated content — Timeline
    and Pricing wrap a generated lead-in around the pinned fact, Next Steps
    is fully generated — so none are excluded here anymore (see
    domain/generation.py's module docstring and docs/edge-cases.md).
    """
    assert_section_is_regenerable(section_key)  # does not raise


def _make_proposal() -> Proposal:
    return Proposal(
        status=ProposalStatus.IN_REVIEW,
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


def test_build_regeneration_prompt_includes_instruction_and_sibling_summaries() -> None:
    proposal = _make_proposal()
    proposal.sections = [
        ProposalSection(
            section_key=SectionKey.PROPOSED_SOLUTION,
            title="Proposed Solution",
            order_index=1,
            content="Scope:\nBuild a widget factory\n\nOld approach text.",
            content_origin=ContentOrigin.AI_GENERATED,
            approval_status=SectionApprovalStatus.PENDING,
            regeneration_count=0,
            version=1,
        ),
        ProposalSection(
            section_key=SectionKey.PRICING,
            title="Pricing",
            order_index=4,
            content="$1",
            content_origin=ContentOrigin.TEMPLATE_DEFAULT,
            approval_status=SectionApprovalStatus.PENDING,
            regeneration_count=0,
            version=1,
        ),
    ]

    prompt = build_regeneration_prompt(
        proposal, SectionKey.PROPOSED_SOLUTION, "make it more formal"
    )

    assert "make it more formal" in prompt
    assert "Pricing: $1" in prompt
    assert "Old approach text." not in prompt  # sibling summary only, not self


def test_build_regeneration_prompt_builds_for_pinned_fact_section() -> None:
    """TIMELINE wraps a generated lead-in around the pinned, verbatim
    `proposed_timeline` — the prompt must ask for the lead-in only and never
    ask the model to restate the date/duration itself.
    """
    proposal = _make_proposal()
    proposal.sections = [
        ProposalSection(section_key=SectionKey.TIMELINE, title="Timeline", order_index=3, content="timeline")
    ]
    prompt = build_regeneration_prompt(proposal, SectionKey.TIMELINE, "shorten it")
    assert "timeline" in prompt.lower()
    assert "do not state" in prompt.lower() or "do not restate" in prompt.lower()


# ---------------------------------------------------------------------------
# Service-level tests — real (in-memory) DB session, Claude call monkeypatched.
# ---------------------------------------------------------------------------


def _make_full_proposal() -> Proposal:
    proposal = _make_proposal()
    sections_defs = [
        (SectionKey.INTRODUCTION, "Introduction", 0, "intro"),
        (SectionKey.PROPOSED_SOLUTION, "Proposed Solution", 1, "Scope:\nBuild a widget factory\n\nOld approach."),
        (SectionKey.DELIVERABLES, "Deliverables", 2, "Old deliverables."),
        (SectionKey.TIMELINE, "Timeline", 3, "timeline"),
        (SectionKey.PRICING, "Pricing", 4, "$1"),
        (SectionKey.NEXT_STEPS, "Next Steps", 5, "1. Review."),
    ]
    proposal.sections = [
        ProposalSection(
            section_key=key,
            title=title,
            order_index=order,
            content=content,
            content_origin=ContentOrigin.AI_GENERATED,
            approval_status=SectionApprovalStatus.APPROVED,
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


async def _persist(db, proposal: Proposal) -> Proposal:
    db.add(proposal)
    await db.flush()
    await db.commit()
    await db.refresh(proposal)
    return await get_proposal_by_id(db, proposal.id)


@pytest.mark.asyncio
async def test_start_regeneration_rejects_missing_instruction(db_session) -> None:
    proposal = await _persist(db_session, _make_full_proposal())
    with pytest.raises(RegenerationInstructionRequiredError):
        await regeneration_service.start_section_regeneration(
            db_session, proposal, SectionKey.PROPOSED_SOLUTION, "   "
        )


@pytest.mark.asyncio
async def test_start_regeneration_allows_timeline_section() -> None:
    """Timeline (a generated lead-in wrapped around the pinned date/duration,
    since 2026-09-11) must be startable like any other generated section —
    it is no longer excluded as a "pinned, nothing to regenerate" section.
    """
    proposal = _make_full_proposal()
    async with TestAsyncSessionLocal() as db:
        proposal = await _persist(db, proposal)
        result = await regeneration_service.start_section_regeneration(
            db, proposal, SectionKey.TIMELINE, "make it shorter"
        )
        assert result is not None


@pytest.mark.asyncio
async def test_start_regeneration_rejects_fourth_attempt(db_session) -> None:
    proposal = _make_full_proposal()
    for section in proposal.sections:
        if section.section_key == SectionKey.PROPOSED_SOLUTION:
            section.regeneration_count = 3
    proposal = await _persist(db_session, proposal)

    with pytest.raises(RegenerationCapExceededError):
        await regeneration_service.start_section_regeneration(
            db_session, proposal, SectionKey.PROPOSED_SOLUTION, "make it shorter"
        )


@pytest.mark.asyncio
async def test_start_regeneration_does_not_mutate_content_or_count(db_session) -> None:
    """The synchronous half of regeneration only validates + (maybe) forces
    the proposal back to IN_REVIEW — content/version/regeneration_count only
    change once the background job actually succeeds.
    """
    proposal = await _persist(db_session, _make_full_proposal())
    before = next(
        s for s in proposal.sections if s.section_key == SectionKey.PROPOSED_SOLUTION
    )
    before_content, before_count, before_version = before.content, before.regeneration_count, before.version

    await regeneration_service.start_section_regeneration(
        db_session, proposal, SectionKey.PROPOSED_SOLUTION, "make it more formal"
    )

    after = next(
        s for s in proposal.sections if s.section_key == SectionKey.PROPOSED_SOLUTION
    )
    assert after.content == before_content
    assert after.regeneration_count == before_count
    assert after.version == before_version


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status", [ProposalStatus.PENDING_APPROVAL, ProposalStatus.APPROVED]
)
async def test_start_regeneration_while_pending_or_approved_forces_in_review(
    db_session, status
) -> None:
    proposal = _make_full_proposal()
    transition_proposal(proposal, ProposalStatus.PENDING_APPROVAL)
    if status == ProposalStatus.APPROVED:
        transition_proposal(proposal, ProposalStatus.APPROVED)
    proposal = await _persist(db_session, proposal)

    updated = await regeneration_service.start_section_regeneration(
        db_session, proposal, SectionKey.PROPOSED_SOLUTION, "make it more formal"
    )

    assert updated.status == ProposalStatus.IN_REVIEW


@pytest.mark.asyncio
async def test_regeneration_job_success_updates_only_targeted_section(
    db_session, monkeypatch
) -> None:
    proposal = await _persist(db_session, _make_full_proposal())
    proposal_id = proposal.id

    async def fake_generate_text(system_prompt: str, user_prompt: str) -> ClaudeCallResult:
        return _fake_result("Brand new approach text.")

    monkeypatch.setattr(regeneration_service, "generate_text", fake_generate_text)

    await regeneration_service.regenerate_section(
        db_session, proposal, SectionKey.PROPOSED_SOLUTION, "make it more formal"
    )

    by_key = {s.section_key: s for s in proposal.sections}

    target = by_key[SectionKey.PROPOSED_SOLUTION]
    assert target.content == "Scope:\nBuild a widget factory\n\nBrand new approach text."
    assert target.content_origin == ContentOrigin.AI_GENERATED
    assert target.approval_status == SectionApprovalStatus.PENDING
    assert target.version == 2
    assert target.regeneration_count == 1
    assert len(target.regeneration_log) == 1
    assert target.regeneration_log[0]["instruction"] == "make it more formal"
    assert target.regeneration_log[0]["outcome"] == "succeeded"

    for key in (
        SectionKey.INTRODUCTION,
        SectionKey.DELIVERABLES,
        SectionKey.TIMELINE,
        SectionKey.PRICING,
        SectionKey.NEXT_STEPS,
    ):
        sibling = by_key[key]
        assert sibling.approval_status == SectionApprovalStatus.APPROVED
        assert sibling.version == 1
        assert sibling.regeneration_count == 0
        assert sibling.regeneration_log == []


@pytest.mark.asyncio
async def test_regeneration_job_failure_does_not_burn_cap_attempt(
    db_session, monkeypatch
) -> None:
    proposal = await _persist(db_session, _make_full_proposal())
    proposal_id = proposal.id

    async def failing_generate_text(system_prompt: str, user_prompt: str) -> str:
        raise ClaudeGenerationError("rate limited")

    monkeypatch.setattr(regeneration_service, "generate_text", failing_generate_text)

    await regeneration_service.regenerate_section(
        db_session, proposal, SectionKey.PROPOSED_SOLUTION, "make it more formal"
    )

    target = next(
        s for s in proposal.sections if s.section_key == SectionKey.PROPOSED_SOLUTION
    )
    assert target.content == "Scope:\nBuild a widget factory\n\nOld approach."
    assert target.regeneration_count == 0
    assert target.version == 1
    assert len(target.regeneration_log) == 1
    assert target.regeneration_log[0]["outcome"] == "failed"


@pytest.mark.asyncio
async def test_regeneration_job_respects_cap_at_run_time(db_session, monkeypatch) -> None:
    """Even if the synchronous guard passed at request time, the job
    re-checks the cap immediately before calling Claude — covers a
    concurrent regeneration call for the same section completing first
    (docs/edge-cases.md on concurrent writers).
    """
    proposal = _make_full_proposal()
    for section in proposal.sections:
        if section.section_key == SectionKey.DELIVERABLES:
            section.regeneration_count = 3
    proposal = await _persist(db_session, proposal)
    proposal_id = proposal.id

    called = False

    async def fake_generate_text(system_prompt: str, user_prompt: str) -> ClaudeCallResult:
        nonlocal called
        called = True
        return _fake_result("should not be reached")

    monkeypatch.setattr(regeneration_service, "generate_text", fake_generate_text)

    await regeneration_service.regenerate_section(
        db_session, proposal, SectionKey.DELIVERABLES, "make it shorter"
    )

    assert called is False


# ---------------------------------------------------------------------------
# HTTP-level tests
# ---------------------------------------------------------------------------


async def _seed_proposal_via_db() -> uuid.UUID:
    async with TestAsyncSessionLocal() as db:
        proposal = _make_full_proposal()
        db.add(proposal)
        await db.commit()
        await db.refresh(proposal)
        return proposal.id


@pytest.mark.asyncio
async def test_regenerate_endpoint_requires_auth(async_client: AsyncClient) -> None:
    proposal_id = await _seed_proposal_via_db()
    response = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/sections/proposed_solution/regenerate",
        json={"instruction": "make it more formal"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_regenerate_endpoint_accepts_and_schedules_job(
    async_client: AsyncClient, monkeypatch
) -> None:
    # Monkeypatched so the background job never opens a real AsyncSessionLocal/
    # Claude call — running two such live-background-job tests in this file
    # without this hit a pytest-asyncio + asyncpg cross-event-loop error
    # ("attached to a different loop") since the pooled connection from
    # whichever test ran first isn't valid on a later test's own event loop.
    monkeypatch.setattr(regeneration_service, "AsyncSessionLocal", TestAsyncSessionLocal)

    async def fake_generate_text(system_prompt: str, user_prompt: str) -> ClaudeCallResult:
        return _fake_result("Generated text.")

    monkeypatch.setattr(regeneration_service, "generate_text", fake_generate_text)

    proposal_id = await _seed_proposal_via_db()
    response = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/sections/proposed_solution/regenerate",
        json={"instruction": "make it more formal"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 202
    body = response.json()
    # Synchronous response: content unchanged, cap not yet spent.
    section = next(s for s in body["sections"] if s["section_key"] == "proposed_solution")
    assert section["regeneration_count"] == 0


@pytest.mark.asyncio
async def test_regenerate_endpoint_rejects_blank_instruction(
    async_client: AsyncClient,
) -> None:
    proposal_id = await _seed_proposal_via_db()
    response = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/sections/proposed_solution/regenerate",
        json={"instruction": "   "},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_regenerate_endpoint_accepts_timeline_section(
    async_client: AsyncClient, monkeypatch
) -> None:
    """Timeline is a generated-lead-in-plus-pinned-fact section, not an
    excluded one — the endpoint must accept it like any other section.
    Monkeypatches the background job's session/Claude call the same way
    test_generate_endpoint_happy_path does, so this doesn't depend on a real
    Claude/network call or reuse a pooled DB connection across a different
    test's event loop.
    """
    monkeypatch.setattr(regeneration_service, "AsyncSessionLocal", TestAsyncSessionLocal)

    async def fake_generate_text(system_prompt: str, user_prompt: str) -> ClaudeCallResult:
        return _fake_result("Generated lead-in.")

    monkeypatch.setattr(regeneration_service, "generate_text", fake_generate_text)

    proposal_id = await _seed_proposal_via_db()
    response = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/sections/timeline/regenerate",
        json={"instruction": "make it shorter"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 202


@pytest.mark.asyncio
async def test_regenerate_endpoint_rejects_fourth_attempt(
    async_client: AsyncClient,
) -> None:
    async with TestAsyncSessionLocal() as db:
        proposal = _make_full_proposal()
        for section in proposal.sections:
            if section.section_key == SectionKey.DELIVERABLES:
                section.regeneration_count = 3
        db.add(proposal)
        await db.commit()
        await db.refresh(proposal)
        proposal_id = proposal.id

    response = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/sections/deliverables/regenerate",
        json={"instruction": "make it shorter"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_regenerate_endpoint_unknown_proposal_is_404(
    async_client: AsyncClient,
) -> None:
    response = await async_client.post(
        f"/api/v1/proposals/{uuid.uuid4()}/sections/proposed_solution/regenerate",
        json={"instruction": "make it more formal"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 404
