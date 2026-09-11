"""
Public (unauthenticated) client-facing endpoints for the delivered-proposal
response flow (week-3 feature).

GET  /public/proposals/{proposal_id}        -> meta the client page needs to render (no PII beyond client_name/company)
POST /public/proposals/{proposal_id}/response -> record accept/decline/feedback (no auth; idempotency on response type)

These intentionally carry no JWT requirement — clients never authenticate into
this system (CLAUDE.md). The link embedded in the delivery email points here.
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.proposal import Proposal, ProposalStatus
from app.schemas.extended import (
    ClientPageMetaResponse,
    ClientResponseRecordResponse,
    ClientResponseRequest,
)
from app.services.client_response_service import record_client_response
from app.services.document_service import get_document_artifact
from app.services.proposal_service import get_proposal_by_id

# A response is only meaningful once the client has actually been sent
# something — recording ACCEPTED/DECLINED before DELIVERED would let anyone
# guessing/holding a proposal UUID register a response to a proposal that was
# never sent to them.
_RESPONDABLE_STATUSES = {ProposalStatus.DELIVERED, ProposalStatus.CLOSED}

router = APIRouter()


@router.get(
    "/proposals/{proposal_id}",
    response_model=ClientPageMetaResponse,
    summary="Public client page meta — renders the 'view your proposal' page (no auth)",
)
async def public_proposal_meta(
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ClientPageMetaResponse:
    """Return the minimal public-facing info a recipient needs: who the proposal
    is for, the company, and whether the PDF is ready (with a signed link if so).
    No salesperson identity, no internal status enum, no activity log.
    """
    proposal = await get_proposal_by_id(db, proposal_id)
    if not proposal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")

    artifact = await get_document_artifact(db, proposal_id)
    if artifact is not None:
        from app.adapters.storage_client import get_signed_url
        try:
            download_url = await get_signed_url(artifact.storage_path)
        except Exception:
            download_url = None
    else:
        download_url = None

    return ClientPageMetaResponse(
        proposal_id=proposal.id,
        client_name=proposal.client_name,
        company_name=proposal.company_name,
        document_ready=artifact is not None,
        document_download_url=download_url,
    )


@router.post(
    "/proposals/{proposal_id}/response",
    response_model=ClientResponseRecordResponse,
    summary="Record the recipient's response to a delivered proposal (no auth)",
)
async def record_public_response(
    proposal_id: uuid.UUID,
    body: ClientResponseRequest,
    db: AsyncSession = Depends(get_db),
    client_ip: str | None = Query(default=None, include_in_schema=False),
) -> ClientResponseRecordResponse:
    """Record the client's accept/decline/feedback. Idempotent per response type
    per proposal: a second ACCEPTED on the same proposal returns the existing row
    rather than creating a duplicate.

    The client_ip is best-effort from the requesting layer (FastAPI
    ``request.client.host`` when available) and is passed through as a query
    parameter here so this endpoint stays simple and testable.
    """
    proposal = await get_proposal_by_id(db, proposal_id)
    if not proposal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")

    if proposal.status not in _RESPONDABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This proposal has not been delivered yet, so it cannot be responded to.",
        )

    record = await record_client_response(
        db,
        proposal,
        response_type=body.response_type,
        feedback_text=body.feedback_text,
        client_ip=client_ip,
        actor=None,
    )
    return ClientResponseRecordResponse.model_validate(record)
