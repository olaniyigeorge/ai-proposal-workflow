import uuid
import pytest
from httpx import AsyncClient

SAMPLE_PAYLOAD = {
    "timestamp": "2026-09-09 10:15:00",
    "respondent_email": "sales.rep@example.com",
    "client_name": "Alice Johnson",
    "client_email": "alice@acme.com",
    "company_name": "Acme Corp",
    "date_of_call": "2026-09-08",
    "salesperson_name": "Bob Smith",
    "client_needs_summary": "Acme needs an end-to-end automated CRM integration.",
    "project_scope": "Design and deployment of custom CRM connector with automated webhooks.",
    "goals_and_objectives": "Reduce manual entry by 80% and synchronize customer records in real-time.",
    "recommended_services": "CRM API setup, custom middleware, data migration, and staff training.",
    "proposed_timeline": "6 weeks from kickoff",
    "estimated_pricing": "$15,000 USD flat fee",
}


@pytest.mark.asyncio
async def test_intake_missing_secret_header(async_client: AsyncClient) -> None:
    """Rejects webhook if X-Webhook-Secret header is omitted."""
    response = await async_client.post("/api/v1/intake", json=SAMPLE_PAYLOAD)
    assert response.status_code == 401
    assert "Invalid or missing X-Webhook-Secret" in response.json()["detail"]


@pytest.mark.asyncio
async def test_intake_invalid_secret_header(async_client: AsyncClient) -> None:
    """Rejects webhook if X-Webhook-Secret header is wrong."""
    headers = {"X-Webhook-Secret": "wrong-secret"}
    response = await async_client.post(
        "/api/v1/intake", json=SAMPLE_PAYLOAD, headers=headers
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_intake_validation_error_422(async_client: AsyncClient) -> None:
    """Rejects malformed submission with 422 instead of accepting nulls."""
    headers = {"X-Webhook-Secret": "dev-webhook-secret"}
    invalid_payload = SAMPLE_PAYLOAD.copy()
    del invalid_payload["client_name"]
    response = await async_client.post(
        "/api/v1/intake", json=invalid_payload, headers=headers
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_intake_creates_proposal_and_sections(
    async_client: AsyncClient,
) -> None:
    """Valid intake creates a Proposal in DRAFT status with 6 canonical sections."""
    headers = {"X-Webhook-Secret": "dev-webhook-secret"}
    payload = SAMPLE_PAYLOAD.copy()
    payload["timestamp"] = "2026-09-09 11:00:00"
    payload["respondent_email"] = "rep1@example.com"

    response = await async_client.post("/api/v1/intake", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["status"] == "created"
    proposal_id = data["proposal_id"]

    # Verify via salesperson authenticated endpoint
    auth_headers = {"Authorization": "Bearer dev-salesperson-token"}
    detail_resp = await async_client.get(
        f"/api/v1/proposals/{proposal_id}", headers=auth_headers
    )
    assert detail_resp.status_code == 200
    prop = detail_resp.json()
    assert prop["id"] == proposal_id
    assert prop["status"] == "DRAFT"
    assert prop["client_name"] == "Alice Johnson"
    assert prop["company_name"] == "Acme Corp"

    # Verify all 6 sections exist in exact order
    sections = prop["sections"]
    assert len(sections) == 6
    expected_sections = [
        ("introduction", "Introduction", 0),
        ("proposed_solution", "Proposed Solution", 1),
        ("deliverables", "Deliverables", 2),
        ("timeline", "Timeline", 3),
        ("pricing", "Pricing", 4),
        ("next_steps", "Next Steps", 5),
    ]
    for sec, (expected_key, expected_title, expected_order) in zip(
        sections, expected_sections
    ):
        assert sec["section_key"] == expected_key
        assert sec["title"] == expected_title
        assert sec["order_index"] == expected_order
        assert sec["approval_status"] == "pending"
        assert sec["regeneration_count"] == 0

    # Verify pinned facts are captured in sections
    assert "Design and deployment" in sections[1]["content"]
    assert "CRM API setup" in sections[2]["content"]
    assert "6 weeks from kickoff" in sections[3]["content"]
    assert "$15,000 USD flat fee" in sections[4]["content"]


@pytest.mark.asyncio
async def test_intake_idempotency_duplicate(async_client: AsyncClient) -> None:
    """Submitting the exact same payload twice returns 200 with the existing proposal."""
    headers = {"X-Webhook-Secret": "dev-webhook-secret"}
    payload = SAMPLE_PAYLOAD.copy()
    payload["timestamp"] = "2026-09-09 12:00:00"
    payload["respondent_email"] = "rep2@example.com"

    # First attempt: creates proposal
    resp1 = await async_client.post("/api/v1/intake", json=payload, headers=headers)
    assert resp1.status_code == 201
    data1 = resp1.json()
    assert data1["status"] == "created"
    prop_id = data1["proposal_id"]

    # Second attempt with identical payload: returns existing
    resp2 = await async_client.post("/api/v1/intake", json=payload, headers=headers)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["status"] == "existing"
    assert data2["proposal_id"] == prop_id
    assert "already processed" in data2["message"]


@pytest.mark.asyncio
async def test_intake_idempotency_survives_resubmission_with_new_timestamp(
    async_client: AsyncClient,
) -> None:
    """A salesperson resubmitting the same form (new Google Forms Timestamp, same
    company/project_scope/email) must dedupe — not just retries with an identical
    timestamp. This is the gap the timestamp+email key had before it was revised
    (see docs/decisions.md #4)."""
    headers = {"X-Webhook-Secret": "dev-webhook-secret"}
    payload = SAMPLE_PAYLOAD.copy()
    payload["timestamp"] = "2026-09-09 13:00:00"
    payload["respondent_email"] = "rep3@example.com"

    resp1 = await async_client.post("/api/v1/intake", json=payload, headers=headers)
    assert resp1.status_code == 201
    prop_id = resp1.json()["proposal_id"]

    resubmission = payload.copy()
    resubmission["timestamp"] = "2026-09-09 13:05:12"  # different timestamp, same content

    resp2 = await async_client.post(
        "/api/v1/intake", json=resubmission, headers=headers
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["status"] == "existing"
    assert data2["proposal_id"] == prop_id


@pytest.mark.asyncio
async def test_intake_idempotency_ignores_cosmetic_differences(
    async_client: AsyncClient,
) -> None:
    """Extra whitespace/casing/trailing punctuation in company_name or project_scope
    must not fork the idempotency key."""
    headers = {"X-Webhook-Secret": "dev-webhook-secret"}
    payload = SAMPLE_PAYLOAD.copy()
    payload["timestamp"] = "2026-09-09 14:00:00"
    payload["respondent_email"] = "rep4@example.com"

    resp1 = await async_client.post("/api/v1/intake", json=payload, headers=headers)
    assert resp1.status_code == 201
    prop_id = resp1.json()["proposal_id"]

    cosmetic_variant = payload.copy()
    cosmetic_variant["timestamp"] = "2026-09-09 14:10:00"
    cosmetic_variant["company_name"] = "  ACME corp.  "
    cosmetic_variant["project_scope"] = (
        "Design  and deployment of custom CRM connector with automated webhooks."
    )

    resp2 = await async_client.post(
        "/api/v1/intake", json=cosmetic_variant, headers=headers
    )
    assert resp2.status_code == 200
    assert resp2.json()["proposal_id"] == prop_id


@pytest.mark.asyncio
async def test_list_and_get_proposals(async_client: AsyncClient) -> None:
    """Salesperson can list and fetch proposals."""
    headers = {"X-Webhook-Secret": "dev-webhook-secret"}
    create_resp = await async_client.post(
        "/api/v1/intake", json=SAMPLE_PAYLOAD, headers=headers
    )
    assert create_resp.status_code == 201
    prop_id = create_resp.json()["proposal_id"]

    auth_headers = {"Authorization": "Bearer dev-salesperson-token"}
    list_resp = await async_client.get("/api/v1/proposals", headers=auth_headers)
    assert list_resp.status_code == 200
    proposals = list_resp.json()
    assert isinstance(proposals, list)
    assert len(proposals) == 1
    assert proposals[0]["id"] == prop_id

    # Fetch 404 for unknown proposal
    fake_id = str(uuid.uuid4())
    not_found_resp = await async_client.get(
        f"/api/v1/proposals/{fake_id}", headers=auth_headers
    )
    assert not_found_resp.status_code == 404
