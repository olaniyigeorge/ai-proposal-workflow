"""
Authenticated salesperson feedback + KPI + AI email draft endpoints (week-3
feature).

- POST   /feedback                       -> submit FeedbackEntry (auth)
- GET    /feedback                       -> list FeedbackEntry (auth, optional category filter)
- GET    /proposals                      -> adds server-side filter query params (auth)
- GET    /analytics/kpis                -> KPI summary (auth, optional date window)
- POST   /proposals/{proposal_id}/generate-email-draft -> AI-written delivery email draft (auth)
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentSalesperson, get_current_salesperson
from app.schemas.extended import (
    ClientResponseRequest,
    FeedbackEntryRequest,
    FeedbackEntryResponse,
    KpiSummaryResponse,
    ProposalFilterParams,
)
from app.services.feedback_service import list_feedback, submit_feedback
from app.services.proposal_filter_service import compute_kpis, list_proposals_filtered
from app.services.proposal_service import get_proposal_by_id

router = APIRouter()


@router.post(
    "/feedback",
    response_model=FeedbackEntryResponse,
    summary="Submit salesperson feedback about the system (auth required)",
)
async def post_feedback(
    body: FeedbackEntryRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentSalesperson = Depends(get_current_salesperson),
) -> FeedbackEntryResponse:
    entry = await submit_feedback(db, body, actor_email=current.email)
    return FeedbackEntryResponse.model_validate(entry)


@router.get(
    "/feedback",
    response_model=list[FeedbackEntryResponse],
    summary="List salesperson feedback entries (auth required)",
)
async def get_feedback(
    category: Optional[str] = Query(default=None, description="Optional category filter: BUG, FEATURE_REQUEST, GENERAL"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: CurrentSalesperson = Depends(get_current_salesperson),
) -> list[FeedbackEntryResponse]:
    cat: Optional[str] = category
    entries = await list_feedback(db, category=cat, limit=limit, offset=offset)
    return [FeedbackEntryResponse.model_validate(e) for e in entries]


@router.get(
    "/analytics/kpis",
    response_model=KpiSummaryResponse,
    summary="Business KPIs computed from proposals + delivery + client responses (auth required)",
)
async def get_kpis(
    period_from: Optional[str] = Query(default=None, description="ISO-8601 start of reporting window (inclusive)"),
    period_to: Optional[str] = Query(default=None, description="ISO-8601 end of reporting window (inclusive)"),
    db: AsyncSession = Depends(get_db),
    _: CurrentSalesperson = Depends(get_current_salesperson),
) -> KpiSummaryResponse:
    from datetime import datetime

    def parse_iso(v: Optional[str]) -> Optional[datetime]:
        if not v:
            return None
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid date value: {v}",
            )

    pf = parse_iso(period_from)
    pt = parse_iso(period_to)
    return await compute_kpis(db, period_from=pf, period_to=pt)


@router.post(
    "/proposals/{proposal_id}/generate-email-draft",
    response_model=app.schemas.delivery.DeliveryDraftResponse,
    summary="Generate an AI-written delivery email draft for review (auth required, advisory only)",
)
async def generate_email_draft_endpoint(
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentSalesperson = Depends(get_current_salesperson),
) -> app.schemas.delivery.DeliveryDraftResponse:
    from app.domain.aidraft import generate_email_draft
    from app.services.delivery_service import build_document_link

    proposal = await get_proposal_by_id(db, proposal_id)
    if not proposal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")

    try:
        subject, body = await generate_email_draft(proposal)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Email draft generation failed: {exc}",
        ) from exc

    link = build_document_link(proposal.id)
    body_with_link = body.replace("[PROPOSAL_LINK]", link)

    return app.schemas.delivery.DeliveryDraftResponse(
        subject=subject,
        body=body_with_link,
        recipient_email=proposal.client_email,
    )
