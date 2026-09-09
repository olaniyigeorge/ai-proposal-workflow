import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentSalesperson, get_current_salesperson
from app.schemas.proposal import ProposalDetailResponse, ProposalSummaryResponse
from app.services.proposal_service import get_proposal_by_id, list_proposals

router = APIRouter()


@router.get(
    "",
    response_model=List[ProposalSummaryResponse],
    summary="List all proposals (salesperson authenticated)",
)
async def get_proposals(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: CurrentSalesperson = Depends(get_current_salesperson),
) -> List[ProposalSummaryResponse]:
    return await list_proposals(db, skip=skip, limit=limit)


@router.get(
    "/{proposal_id}",
    response_model=ProposalDetailResponse,
    summary="Get proposal details by ID (salesperson authenticated)",
)
async def get_proposal(
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: CurrentSalesperson = Depends(get_current_salesperson),
) -> ProposalDetailResponse:
    proposal = await get_proposal_by_id(db, proposal_id)
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal with ID {proposal_id} not found",
        )
    return proposal
