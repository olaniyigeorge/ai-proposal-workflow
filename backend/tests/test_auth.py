import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_protected_route_unauthenticated(async_client: AsyncClient) -> None:
    """Verifies that calling the protected route without credentials returns 401."""
    response = await async_client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_protected_route_authenticated(async_client: AsyncClient) -> None:
    """Verifies that an authenticated salesperson can access the protected route."""
    headers = {"Authorization": "Bearer dev-salesperson-token"}
    response = await async_client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "salesperson"
    assert data["user_id"] == "dev-salesperson-uuid"
    assert data["email"] == "salesperson@example.com"


@pytest.mark.asyncio
async def test_protected_route_invalid_token(async_client: AsyncClient) -> None:
    """Verifies that an invalid bearer token returns 401."""
    headers = {"Authorization": "Bearer invalid-token"}
    response = await async_client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 401
