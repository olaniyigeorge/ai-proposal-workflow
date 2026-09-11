"""Tests for proposal ownership enforcement (resolved 2026-09-11, see
docs/design-system-redesign-and-ownership-concerns.md §1): claiming is
strict and has no override — once a proposal is claimed, only the owner may
edit/regenerate/approve/generate-document/deliver it. The owner may unclaim
or transfer it to a named colleague; nobody else can.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

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
        result = await db.execute(
            select(SalespersonAccount).where(
                SalespersonAccount.supabase_user_id == supabase_user_id
            )
        )
        account = result.scalar_one()
        account.status = SalespersonAccountStatus.APPROVED
        await db.commit()


async def _account_id(supabase_user_id: str) -> str:
    async with TestAsyncSessionLocal() as db:
        result = await db.execute(
            select(SalespersonAccount).where(
                SalespersonAccount.supabase_user_id == supabase_user_id
            )
        )
        return str(result.scalar_one().id)


async def _setup_approved_user(async_client: AsyncClient, headers: dict, display_name: str) -> str:
    await async_client.get("/api/v1/auth/me", headers=headers)
    sub = "user-a" if headers is REAL_USER_A else "user-b"
    await _approve(sub)
    await async_client.patch("/api/v1/auth/me", json={"display_name": display_name}, headers=headers)
    return await _account_id(sub)


def _make_proposal(
    status: ProposalStatus = ProposalStatus.IN_REVIEW,
    salesperson_name: str | None = None,
    section_approval: SectionApprovalStatus = SectionApprovalStatus.PENDING,
) -> Proposal:
    proposal = Proposal(
        status=status,
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
            approval_status=section_approval,
            regeneration_count=0,
            version=1,
        )
    ]
    return proposal


async def _seed_claimed_proposal(owner_account_id: str, owner_name: str, **kwargs) -> str:
    async with TestAsyncSessionLocal() as db:
        proposal = _make_proposal(salesperson_name=owner_name, **kwargs)
        proposal.salesperson_account_id = uuid.UUID(owner_account_id)
        db.add(proposal)
        await db.commit()
        return str(proposal.id)


@pytest.mark.asyncio
async def test_non_owner_cannot_edit_claimed_proposal(async_client: AsyncClient) -> None:
    owner_id = await _setup_approved_user(async_client, REAL_USER_A, "Alice Owner")
    await _setup_approved_user(async_client, REAL_USER_B, "Bob Bystander")
    proposal_id = await _seed_claimed_proposal(owner_id, "Alice Owner")

    response = await async_client.patch(
        f"/api/v1/proposals/{proposal_id}/sections/introduction",
        json={"content": "hijacked"},
        headers=REAL_USER_B,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_owner_can_edit_own_claimed_proposal(async_client: AsyncClient) -> None:
    owner_id = await _setup_approved_user(async_client, REAL_USER_A, "Alice Owner2")
    proposal_id = await _seed_claimed_proposal(owner_id, "Alice Owner2")

    response = await async_client.patch(
        f"/api/v1/proposals/{proposal_id}/sections/introduction",
        json={"content": "updated by owner"},
        headers=REAL_USER_A,
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_anyone_can_edit_unclaimed_proposal(async_client: AsyncClient) -> None:
    await _setup_approved_user(async_client, REAL_USER_B, "Bob Free")
    async with TestAsyncSessionLocal() as db:
        proposal = _make_proposal(salesperson_name=None)
        db.add(proposal)
        await db.commit()
        proposal_id = str(proposal.id)

    response = await async_client.patch(
        f"/api/v1/proposals/{proposal_id}/sections/introduction",
        json={"content": "anyone can edit unclaimed"},
        headers=REAL_USER_B,
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_non_owner_cannot_approve_section(async_client: AsyncClient) -> None:
    owner_id = await _setup_approved_user(async_client, REAL_USER_A, "Alice ApproveOwner")
    await _setup_approved_user(async_client, REAL_USER_B, "Bob ApproveBystander")
    proposal_id = await _seed_claimed_proposal(owner_id, "Alice ApproveOwner")

    response = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/sections/introduction/approve",
        headers=REAL_USER_B,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_non_owner_cannot_approve_entire_proposal(async_client: AsyncClient) -> None:
    owner_id = await _setup_approved_user(async_client, REAL_USER_A, "Alice WholeOwner")
    await _setup_approved_user(async_client, REAL_USER_B, "Bob WholeBystander")
    proposal_id = await _seed_claimed_proposal(
        owner_id, "Alice WholeOwner", section_approval=SectionApprovalStatus.APPROVED
    )

    response = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/approve", headers=REAL_USER_B
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_non_owner_cannot_start_document_generation(async_client: AsyncClient) -> None:
    owner_id = await _setup_approved_user(async_client, REAL_USER_A, "Alice DocOwner")
    await _setup_approved_user(async_client, REAL_USER_B, "Bob DocBystander")
    proposal_id = await _seed_claimed_proposal(
        owner_id,
        "Alice DocOwner",
        status=ProposalStatus.APPROVED,
        section_approval=SectionApprovalStatus.APPROVED,
    )

    response = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/generate-document", headers=REAL_USER_B
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_non_owner_cannot_start_delivery(async_client: AsyncClient) -> None:
    owner_id = await _setup_approved_user(async_client, REAL_USER_A, "Alice DeliverOwner")
    await _setup_approved_user(async_client, REAL_USER_B, "Bob DeliverBystander")
    proposal_id = await _seed_claimed_proposal(
        owner_id, "Alice DeliverOwner", status=ProposalStatus.DOCUMENT_READY
    )

    response = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/deliver", headers=REAL_USER_B
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_dev_token_cannot_act_on_claimed_proposal(async_client: AsyncClient) -> None:
    owner_id = await _setup_approved_user(async_client, REAL_USER_A, "Alice DevGuard")
    proposal_id = await _seed_claimed_proposal(owner_id, "Alice DevGuard")

    response = await async_client.patch(
        f"/api/v1/proposals/{proposal_id}/sections/introduction",
        json={"content": "dev token should not own anything"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_owner_can_unclaim(async_client: AsyncClient) -> None:
    owner_id = await _setup_approved_user(async_client, REAL_USER_A, "Alice Unclaimer")
    proposal_id = await _seed_claimed_proposal(owner_id, "Alice Unclaimer")

    response = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/unclaim", headers=REAL_USER_A
    )
    assert response.status_code == 200
    assert response.json()["salesperson_name"] is None
    assert response.json()["salesperson_account_id"] is None


@pytest.mark.asyncio
async def test_non_owner_cannot_unclaim(async_client: AsyncClient) -> None:
    owner_id = await _setup_approved_user(async_client, REAL_USER_A, "Alice Unclaimer2")
    await _setup_approved_user(async_client, REAL_USER_B, "Bob Unclaimer2")
    proposal_id = await _seed_claimed_proposal(owner_id, "Alice Unclaimer2")

    response = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/unclaim", headers=REAL_USER_B
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_unclaim_on_unclaimed_proposal_is_rejected(async_client: AsyncClient) -> None:
    await _setup_approved_user(async_client, REAL_USER_A, "Alice NeverClaimed")
    async with TestAsyncSessionLocal() as db:
        proposal = _make_proposal(salesperson_name=None)
        db.add(proposal)
        await db.commit()
        proposal_id = str(proposal.id)

    response = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/unclaim", headers=REAL_USER_A
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_owner_can_transfer_to_approved_named_colleague(async_client: AsyncClient) -> None:
    owner_id = await _setup_approved_user(async_client, REAL_USER_A, "Alice Transferor")
    target_id = await _setup_approved_user(async_client, REAL_USER_B, "Bob Transferee")
    proposal_id = await _seed_claimed_proposal(owner_id, "Alice Transferor")

    response = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/transfer",
        json={"target_account_id": target_id},
        headers=REAL_USER_A,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["salesperson_name"] == "Bob Transferee"
    assert body["salesperson_account_id"] == target_id

    # Ownership actually moved: the old owner can no longer act on it.
    stale_owner_attempt = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/unclaim", headers=REAL_USER_A
    )
    assert stale_owner_attempt.status_code == 403


@pytest.mark.asyncio
async def test_non_owner_cannot_transfer(async_client: AsyncClient) -> None:
    owner_id = await _setup_approved_user(async_client, REAL_USER_A, "Alice Transferor2")
    target_id = await _setup_approved_user(async_client, REAL_USER_B, "Bob Transferee2")
    proposal_id = await _seed_claimed_proposal(owner_id, "Alice Transferor2")

    response = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/transfer",
        json={"target_account_id": target_id},
        headers=REAL_USER_B,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_transfer_rejected_when_target_has_no_display_name(async_client: AsyncClient) -> None:
    owner_id = await _setup_approved_user(async_client, REAL_USER_A, "Alice Transferor3")
    await async_client.get("/api/v1/auth/me", headers=REAL_USER_B)
    await _approve("user-b")  # approved, but never set a display_name
    target_id = await _account_id("user-b")
    proposal_id = await _seed_claimed_proposal(owner_id, "Alice Transferor3")

    response = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/transfer",
        json={"target_account_id": target_id},
        headers=REAL_USER_A,
    )
    assert response.status_code == 422
