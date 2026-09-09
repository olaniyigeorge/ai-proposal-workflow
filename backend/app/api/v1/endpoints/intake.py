from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.schemas.intake import IntakePayload, IntakeResponse
from app.services.intake_service import process_intake

router = APIRouter()


async def verify_webhook_secret(
    x_webhook_secret: Annotated[Optional[str], Header()] = None,
) -> None:
    if not x_webhook_secret or x_webhook_secret != settings.WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Webhook-Secret header",
        )


@router.post(
    "/intake",
    response_model=IntakeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest canonical proposal intake from n8n webhook",
)
async def ingest_intake(
    payload: IntakePayload,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_webhook_secret),
) -> IntakeResponse:
    proposal, created = await process_intake(db, payload)
    if not created:
        response.status_code = status.HTTP_200_OK
        return IntakeResponse(
            success=True,
            message="Submission already processed (idempotent no-op)",
            proposal_id=proposal.id,
            status="existing",
        )

    return IntakeResponse(
        success=True,
        message="Proposal successfully created from intake",
        proposal_id=proposal.id,
        status="created",
    )
