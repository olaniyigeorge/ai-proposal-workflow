"""Tests for Claude call logging (observability): one row per Claude API
call — full-generation and regeneration — with prompts, response, token
usage, and latency, independent of whether the underlying section mutation
succeeds or is later rolled back.
"""

import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient

import app.services.generation_service as generation_service
import app.services.regeneration_service as regeneration_service
from app.adapters.claude_client import ClaudeCallResult, ClaudeGenerationError
from app.domain.proposal_transitions import transition_proposal
from app.models.claude_call_log import ClaudeCallStatus, ClaudeCallType
from app.models.proposal import (
    ContentOrigin,
    Proposal,
    ProposalSection,
    ProposalStatus,
    SectionApprovalStatus,
    SectionKey,
)
from app.services.claude_log_service import list_claude_calls_for_proposal
from app.services.proposal_service import get_proposal_by_id
from tests.conftest import TestAsyncSessionLocal

AUTH_HEADERS = {"Authorization": "Bearer dev-salesperson-token"}


def _fake_result(text: str) -> ClaudeCallResult:
    return ClaudeCallResult(
        text=text, model="claude-test", input_tokens=42, output_tokens=84, stop_reason="end_turn"
    )


def _make_full_proposal() -> Proposal:
    proposal = Proposal(
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
    sections_defs = [
        (SectionKey.INTRODUCTION, "Introduction", 0, "intro"),
        (SectionKey.PROPOSED_SOLUTION, "Proposed Solution", 1, "Scope:\nBuild a widget factory"),
        (SectionKey.DELIVERABLES, "Deliverables", 2, ""),
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


async def _persist(db, proposal: Proposal) -> Proposal:
    db.add(proposal)
    await db.flush()
    await db.commit()
    await db.refresh(proposal)
    return await get_proposal_by_id(db, proposal.id)


@pytest.mark.asyncio
async def test_full_generation_logs_one_call_per_generated_section(
    db_session, monkeypatch
) -> None:
    proposal = await _persist(db_session, _make_full_proposal())
    transition_proposal(proposal, ProposalStatus.GENERATING)
    await db_session.commit()

    async def fake_generate_text(system_prompt: str, user_prompt: str) -> ClaudeCallResult:
        return _fake_result("Generated text.")

    monkeypatch.setattr(generation_service, "generate_text", fake_generate_text)

    await generation_service.generate_all_sections(db_session, proposal)

    logs = await list_claude_calls_for_proposal(db_session, proposal.id)
    assert len(logs) == 3  # introduction + proposed_solution + deliverables
    section_keys = {log.section_key for log in logs}
    assert section_keys == {"introduction", "proposed_solution", "deliverables"}
    for log in logs:
        assert log.call_type == ClaudeCallType.FULL_GENERATION
        assert log.status == ClaudeCallStatus.SUCCEEDED
        assert log.input_tokens == 42
        assert log.output_tokens == 84
        assert log.model == "claude-test"
        assert log.response_text == "Generated text."
        assert log.duration_ms is not None


@pytest.mark.asyncio
async def test_full_generation_failure_still_logs_the_failed_call(
    db_session, monkeypatch
) -> None:
    proposal = await _persist(db_session, _make_full_proposal())
    transition_proposal(proposal, ProposalStatus.GENERATING)
    await db_session.commit()

    async def failing_generate_text(system_prompt: str, user_prompt: str) -> ClaudeCallResult:
        raise ClaudeGenerationError("rate limited")

    monkeypatch.setattr(generation_service, "generate_text", failing_generate_text)

    await generation_service.generate_all_sections(db_session, proposal)

    logs = await list_claude_calls_for_proposal(db_session, proposal.id)
    assert len(logs) == 1  # fails on the first generated section, loop stops
    assert logs[0].status == ClaudeCallStatus.FAILED
    assert logs[0].error_message == "rate limited"
    assert logs[0].response_text is None


@pytest.mark.asyncio
async def test_regeneration_logs_call_with_instruction(db_session, monkeypatch) -> None:
    proposal = await _persist(db_session, _make_full_proposal())

    async def fake_generate_text(system_prompt: str, user_prompt: str) -> ClaudeCallResult:
        return _fake_result("New approach text.")

    monkeypatch.setattr(regeneration_service, "generate_text", fake_generate_text)

    await regeneration_service.regenerate_section(
        db_session, proposal, SectionKey.PROPOSED_SOLUTION, "make it more formal"
    )

    logs = await list_claude_calls_for_proposal(db_session, proposal.id)
    assert len(logs) == 1
    assert logs[0].call_type == ClaudeCallType.REGENERATION
    assert logs[0].instruction == "make it more formal"
    assert logs[0].status == ClaudeCallStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_regeneration_failure_logs_call_without_burning_attempt(
    db_session, monkeypatch
) -> None:
    proposal = await _persist(db_session, _make_full_proposal())

    async def failing_generate_text(system_prompt: str, user_prompt: str) -> ClaudeCallResult:
        raise ClaudeGenerationError("timeout")

    monkeypatch.setattr(regeneration_service, "generate_text", failing_generate_text)

    await regeneration_service.regenerate_section(
        db_session, proposal, SectionKey.DELIVERABLES, "make it shorter"
    )

    logs = await list_claude_calls_for_proposal(db_session, proposal.id)
    assert len(logs) == 1
    assert logs[0].status == ClaudeCallStatus.FAILED
    assert logs[0].error_message == "timeout"


@pytest.mark.asyncio
async def test_claude_calls_endpoint_requires_auth(async_client: AsyncClient) -> None:
    async with TestAsyncSessionLocal() as db:
        proposal = _make_full_proposal()
        db.add(proposal)
        await db.commit()
        await db.refresh(proposal)
        proposal_id = proposal.id

    response = await async_client.get(f"/api/v1/proposals/{proposal_id}/claude-calls")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_claude_calls_endpoint_returns_logged_calls(
    async_client: AsyncClient, monkeypatch
) -> None:
    async with TestAsyncSessionLocal() as db:
        proposal = _make_full_proposal()
        db.add(proposal)
        await db.commit()
        await db.refresh(proposal)
        proposal_id = proposal.id

    async def fake_generate_text(system_prompt: str, user_prompt: str) -> ClaudeCallResult:
        return _fake_result("New text.")

    monkeypatch.setattr(regeneration_service, "generate_text", fake_generate_text)

    async with TestAsyncSessionLocal() as db:
        proposal = await get_proposal_by_id(db, proposal_id)
        await regeneration_service.regenerate_section(
            db, proposal, SectionKey.DELIVERABLES, "make it shorter"
        )

    response = await async_client.get(
        f"/api/v1/proposals/{proposal_id}/claude-calls", headers=AUTH_HEADERS
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["instruction"] == "make it shorter"
    assert body[0]["input_tokens"] == 42


@pytest.mark.asyncio
async def test_claude_calls_endpoint_unknown_proposal_is_404(
    async_client: AsyncClient,
) -> None:
    response = await async_client.get(
        f"/api/v1/proposals/{uuid.uuid4()}/claude-calls", headers=AUTH_HEADERS
    )
    assert response.status_code == 404
