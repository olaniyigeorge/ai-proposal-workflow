"""Client-facing endpoints — intentionally unauthenticated. CLAUDE.md:
"Clients never authenticate into this system" — a client is either the
form-filler (n8n intake, a separate flow) or a pure email/PDF recipient.
This module is the "pure recipient" side: the one link embedded in the
delivery email.
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.storage_client import StorageUploadError, get_signed_url
from app.core.database import get_db
from app.services.document_service import get_document_artifact
from app.services.proposal_service import get_proposal_by_id

router = APIRouter()


@router.get(
    "/proposals/{proposal_id}/document",
    summary="Redirect to a fresh signed download link for the proposal's PDF — no auth",
)
async def public_document_redirect(
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Regenerates the signed URL on every hit rather than storing one, so
    the link embedded in the delivery email never goes stale no matter how
    long it sits unopened in the client's inbox (see
    services/delivery_service.py::build_document_link and
    docs/edge-cases.md).
    """
    proposal = await get_proposal_by_id(db, proposal_id)
    if not proposal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    artifact = await get_document_artifact(db, proposal_id)
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not available"
        )

    try:
        signed_url = await get_signed_url(artifact.storage_path)
    except StorageUploadError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not generate a download link",
        ) from exc

    return RedirectResponse(url=signed_url, status_code=status.HTTP_302_FOUND)
