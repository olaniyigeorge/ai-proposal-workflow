"""
Public (unauthenticated) client-facing endpoints for the delivered-proposal
response flow (week-3 feature).

GET  /client/proposals/{proposal_id}        -> metadata for the Accept/Decline/Feedback page
POST /client/proposals/{proposal_id}/respond -> record client Accept/Decline/Feedback decision
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domain.client_response import (
    ClientResponseError,
    record_client_response,
)
from app.schemas.extended import (
    ClientPageMetaResponse,
    ClientResponseRecordResponse,
    ClientResponseRequest,
)

router = APIRouter()


@router.get(
    "/proposals/{proposal_id}",
    response_model=ClientPageMetaResponse,
    summary="Public client-page metadata used by the unauthenticated Accept/Decline/Feedback page",
)
async def client_page_meta(
    proposal_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ClientPageMetaResponse:
    """Return just enough metadata for the public client page to render without
    any authentication. Does not surface salesperson identity or internal status
    beyond whether the document is downloadable."""
    record = await _fetch_meta(db, proposal_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return ClientPageMetaResponse(
        proposal_id=proposal_id,
        client_name=record.client_name,
        company_name=record.company_name,
        document_ready=record.document_ready,
        document_download_url=record.document_url,
    )


@router.post(
    "/proposals/{proposal_id}/respond",
    response_model=ClientResponseRecordResponse,
    summary="Record a client Accept/Decline/Feedback decision (no auth)",
)
async def client_respond(
    proposal_id: UUID,
    body: ClientResponseRequest,
    db: AsyncSession = Depends(get_db),
) -> ClientResponseRecordResponse:
    """Persist a client decision (accepted / declined / no_response) plus optional
    feedback text, and update the proposal's status to reflect the response.

    Returns 400 if the proposal is unknown or the response cannot be recorded
    (e.g. already responded, not yet ready to respond).
    """
    try:
        record = await record_client_response(db, proposal_id, body)
    except ClientResponseError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return ClientResponseRecordResponse(
        id=record.id,
        proposal_id=record.proposal_id,
        response_type=record.response_type,
        feedback_text=record.feedback_text,
    )


async def _fetch_meta(db: AsyncSession, proposal_id: UUID):
    """Minimal read of proposal + document-artifact to build ClientPageMetaResponse."""
    from app.models.proposal import Proposal  # local import to avoid circular dep at module level
    prop = await db.get(Proposal, proposal_id)
    if prop is None:
        return None
    doc_url = None
    try:
        from app.services.document_service import get_document_url
        doc_url = await get_document_url(db, proposal_id)
    except Exception:
        doc_url = None
    return _MetaRow(
        client_name=prop.client_name,
        company_name=prop.company_name,
        has_doc=doc_url is not None,
        doc_url=doc_url,
    )


class _MetaRow:
    __slots__ = ("client_name", "company_name", "has_doc", "doc_url")

    def __init__(self, client_name, company_name, has_doc, doc_url):
        self.client_name = client_name
        self.company_name = company_name
        self.document_ready = has_doc
        self.document_url = doc_url