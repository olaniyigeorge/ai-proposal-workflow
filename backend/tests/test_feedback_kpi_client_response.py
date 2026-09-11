"""Tests for salesperson feedback, proposal date-range filtering, business
KPIs, and the unauthenticated client accept/decline/feedback flow
(week-3 feature).
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.models.client_feedback import FeedbackCategory
from app.models.delivery import DeliveryRecord, DeliveryStatus
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
    status: ProposalStatus = ProposalStatus.DRAFT,
    created_at: datetime | None = None,
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
    if created_at is not None:
        proposal.created_at = created_at
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
# Salesperson feedback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_feedback_requires_auth(async_client: AsyncClient) -> None:
    resp = await async_client.post(
        "/api/v1/feedback/feedback",
        json={"category": "BUG", "text": "regenerate button is slow"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_submit_and_list_feedback(async_client: AsyncClient) -> None:
    resp = await async_client.post(
        "/api/v1/feedback/feedback",
        json={"category": "FEATURE_REQUEST", "text": "add bulk approve"},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["category"] == "FEATURE_REQUEST"
    assert body["text"] == "add bulk approve"
    assert body["actor_email"]

    listing = await async_client.get("/api/v1/feedback/feedback", headers=AUTH_HEADERS)
    assert listing.status_code == 200
    assert any(e["text"] == "add bulk approve" for e in listing.json())


@pytest.mark.asyncio
async def test_list_feedback_filters_by_category(async_client: AsyncClient) -> None:
    await async_client.post(
        "/api/v1/feedback/feedback",
        json={"category": "BUG", "text": "bug one"},
        headers=AUTH_HEADERS,
    )
    await async_client.post(
        "/api/v1/feedback/feedback",
        json={"category": "GENERAL", "text": "general one"},
        headers=AUTH_HEADERS,
    )
    resp = await async_client.get(
        "/api/v1/feedback/feedback", params={"category": "BUG"}, headers=AUTH_HEADERS
    )
    assert resp.status_code == 200
    categories = {e["category"] for e in resp.json()}
    assert categories == {"BUG"}


@pytest.mark.asyncio
async def test_feedback_rejects_empty_text(async_client: AsyncClient) -> None:
    resp = await async_client.post(
        "/api/v1/feedback/feedback",
        json={"category": "BUG", "text": ""},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Proposal date-range / status filtering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_proposals_filters_by_date_range(db_session, async_client: AsyncClient) -> None:
    now = datetime.now(timezone.utc)
    old = await _persist(db_session, _make_proposal(created_at=now - timedelta(days=30)))
    recent = await _persist(db_session, _make_proposal(created_at=now - timedelta(days=1)))

    resp = await async_client.get(
        "/api/v1/proposals",
        params={
            "date_from": (now - timedelta(days=5)).isoformat(),
            "date_to": now.isoformat(),
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    ids = {p["id"] for p in resp.json()}
    assert str(recent.id) in ids
    assert str(old.id) not in ids


@pytest.mark.asyncio
async def test_list_proposals_filters_by_status(db_session, async_client: AsyncClient) -> None:
    await _persist(db_session, _make_proposal(status=ProposalStatus.DRAFT))
    reviewed = await _persist(db_session, _make_proposal(status=ProposalStatus.IN_REVIEW))

    resp = await async_client.get(
        "/api/v1/proposals", params={"status": "IN_REVIEW"}, headers=AUTH_HEADERS
    )
    assert resp.status_code == 200
    ids = {p["id"] for p in resp.json()}
    assert str(reviewed.id) in ids
    assert all(p["status"] == "IN_REVIEW" for p in resp.json())


# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kpis_requires_auth(async_client: AsyncClient) -> None:
    resp = await async_client.get("/api/v1/feedback/analytics/kpis")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_kpis_counts_delivered_and_won(db_session, async_client: AsyncClient) -> None:
    proposal = await _persist(db_session, _make_proposal(status=ProposalStatus.DELIVERED))
    db_session.add(
        DeliveryRecord(
            proposal_id=proposal.id,
            status=DeliveryStatus.SENT,
            recipient_email="alice@acme.com",
            subject="Proposal for Acme Corp",
            sent_at=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()

    accept_resp = await async_client.post(
        f"/api/v1/public/proposals/{proposal.id}/response",
        json={"response_type": "ACCEPTED"},
    )
    assert accept_resp.status_code == 200

    kpi_resp = await async_client.get("/api/v1/feedback/analytics/kpis", headers=AUTH_HEADERS)
    assert kpi_resp.status_code == 200
    kpis = kpi_resp.json()
    assert kpis["total_delivered"] == 1
    assert kpis["total_accepted"] == 1
    assert kpis["won_proposals"] == 1
    assert kpis["won_rate_pct"] == 100.0


@pytest.mark.asyncio
async def test_kpis_invalid_date_rejected(async_client: AsyncClient) -> None:
    resp = await async_client.get(
        "/api/v1/feedback/analytics/kpis",
        params={"period_from": "not-a-date"},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Public client accept/decline/feedback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_public_meta_requires_no_auth(db_session, async_client: AsyncClient) -> None:
    proposal = await _persist(db_session, _make_proposal(status=ProposalStatus.DELIVERED))
    resp = await async_client.get(f"/api/v1/public/proposals/{proposal.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["client_name"] == "Alice"
    assert body["company_name"] == "Acme Corp"
    assert "status" not in body


@pytest.mark.asyncio
async def test_public_meta_404_for_unknown_proposal(async_client: AsyncClient) -> None:
    resp = await async_client.get(f"/api/v1/public/proposals/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_response_rejected_before_delivery(db_session, async_client: AsyncClient) -> None:
    proposal = await _persist(db_session, _make_proposal(status=ProposalStatus.DRAFT))
    resp = await async_client.post(
        f"/api/v1/public/proposals/{proposal.id}/response",
        json={"response_type": "ACCEPTED"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_response_accepted_after_delivery_and_is_idempotent(
    db_session, async_client: AsyncClient
) -> None:
    proposal = await _persist(db_session, _make_proposal(status=ProposalStatus.DELIVERED))

    first = await async_client.post(
        f"/api/v1/public/proposals/{proposal.id}/response",
        json={"response_type": "ACCEPTED", "feedback_text": "Looks great, let's move forward!"},
    )
    assert first.status_code == 200
    first_id = first.json()["id"]

    second = await async_client.post(
        f"/api/v1/public/proposals/{proposal.id}/response",
        json={"response_type": "ACCEPTED"},
    )
    assert second.status_code == 200
    assert second.json()["id"] == first_id  # no duplicate row


@pytest.mark.asyncio
async def test_response_declined_does_not_require_feedback(
    db_session, async_client: AsyncClient
) -> None:
    proposal = await _persist(db_session, _make_proposal(status=ProposalStatus.DELIVERED))
    resp = await async_client.post(
        f"/api/v1/public/proposals/{proposal.id}/response",
        json={"response_type": "DECLINED"},
    )
    assert resp.status_code == 200
    assert resp.json()["response_type"] == "DECLINED"


@pytest.mark.asyncio
async def test_response_rejects_unknown_field(db_session, async_client: AsyncClient) -> None:
    proposal = await _persist(db_session, _make_proposal(status=ProposalStatus.DELIVERED))
    resp = await async_client.post(
        f"/api/v1/public/proposals/{proposal.id}/response",
        json={"response_type": "ACCEPTED", "salesperson_name": "hijacked"},
    )
    assert resp.status_code == 422
