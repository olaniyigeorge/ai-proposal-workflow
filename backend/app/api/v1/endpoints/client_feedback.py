from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.extended import (
    ClientPageMetaResponse,
    ClientResponseRequest,
    ClientResponseRecordResponse,
)
from app.core.database import get_db
from app.services.client_response_service import record_client_response
from app.models.proposal import ProposalStatus

router = APIRouter()

# Public (unauthenticated) client response page endpoints


@router.get(
    "/public/proposals/{proposal_id}",
    response_model=ClientPageMetaResponse,
    summary="Public client page — metadata needed to render the Accept/Decline/Feedback page",
)
async def get_client_page_meta(
    proposal_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ClientPageMetaResponse:
    """No auth. A client clicks the link in the delivery email and lands here;
    the page uses this response to render the company name, salesperson name,
    and the three response buttons."""
    proposal = await db.get(Proposal, proposal_id)
    if proposal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found"
        )
    return ClientPageMetaResponse(
        id=proposal.id,
        company_name=proposal.company_name,
        client_name=proposal.client_name,
        salesperson_name=(proposal.salesperson_name or "Your sales team"),
        status=proposal.status,
    )


@router.post(
    "/public/proposals/{proposal_id}/respond",
    response_model=ClientResponseRecordResponse,
    summary="Record the client's Accept / Decline / Feedback decision",
)
async def submit_client_response(
    proposal_id: UUID,
    body: ClientResponseRequest,
    db: AsyncSession = Depends(get_db),
) -> ClientResponseRecordResponse:
    """No auth. The client page POSTs this when the recipient clicks Accept or
    Decline (with optional feedback text). Both the proposal status is updated
    AND a ClientResponseRecord is persisted (per the chosen default), so the
    won-lead pipeline and the activity trail both see the decision.

    400 is raised (by domain/client_response.py) if the proposal hasn't reached
    a deliverable status (DOCUMENT_READY / DELIVERED), or if the response was
    already recorded for this proposal — clients are told to click only once,
    but the guard still exists."""
    try:
        record = await record_client_response(db, proposal_id, body)
    except ClientResponseError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return ClientResponseRecordResponse(
        id=record.id,
        proposal_id=record.proposal_id,
        response_type=record.response_type,
        feedback_text=record.feedback_text,
        recorded_at=record.recorded_at,
    )
