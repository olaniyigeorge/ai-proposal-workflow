"""Tests for client delivery (Phase 7): email composition, the
draft-before-send flow, delivery status tracking, and the public redirect
endpoint. Per CLAUDE.md: delivery is email-only with a link (not an
attachment), the composed draft must be reviewed before sending (no
auto-send from DOCUMENT_READY), and delivery status must be tracked, not
fired-and-forgotten.
"""

import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient

import app.services.delivery_service as delivery_service
from app.adapters.email_client import EmailSendError
from app.core.config import settings
from app.domain.delivery import BRAND_NAME, build_email_body, build_email_html, build_email_subject
from app.domain.exceptions import DocumentNotReadyError, InvalidTransitionError
from app.domain.proposal_transitions import transition_proposal
from app.models.delivery import DeliveryRecord, DeliveryStatus
from app.models.document import DocumentArtifact
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
    status: ProposalStatus = ProposalStatus.DOCUMENT_READY,
    salesperson_name: str | None = "Bob",
) -> Proposal:
    proposal = Proposal(
        status=status,
        client_name="Alice",
        client_email="alice@acme.com",
        company_name="Acme Corp",
        salesperson_name=salesperson_name,
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
            approval_status=SectionApprovalStatus.APPROVED,
            regeneration_count=0,
            version=1,
        )
        for i, key in enumerate(SectionKey)
    ]
    return proposal


# ---------------------------------------------------------------------------
# Pure domain tests — no DB, no HTTP.
# ---------------------------------------------------------------------------


def test_build_email_subject_matches_reference_template() -> None:
    proposal = _make_proposal()
    assert build_email_subject(proposal) == "Proposal for Acme Corp"


def test_build_email_body_includes_client_name_and_link() -> None:
    proposal = _make_proposal()
    body = build_email_body(proposal, "https://example.com/doc")
    assert "Hi Alice," in body
    assert "https://example.com/doc" in body
    assert "Bob" in body
    assert BRAND_NAME in body


def test_build_email_body_signs_as_brand_when_salesperson_unassigned() -> None:
    proposal = _make_proposal(salesperson_name=None)
    body = build_email_body(proposal, "https://example.com/doc")
    assert f"The {BRAND_NAME} Team" in body
    assert "None" not in body


def test_build_email_html_includes_cta_button_and_escapes_content() -> None:
    proposal = _make_proposal()
    proposal.client_name = "Alice <script>alert(1)</script>"
    html_out = build_email_html(proposal, "https://example.com/doc")
    assert "https://example.com/doc" in html_out
    assert "View Your Proposal" in html_out
    assert "<script>alert(1)</script>" not in html_out
    assert "&lt;script&gt;" in html_out


def test_build_email_html_signs_as_brand_when_salesperson_unassigned() -> None:
    proposal = _make_proposal(salesperson_name=None)
    html_out = build_email_html(proposal, "https://example.com/doc")
    assert f"The {BRAND_NAME} Team" in html_out


def test_build_document_link_points_at_public_redirect_endpoint() -> None:
    proposal_id = uuid.uuid4()
    link = delivery_service.build_document_link(proposal_id)
    assert link == f"{settings.PUBLIC_BASE_URL}{settings.API_V1_STR}/public/proposals/{proposal_id}/document"


# ---------------------------------------------------------------------------
# Service-level tests — real (in-memory) DB session.
# ---------------------------------------------------------------------------


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


async def _add_artifact(db, proposal_id: uuid.UUID) -> None:
    db.add(
        DocumentArtifact(
            proposal_id=proposal_id, storage_path="proposals/x/proposal.pdf",
            file_size_bytes=100, page_count=1,
        )
    )
    await db.commit()


@pytest.mark.asyncio
async def test_get_delivery_draft_requires_document_artifact(db_session) -> None:
    proposal = await _persist(db_session, _make_proposal())
    with pytest.raises(DocumentNotReadyError):
        await delivery_service.get_delivery_draft(db_session, proposal)


@pytest.mark.asyncio
async def test_get_delivery_draft_does_not_mutate_state(db_session) -> None:
    proposal = await _persist(db_session, _make_proposal())
    await _add_artifact(db_session, proposal.id)

    subject, body, recipient = await delivery_service.get_delivery_draft(db_session, proposal)

    assert subject == "Proposal for Acme Corp"
    assert recipient == "alice@acme.com"
    assert proposal.status == ProposalStatus.DOCUMENT_READY  # unchanged


@pytest.mark.asyncio
async def test_start_delivery_from_document_ready_succeeds(db_session) -> None:
    proposal = await _persist(db_session, _make_proposal(ProposalStatus.DOCUMENT_READY))
    updated = await delivery_service.start_delivery(db_session, proposal)
    assert updated.status == ProposalStatus.DELIVERING


@pytest.mark.asyncio
async def test_start_delivery_from_delivery_failed_succeeds(db_session) -> None:
    proposal = _make_proposal(ProposalStatus.DOCUMENT_READY)
    transition_proposal(proposal, ProposalStatus.DELIVERING)
    transition_proposal(proposal, ProposalStatus.DELIVERY_FAILED)
    proposal = await _persist(db_session, proposal)

    updated = await delivery_service.start_delivery(db_session, proposal)
    assert updated.status == ProposalStatus.DELIVERING


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [ProposalStatus.IN_REVIEW, ProposalStatus.PENDING_APPROVAL, ProposalStatus.APPROVED],
)
async def test_start_delivery_rejected_outside_document_ready(db_session, status) -> None:
    proposal = _make_proposal(ProposalStatus.DOCUMENT_READY)
    proposal.status = status
    proposal = await _persist(db_session, proposal)

    with pytest.raises(InvalidTransitionError):
        await delivery_service.start_delivery(db_session, proposal)


@pytest.mark.asyncio
async def test_deliver_proposal_success_creates_sent_record_and_transitions(
    db_session, monkeypatch
) -> None:
    proposal = _make_proposal(ProposalStatus.DOCUMENT_READY)
    transition_proposal(proposal, ProposalStatus.DELIVERING)
    proposal = await _persist(db_session, proposal)
    await _add_artifact(db_session, proposal.id)

    sent = {}

    async def fake_send_email(to_email: str, subject: str, body: str, html_body: str | None = None) -> None:
        sent["to"] = to_email
        sent["subject"] = subject
        sent["body"] = body

    monkeypatch.setattr(delivery_service, "send_email", fake_send_email)

    await delivery_service.deliver_proposal(db_session, proposal)

    assert proposal.status == ProposalStatus.DELIVERED
    assert sent["to"] == "alice@acme.com"
    assert sent["subject"] == "Proposal for Acme Corp"

    records = await delivery_service.list_delivery_records(db_session, proposal.id)
    assert len(records) == 1
    assert records[0].status == DeliveryStatus.SENT
    assert records[0].sent_at is not None


@pytest.mark.asyncio
async def test_deliver_proposal_failure_creates_failed_record_and_is_retryable(
    db_session, monkeypatch
) -> None:
    proposal = _make_proposal(ProposalStatus.DOCUMENT_READY)
    transition_proposal(proposal, ProposalStatus.DELIVERING)
    proposal = await _persist(db_session, proposal)
    await _add_artifact(db_session, proposal.id)

    async def failing_send_email(to_email: str, subject: str, body: str, html_body: str | None = None) -> None:
        raise EmailSendError("SMTP connection refused")

    monkeypatch.setattr(delivery_service, "send_email", failing_send_email)

    await delivery_service.deliver_proposal(db_session, proposal)

    assert proposal.status == ProposalStatus.DELIVERY_FAILED
    records = await delivery_service.list_delivery_records(db_session, proposal.id)
    assert len(records) == 1
    assert records[0].status == DeliveryStatus.FAILED
    assert records[0].error_message == "SMTP connection refused"

    # Retry path: DELIVERY_FAILED -> DELIVERING is legal.
    updated = await delivery_service.start_delivery(db_session, proposal)
    assert updated.status == ProposalStatus.DELIVERING


@pytest.mark.asyncio
async def test_deliver_proposal_without_artifact_fails_gracefully(db_session) -> None:
    """Defensive path: DOCUMENT_READY should always imply an artifact
    exists, but the job doesn't assume it — no crash, no email sent.
    """
    proposal = _make_proposal(ProposalStatus.DOCUMENT_READY)
    transition_proposal(proposal, ProposalStatus.DELIVERING)
    proposal = await _persist(db_session, proposal)

    await delivery_service.deliver_proposal(db_session, proposal)

    assert proposal.status == ProposalStatus.DELIVERY_FAILED
    records = await delivery_service.list_delivery_records(db_session, proposal.id)
    assert len(records) == 0


# ---------------------------------------------------------------------------
# HTTP-level tests
# ---------------------------------------------------------------------------


async def _seed_proposal_via_db(
    status: ProposalStatus = ProposalStatus.DOCUMENT_READY, with_artifact: bool = True
) -> uuid.UUID:
    async with TestAsyncSessionLocal() as db:
        proposal = _make_proposal(status)
        db.add(proposal)
        await db.commit()
        await db.refresh(proposal)
        if with_artifact:
            db.add(
                DocumentArtifact(
                    proposal_id=proposal.id, storage_path="proposals/x/proposal.pdf",
                    file_size_bytes=100, page_count=1,
                )
            )
            await db.commit()
        return proposal.id


@pytest.mark.asyncio
async def test_delivery_draft_endpoint_requires_auth(async_client: AsyncClient) -> None:
    proposal_id = await _seed_proposal_via_db()
    response = await async_client.get(f"/api/v1/proposals/{proposal_id}/delivery-draft")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delivery_draft_endpoint_success(async_client: AsyncClient) -> None:
    proposal_id = await _seed_proposal_via_db()
    response = await async_client.get(
        f"/api/v1/proposals/{proposal_id}/delivery-draft", headers=AUTH_HEADERS
    )
    assert response.status_code == 200
    body = response.json()
    assert body["subject"] == "Proposal for Acme Corp"
    assert body["recipient_email"] == "alice@acme.com"
    assert f"{settings.PUBLIC_BASE_URL}" in body["body"]


@pytest.mark.asyncio
async def test_delivery_draft_endpoint_409_before_document_generated(
    async_client: AsyncClient,
) -> None:
    proposal_id = await _seed_proposal_via_db(with_artifact=False)
    response = await async_client.get(
        f"/api/v1/proposals/{proposal_id}/delivery-draft", headers=AUTH_HEADERS
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_deliver_endpoint_rejects_wrong_status(async_client: AsyncClient) -> None:
    proposal_id = await _seed_proposal_via_db(status=ProposalStatus.APPROVED)
    response = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/deliver", headers=AUTH_HEADERS
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_deliver_endpoint_happy_path(async_client: AsyncClient, monkeypatch) -> None:
    monkeypatch.setattr(delivery_service, "AsyncSessionLocal", TestAsyncSessionLocal)

    async def fake_send_email(to_email: str, subject: str, body: str, html_body: str | None = None) -> None:
        pass

    monkeypatch.setattr(delivery_service, "send_email", fake_send_email)

    proposal_id = await _seed_proposal_via_db()

    response = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/deliver", headers=AUTH_HEADERS
    )
    assert response.status_code == 202

    detail_resp = await async_client.get(
        f"/api/v1/proposals/{proposal_id}", headers=AUTH_HEADERS
    )
    assert detail_resp.json()["status"] == "DELIVERED"

    records_resp = await async_client.get(
        f"/api/v1/proposals/{proposal_id}/delivery", headers=AUTH_HEADERS
    )
    assert records_resp.status_code == 200
    records = records_resp.json()
    assert len(records) == 1
    assert records[0]["status"] == "sent"


@pytest.mark.asyncio
async def test_delivery_records_endpoint_requires_auth(async_client: AsyncClient) -> None:
    proposal_id = await _seed_proposal_via_db()
    response = await async_client.get(f"/api/v1/proposals/{proposal_id}/delivery")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_deliver_endpoint_unknown_proposal_is_404(async_client: AsyncClient) -> None:
    response = await async_client.post(
        f"/api/v1/proposals/{uuid.uuid4()}/deliver", headers=AUTH_HEADERS
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Public (unauthenticated) redirect endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_public_document_redirect_404_for_unknown_proposal(
    async_client: AsyncClient,
) -> None:
    response = await async_client.get(
        f"/api/v1/public/proposals/{uuid.uuid4()}/document", follow_redirects=False
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_public_document_redirect_404_before_document_generated(
    async_client: AsyncClient,
) -> None:
    proposal_id = await _seed_proposal_via_db(with_artifact=False)
    response = await async_client.get(
        f"/api/v1/public/proposals/{proposal_id}/document", follow_redirects=False
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_public_document_redirect_requires_no_auth_but_fails_without_real_storage(
    async_client: AsyncClient,
) -> None:
    """Confirms the endpoint is reachable with zero auth headers (the whole
    point — a client recipient is never a system user) and that it degrades
    to a clear 502 rather than crashing when Storage is unreachable (see
    docs/edge-cases.md on the placeholder Supabase config in this env).
    """
    proposal_id = await _seed_proposal_via_db(with_artifact=True)
    response = await async_client.get(
        f"/api/v1/public/proposals/{proposal_id}/document", follow_redirects=False
    )
    assert response.status_code == 502
