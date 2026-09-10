"""Document generation (Phase 6): render the branded PDF exactly once, at
APPROVED, upload it to Supabase Storage, and record a DocumentArtifact.
Runs as a background job — CLAUDE.md: no external call (render or upload)
inline in a request handler.

Treated as its own failure domain distinct from approval (architecture.md
§6): a failed render/upload leaves the Proposal's content and approval state
completely untouched and moves it to DOCUMENT_GENERATION_FAILED rather than
leaving it looking like "no document exists yet" — those are operationally
different (a stuck APPROVED proposal needs alerting, a fresh one doesn't).
"""

import asyncio
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.pdf_renderer import PdfRenderError, count_pdf_pages, render_pdf
from app.adapters.storage_client import StorageUploadError, upload_pdf
from app.core.database import AsyncSessionLocal
from app.domain.document import build_document_filename, render_proposal_html
from app.domain.exceptions import DocumentAlreadyGeneratedError
from app.domain.proposal_transitions import transition_proposal
from app.models.document import DocumentArtifact
from app.models.proposal import Proposal, ProposalStatus
from app.services.proposal_service import get_proposal_by_id
from app.utils.logger import logger


def _storage_path_for(proposal: Proposal) -> str:
    # The proposal's UUID is what makes this unique (see build_document_filename's
    # docstring) — the filename segment is purely for readability when a
    # salesperson or client downloads it.
    return f"proposals/{proposal.id}/{build_document_filename(proposal)}"


async def get_document_artifact(
    db: AsyncSession, proposal_id: uuid.UUID
) -> Optional[DocumentArtifact]:
    stmt = select(DocumentArtifact).where(DocumentArtifact.proposal_id == proposal_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def start_document_generation(db: AsyncSession, proposal: Proposal) -> Proposal:
    """Validate + apply the APPROVED -> DOCUMENT_GENERATING transition
    synchronously (cheap, no I/O — matches start_generation/
    start_section_regeneration). Raises InvalidTransitionError (via
    transition_proposal) if the proposal isn't APPROVED, or
    DocumentAlreadyGeneratedError if a DocumentArtifact already exists (the
    DB unique constraint on proposal_id is the last-resort backstop; this is
    the friendlier, checked-first guard).
    """
    existing = await get_document_artifact(db, proposal.id)
    if existing is not None:
        raise DocumentAlreadyGeneratedError(proposal.id)

    transition_proposal(proposal, ProposalStatus.DOCUMENT_GENERATING)
    await db.commit()
    await db.refresh(proposal)
    return proposal


async def generate_document(db: AsyncSession, proposal: Proposal) -> None:
    """The actual render + upload + DocumentArtifact write, given an
    already-open db session and loaded proposal. Split out from
    run_document_generation_job so it can be exercised in tests against the
    test DB session directly (mirrors generation_service.py /
    regeneration_service.py's job-wrapper split).
    """
    html_content = render_proposal_html(proposal)

    try:
        pdf_bytes = await asyncio.to_thread(render_pdf, html_content)
    except PdfRenderError as exc:
        logger.warning("Document render failed for proposal %s: %s", proposal.id, exc)
        transition_proposal(proposal, ProposalStatus.DOCUMENT_GENERATION_FAILED)
        await db.commit()
        return

    page_count = count_pdf_pages(pdf_bytes)
    storage_path = _storage_path_for(proposal)

    try:
        await upload_pdf(storage_path, pdf_bytes)
    except StorageUploadError as exc:
        logger.warning("Document upload failed for proposal %s: %s", proposal.id, exc)
        transition_proposal(proposal, ProposalStatus.DOCUMENT_GENERATION_FAILED)
        await db.commit()
        return

    db.add(
        DocumentArtifact(
            proposal_id=proposal.id,
            storage_path=storage_path,
            file_size_bytes=len(pdf_bytes),
            page_count=page_count,
        )
    )
    transition_proposal(proposal, ProposalStatus.DOCUMENT_READY)
    await db.commit()
    logger.info(
        "Document generated for proposal %s (%s pages, %s bytes)",
        proposal.id,
        page_count,
        len(pdf_bytes),
    )


async def run_document_generation_job(proposal_id: uuid.UUID) -> None:
    """Background-task entry point: owns its own DB session since it runs
    outside the request's session scope (FastAPI BackgroundTasks execute
    after the response is sent).
    """
    async with AsyncSessionLocal() as db:
        proposal = await get_proposal_by_id(db, proposal_id)
        if proposal is None:
            logger.error("Document job: proposal %s no longer exists", proposal_id)
            return

        await generate_document(db, proposal)
