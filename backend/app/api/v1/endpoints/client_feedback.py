from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.proposal import Proposal, ProposalStatus
from app.schemas.extended import (
    ClientPageMetaResponse,
    ClientResponseRecordResponse,
    ClientResponseRequest,
)
from app.services.client_response_service import record_client_response
from app.services.proposal_service import get_proposal_by_id


_RESPONDABLE_STATUSES = {
    ProposalStatus.DELIVERED,
    ProposalStatus.CLOSED,
}

router = APIRouter()


@router.get(
    "/public/proposals/{proposal_id}",
    response_model=ClientPageMetaResponse,
    summary="Public client page — metadata needed to render the Accept/Decline/Feedback page",
)
async def get_client_page_meta(
    proposal_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ClientPageMetaResponse:
    """No auth. A client clicks the link in the delivery email and lands here."""
    proposal = await db.get(Proposal, proposal_id)

    if proposal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposal not found",
        )

    return ClientPageMetaResponse(
        id=proposal.id,
        company_name=proposal.company_name,
        client_name=proposal.client_name,
        salesperson_name=proposal.salesperson_name or "Your sales team",
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
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ClientResponseRecordResponse:

    proposal = await get_proposal_by_id(db, proposal_id)

    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposal not found",
        )

    if proposal.status not in _RESPONDABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This proposal has not been delivered yet, so it cannot be responded to.",
        )

    # Get the client's IP address
    client_ip = request.client.host if request.client else None

    record = await record_client_response(
        db,
        proposal,
        response_type=body.response_type,
        feedback_text=body.feedback_text,
        client_ip=client_ip,
        actor=None,
    )

    return record