"""Tests for the Team tab's backend: listing accounts, setting your own
display name, and self-claiming an unassigned proposal (2026-09-11,
resolves decisions #20's manual claim step).
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient

import app.core.security as security
from app.models.proposal import (
    ContentOrigin,
    Proposal,
    ProposalSection,
    ProposalStatus,
    SectionApprovalStatus,
    SectionKey,
)
from app.models.salesperson_account import SalespersonAccount, SalespersonAccountStatus
from tests.conftest import TestAsyncSessionLocal

AUTH_HEADERS = {"Authorization": "Bearer dev-salesperson-token"}
REAL_USER_A = {"Authorization": "Bearer fake-jwt-a"}
REAL_USER_B = {"Authorization": "Bearer fake-jwt-b"}

_ORIGINAL_VERIFY_TOKEN = security.verify_token


def _fake_verify_token(token: str) -> dict:
    mapping = {
        "fake-jwt-a": {"sub": "user-a", "email": "alice@example.com"},
        "fake-jwt-b": {"sub": "user-b", "email": "bob@example.com"},
    }
    if token in mapping:
        return mapping[token]
    return _ORIGINAL_VERIFY_TOKEN(token)


@pytest.fixture(autouse=True)
def fake_users(monkeypatch):
    monkeypatch.setattr(security, "verify_token", _fake_verify_token)


async def _approve(supabase_user_id: str) -> None:
    async with TestAsyncSessionLocal() as db:
        from sqlalchemy import select

        result = await db.execute(
            select(SalespersonAccount).where(
                SalespersonAccount.supabase_user_id == supabase_user_id
            )
        )
        account = result.scalar_one()
        account.status = SalespersonAccountStatus.APPROVED
        await db.commit()


def _make_proposal(salesperson_name: str | None = None) -> Proposal:
    proposal = Proposal(
        status=ProposalStatus.IN_REVIEW,
        client_name="Alice",
        client_email="alice@acme.com",
        company_name="Acme Corp",
        salesperson_name=salesperson_name,
        date_of_call="2026-09-08",
        client_needs_summary="needs",
        project_scope="scope",
        goals_and_objectives="goals",
        recommended_services="services",
        proposed_timeline="6 weeks",
        estimated_pricing="$20,000",
    )
    proposal.sections = [
        ProposalSection(
            section_key=SectionKey.INTRODUCTION,
            title="Introduction",
            order_index=0,
            content="x",
            content_origin=ContentOrigin.AI_GENERATED,
            approval_status=SectionApprovalStatus.PENDING,
            regeneration_count=0,
            version=1,
        )
    ]
    return proposal


@pytest.mark.asyncio
async def test_update_display_name_succeeds_once_approved(async_client: AsyncClient) -> None:
    await async_client.get("/api/v1/auth/me", headers=REAL_USER_A)
    await _approve("user-a")

    response = await async_client.patch(
        "/api/v1/auth/me", json={"display_name": "Alice A."}, headers=REAL_USER_A
    )
    assert response.status_code == 200
    assert response.json()["display_name"] == "Alice A."


@pytest.mark.asyncio
async def test_duplicate_display_name_is_rejected(async_client: AsyncClient) -> None:
    await async_client.get("/api/v1/auth/me", headers=REAL_USER_A)
    await _approve("user-a")
    await async_client.get("/api/v1/auth/me", headers=REAL_USER_B)
    await _approve("user-b")

    first = await async_client.patch(
        "/api/v1/auth/me", json={"display_name": "Same Name"}, headers=REAL_USER_A
    )
    assert first.status_code == 200

    second = await async_client.patch(
        "/api/v1/auth/me", json={"display_name": "Same Name"}, headers=REAL_USER_B
    )
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_dev_token_cannot_update_display_name(async_client: AsyncClient) -> None:
    response = await async_client.patch(
        "/api/v1/auth/me", json={"display_name": "Dev"}, headers=AUTH_HEADERS
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_list_accounts_returns_everyone_regardless_of_status(async_client: AsyncClient) -> None:
    await async_client.get("/api/v1/auth/me", headers=REAL_USER_A)  # stays pending

    response = await async_client.get("/api/v1/auth/accounts", headers=AUTH_HEADERS)
    assert response.status_code == 200
    emails = [a["email"] for a in response.json()]
    assert "alice@example.com" in emails


@pytest.mark.asyncio
async def test_claim_requires_display_name_first(async_client: AsyncClient, db_session=None) -> None:
    await async_client.get("/api/v1/auth/me", headers=REAL_USER_A)
    await _approve("user-a")

    async with TestAsyncSessionLocal() as db:
        proposal = _make_proposal(salesperson_name=None)
        db.add(proposal)
        await db.commit()
        proposal_id = proposal.id

    response = await async_client.post(f"/api/v1/proposals/{proposal_id}/claim", headers=REAL_USER_A)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_claim_succeeds_on_unassigned_proposal(async_client: AsyncClient) -> None:
    await async_client.get("/api/v1/auth/me", headers=REAL_USER_A)
    await _approve("user-a")
    await async_client.patch(
        "/api/v1/auth/me", json={"display_name": "Alice Claimer"}, headers=REAL_USER_A
    )

    async with TestAsyncSessionLocal() as db:
        proposal = _make_proposal(salesperson_name=None)
        db.add(proposal)
        await db.commit()
        proposal_id = proposal.id

    response = await async_client.post(f"/api/v1/proposals/{proposal_id}/claim", headers=REAL_USER_A)
    assert response.status_code == 200
    assert response.json()["salesperson_name"] == "Alice Claimer"


@pytest.mark.asyncio
async def test_claim_rejected_when_already_assigned(async_client: AsyncClient) -> None:
    await async_client.get("/api/v1/auth/me", headers=REAL_USER_A)
    await _approve("user-a")
    await async_client.patch(
        "/api/v1/auth/me", json={"display_name": "Alice Claimer 2"}, headers=REAL_USER_A
    )

    async with TestAsyncSessionLocal() as db:
        proposal = _make_proposal(salesperson_name="Someone Else")
        db.add(proposal)
        await db.commit()
        proposal_id = proposal.id

    response = await async_client.post(f"/api/v1/proposals/{proposal_id}/claim", headers=REAL_USER_A)
    assert response.status_code == 409
