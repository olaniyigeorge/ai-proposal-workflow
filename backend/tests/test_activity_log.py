"""Tests for the activity log / audit trail (Phase 8): CLAUDE.md requires
this for every state-relevant action (created, edited, regenerated, section
approved, proposal approved, rejected, document generated, delivered),
viewable in the dashboard and exportable for compliance (decisions #19).

Covers: the service (record/list/csv), that each service call site actually
writes an entry with the right event type/actor, and endpoint auth.
"""

import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient

import app.services.delivery_service as delivery_service
import app.services.document_service as document_service
import app.services.generation_service as generation_service
import app.services.regeneration_service as regeneration_service
from app.adapters.claude_client import ClaudeCallResult, ClaudeGenerationError
from app.models.activity_log import ActivityEventType
from app.models.document import DocumentArtifact
from app.models.proposal import (
    ContentOrigin,
    Proposal,
    ProposalSection,
    ProposalStatus,
    SectionApprovalStatus,
    SectionKey,
)
from app.services.activity_log_service import (
    build_activity_csv,
    list_activity_for_export,
    list_activity_for_proposal,
    record_activity,
)
from app.services.approval_service import approve_section
from app.services.proposal_service import get_proposal_by_id, update_section_content
from tests.conftest import TestAsyncSessionLocal

AUTH_HEADERS = {"Authorization": "Bearer dev-salesperson-token"}


def _make_proposal(status: ProposalStatus = ProposalStatus.IN_REVIEW) -> Proposal:
    proposal = Proposal(
        status=status,
        client_name="Alice",
        client_email="alice@acme.com",
        company_name="Acme Corp",
        salesperson_name="Bob",
        date_of_call="2026-09-08",
        client_needs_summary="needs",
        project_scope="Build a widget factory",
        goals_and_objectives="goals",
        recommended_services="services",
        proposed_timeline="6 weeks",
        estimated_pricing="$20,000",
    )
    proposal.sections = [
        ProposalSection(
            section_key=key,
            title=key.value,
            order_index=i,
            content="x",
            content_origin=ContentOrigin.AI_GENERATED,
            approval_status=SectionApprovalStatus.PENDING,
            regeneration_count=0,
            version=1,
            regeneration_log=[],
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
# Service-level: record/list/csv
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_activity_does_not_commit_on_its_own(db_session) -> None:
    proposal = await _persist(db_session, _make_proposal())
    proposal_id = proposal.id

    record_activity(
        db_session,
        proposal_id=proposal_id,
        event_type=ActivityEventType.SECTION_EDITED,
        description="test entry",
        actor="test@example.com",
    )
    # Never committed the entry above and rolled back instead.
    await db_session.rollback()

    entries = await list_activity_for_proposal(db_session, proposal_id)
    assert entries == []


@pytest.mark.asyncio
async def test_list_activity_for_proposal_is_newest_first(db_session) -> None:
    proposal = await _persist(db_session, _make_proposal())

    for event_type in (ActivityEventType.SECTION_EDITED, ActivityEventType.SECTION_APPROVED):
        record_activity(
            db_session, proposal_id=proposal.id, event_type=event_type, description="x"
        )
        await db_session.commit()

    entries = await list_activity_for_proposal(db_session, proposal.id)
    assert [e.event_type for e in entries] == [
        ActivityEventType.SECTION_APPROVED,
        ActivityEventType.SECTION_EDITED,
    ]


@pytest.mark.asyncio
async def test_list_activity_for_export_filters_by_proposal_and_is_oldest_first(db_session) -> None:
    proposal_a = await _persist(db_session, _make_proposal())
    proposal_b = await _persist(db_session, _make_proposal())

    record_activity(
        db_session, proposal_id=proposal_a.id, event_type=ActivityEventType.CREATED, description="a1"
    )
    record_activity(
        db_session, proposal_id=proposal_b.id, event_type=ActivityEventType.CREATED, description="b1"
    )
    record_activity(
        db_session, proposal_id=proposal_a.id, event_type=ActivityEventType.SECTION_EDITED, description="a2"
    )
    await db_session.commit()

    scoped = await list_activity_for_export(db_session, proposal_a.id)
    assert [e.description for e in scoped] == ["a1", "a2"]

    everything = await list_activity_for_export(db_session)
    assert len(everything) == 3


@pytest.mark.asyncio
async def test_build_activity_csv_includes_header_and_rows(db_session) -> None:
    proposal = await _persist(db_session, _make_proposal())
    record_activity(
        db_session,
        proposal_id=proposal.id,
        event_type=ActivityEventType.SECTION_EDITED,
        description="edited it",
        actor="bob@example.com",
        metadata={"section_key": "introduction"},
    )
    await db_session.commit()

    entries = await list_activity_for_export(db_session, proposal.id)
    csv_text = build_activity_csv(entries)

    lines = csv_text.strip().splitlines()
    assert lines[0] == "id,proposal_id,event_type,actor,description,metadata,created_at"
    assert "section_edited" in lines[1]
    assert "bob@example.com" in lines[1]
    assert "edited it" in lines[1]


# ---------------------------------------------------------------------------
# Each service call site writes the right entry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_section_content_logs_section_edited(db_session) -> None:
    proposal = await _persist(db_session, _make_proposal())

    await update_section_content(
        db_session, proposal, SectionKey.INTRODUCTION, "new content", actor="bob@example.com"
    )

    entries = await list_activity_for_proposal(db_session, proposal.id)
    assert len(entries) == 1
    assert entries[0].event_type == ActivityEventType.SECTION_EDITED
    assert entries[0].actor == "bob@example.com"
    assert entries[0].event_metadata["section_key"] == SectionKey.INTRODUCTION.value


@pytest.mark.asyncio
async def test_approve_section_logs_section_approved(db_session) -> None:
    proposal = await _persist(db_session, _make_proposal())

    await approve_section(db_session, proposal, SectionKey.INTRODUCTION, actor="bob@example.com")

    entries = await list_activity_for_proposal(db_session, proposal.id)
    assert len(entries) == 1
    assert entries[0].event_type == ActivityEventType.SECTION_APPROVED
    assert entries[0].actor == "bob@example.com"


@pytest.mark.asyncio
async def test_generation_success_logs_generated(db_session, monkeypatch) -> None:
    proposal = await _persist(db_session, _make_proposal(ProposalStatus.GENERATING))

    async def fake_generate_text(system_prompt: str, user_prompt: str) -> ClaudeCallResult:
        return ClaudeCallResult(
            text="generated text", model="claude-test", input_tokens=1, output_tokens=1, stop_reason="end_turn"
        )

    monkeypatch.setattr(generation_service, "generate_text", fake_generate_text)

    await generation_service.generate_all_sections(db_session, proposal, actor="bob@example.com")

    entries = await list_activity_for_proposal(db_session, proposal.id)
    assert [e.event_type for e in entries] == [ActivityEventType.GENERATED]
    assert entries[0].actor == "bob@example.com"


@pytest.mark.asyncio
async def test_generation_failure_logs_generation_failed(db_session, monkeypatch) -> None:
    proposal = await _persist(db_session, _make_proposal(ProposalStatus.GENERATING))

    async def failing_generate_text(system_prompt: str, user_prompt: str) -> ClaudeCallResult:
        raise ClaudeGenerationError("rate limited")

    monkeypatch.setattr(generation_service, "generate_text", failing_generate_text)

    await generation_service.generate_all_sections(db_session, proposal, actor="bob@example.com")

    entries = await list_activity_for_proposal(db_session, proposal.id)
    assert [e.event_type for e in entries] == [ActivityEventType.GENERATION_FAILED]


@pytest.mark.asyncio
async def test_regeneration_success_logs_section_regenerated(db_session, monkeypatch) -> None:
    proposal = await _persist(db_session, _make_proposal())

    async def fake_generate_text(system_prompt: str, user_prompt: str) -> ClaudeCallResult:
        return ClaudeCallResult(
            text="regenerated", model="claude-test", input_tokens=1, output_tokens=1, stop_reason="end_turn"
        )

    monkeypatch.setattr(regeneration_service, "generate_text", fake_generate_text)

    await regeneration_service.regenerate_section(
        db_session, proposal, SectionKey.PROPOSED_SOLUTION, "make it punchier", actor="bob@example.com"
    )

    entries = await list_activity_for_proposal(db_session, proposal.id)
    assert [e.event_type for e in entries] == [ActivityEventType.SECTION_REGENERATED]
    assert entries[0].event_metadata["instruction"] == "make it punchier"


@pytest.mark.asyncio
async def test_regeneration_failure_logs_regeneration_failed_and_does_not_burn_cap(
    db_session, monkeypatch
) -> None:
    proposal = await _persist(db_session, _make_proposal())

    async def failing_generate_text(system_prompt: str, user_prompt: str) -> ClaudeCallResult:
        raise ClaudeGenerationError("timeout")

    monkeypatch.setattr(regeneration_service, "generate_text", failing_generate_text)

    await regeneration_service.regenerate_section(
        db_session, proposal, SectionKey.PROPOSED_SOLUTION, "make it punchier", actor="bob@example.com"
    )

    entries = await list_activity_for_proposal(db_session, proposal.id)
    assert [e.event_type for e in entries] == [ActivityEventType.REGENERATION_FAILED]

    section = next(s for s in proposal.sections if s.section_key == SectionKey.PROPOSED_SOLUTION)
    assert section.regeneration_count == 0


@pytest.mark.asyncio
async def test_document_generation_success_logs_document_generated(db_session, monkeypatch) -> None:
    proposal = await _persist(db_session, _make_proposal(ProposalStatus.DOCUMENT_GENERATING))

    monkeypatch.setattr(document_service, "render_pdf", lambda html: b"%PDF-fake")
    monkeypatch.setattr(document_service, "count_pdf_pages", lambda pdf_bytes: 3)

    async def fake_upload_pdf(path: str, data: bytes) -> None:
        return None

    monkeypatch.setattr(document_service, "upload_pdf", fake_upload_pdf)

    await document_service.generate_document(db_session, proposal, actor="bob@example.com")

    entries = await list_activity_for_proposal(db_session, proposal.id)
    assert [e.event_type for e in entries] == [ActivityEventType.DOCUMENT_GENERATED]
    assert entries[0].event_metadata["page_count"] == 3


@pytest.mark.asyncio
async def test_delivery_success_logs_delivered(db_session, monkeypatch) -> None:
    proposal = await _persist(db_session, _make_proposal(ProposalStatus.DELIVERING))
    db_session.add(
        DocumentArtifact(
            proposal_id=proposal.id, storage_path="proposals/x/proposal.pdf",
            file_size_bytes=100, page_count=1,
        )
    )
    await db_session.commit()

    async def fake_send_email(to_email, subject, body, html_body=None) -> None:
        return None

    monkeypatch.setattr(delivery_service, "send_email", fake_send_email)

    await delivery_service.deliver_proposal(db_session, proposal, actor="bob@example.com")

    entries = await list_activity_for_proposal(db_session, proposal.id)
    assert [e.event_type for e in entries] == [ActivityEventType.DELIVERED]
    # No PII (recipient email) in the activity entry — see
    # docs/reference/data-retention-policy.md; DeliveryRecord holds that.
    assert "alice@acme.com" not in entries[0].description
    assert "recipient_email" not in entries[0].event_metadata


# ---------------------------------------------------------------------------
# Endpoint auth
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_activity_endpoint_requires_auth(async_client: AsyncClient) -> None:
    response = await async_client.get(f"/api/v1/proposals/{uuid.uuid4()}/activity")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_activity_endpoint_returns_404_for_missing_proposal(async_client: AsyncClient) -> None:
    response = await async_client.get(
        f"/api/v1/proposals/{uuid.uuid4()}/activity", headers=AUTH_HEADERS
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_export_activity_endpoint_requires_auth(async_client: AsyncClient) -> None:
    response = await async_client.get("/api/v1/activity/export")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_export_activity_endpoint_returns_csv(async_client: AsyncClient) -> None:
    response = await async_client.get("/api/v1/activity/export", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert response.text.startswith("id,proposal_id,event_type,actor,description,metadata,created_at")


@pytest.mark.asyncio
async def test_intake_creates_activity_entry(async_client: AsyncClient) -> None:
    payload = {
        "timestamp": "2026-09-10T10:00:00Z",
        "respondent_email": "client@acme.com",
        "client_name": "Alice",
        "client_email": "alice@acme.com",
        "company_name": "Acme Corp",
        "date_of_call": "2026-09-10",
        "salesperson_name": None,
        "client_needs_summary": "needs",
        "project_scope": "Build a widget factory",
        "goals_and_objectives": "goals",
        "recommended_services": "services",
        "proposed_timeline": "6 weeks",
        "estimated_pricing": "$20,000",
    }
    from app.core.config import settings

    response = await async_client.post(
        "/api/v1/intake",
        json=payload,
        headers={"X-Webhook-Secret": settings.WEBHOOK_SECRET},
    )
    assert response.status_code == 201
    proposal_id = response.json()["proposal_id"]

    activity_response = await async_client.get(
        f"/api/v1/proposals/{proposal_id}/activity", headers=AUTH_HEADERS
    )
    assert activity_response.status_code == 200
    entries = activity_response.json()
    assert len(entries) == 1
    assert entries[0]["event_type"] == "created"
    assert entries[0]["actor"] is None
