"""Tests for the salesperson-account approval gate (2026-09-11): a real
Supabase signUp() creates a working JWT-issuing account instantly, but that
alone must not be enough to use the app — see app/models/salesperson_account.py.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient

import app.core.security as security
from app.models.salesperson_account import SalespersonAccountStatus
from tests.conftest import TestAsyncSessionLocal

AUTH_HEADERS = {"Authorization": "Bearer dev-salesperson-token"}
REAL_USER_HEADERS = {"Authorization": "Bearer fake-real-jwt"}


_ORIGINAL_VERIFY_TOKEN = security.verify_token


def _fake_verify_token_for(user_id: str, email: str):
    def _verify(token: str) -> dict:
        if token == "fake-real-jwt":
            return {"sub": user_id, "email": email}
        return _ORIGINAL_VERIFY_TOKEN(token)

    return _verify


@pytest.fixture(autouse=True)
def fake_real_user(monkeypatch):
    monkeypatch.setattr(
        security, "verify_token", _fake_verify_token_for("real-user-123", "newperson@example.com")
    )


@pytest.mark.asyncio
async def test_new_real_user_is_rejected_as_pending(async_client: AsyncClient) -> None:
    response = await async_client.get("/api/v1/auth/me", headers=REAL_USER_HEADERS)
    assert response.status_code == 403
    assert "pending approval" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_pending_account_row_is_created_on_first_sight(async_client: AsyncClient) -> None:
    await async_client.get("/api/v1/auth/me", headers=REAL_USER_HEADERS)

    async with TestAsyncSessionLocal() as db:
        from sqlalchemy import select

        from app.models.salesperson_account import SalespersonAccount

        result = await db.execute(
            select(SalespersonAccount).where(SalespersonAccount.supabase_user_id == "real-user-123")
        )
        account = result.scalar_one()
        assert account.status == SalespersonAccountStatus.PENDING
        assert account.email == "newperson@example.com"


@pytest.mark.asyncio
async def test_approved_account_can_use_the_app(async_client: AsyncClient) -> None:
    # First request creates the pending row.
    await async_client.get("/api/v1/auth/me", headers=REAL_USER_HEADERS)

    async with TestAsyncSessionLocal() as db:
        from sqlalchemy import select

        from app.models.salesperson_account import SalespersonAccount

        result = await db.execute(
            select(SalespersonAccount).where(SalespersonAccount.supabase_user_id == "real-user-123")
        )
        account = result.scalar_one()
        account.status = SalespersonAccountStatus.APPROVED
        await db.commit()

    response = await async_client.get("/api/v1/auth/me", headers=REAL_USER_HEADERS)
    assert response.status_code == 200
    assert response.json()["email"] == "newperson@example.com"


@pytest.mark.asyncio
async def test_dev_token_bypasses_the_gate_entirely(async_client: AsyncClient) -> None:
    response = await async_client.get("/api/v1/auth/me", headers=AUTH_HEADERS)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_pending_list_and_approve_endpoint(async_client: AsyncClient) -> None:
    await async_client.get("/api/v1/auth/me", headers=REAL_USER_HEADERS)

    pending_resp = await async_client.get("/api/v1/auth/pending", headers=AUTH_HEADERS)
    assert pending_resp.status_code == 200
    pending = pending_resp.json()
    assert len(pending) == 1
    account_id = pending[0]["id"]
    assert pending[0]["status"] == "pending"

    approve_resp = await async_client.post(
        f"/api/v1/auth/pending/{account_id}/approve", headers=AUTH_HEADERS
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"

    # Now the real user's own request succeeds.
    me_resp = await async_client.get("/api/v1/auth/me", headers=REAL_USER_HEADERS)
    assert me_resp.status_code == 200
