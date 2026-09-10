import uuid
from typing import List
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.storage_client import StorageUploadError, get_signed_url
from app.core.database import get_db
from app.core.security import CurrentSalesperson, get_current_salesperson
from app.domain.exceptions import (
    ApprovalGuardError,
    DocumentNotReadyError,
    InvalidTransitionError,
    RegenerationCapExceededError,
    RegenerationInstructionRequiredError,
    SectionNotApprovableError,
    SectionNotEditableError,
    SectionNotFoundError,
    SectionNotRegenerableError,
)
from app.models.proposal import SectionKey
from app.schemas.activity import ActivityLogEntryResponse
from app.schemas.claude_log import ClaudeCallLogResponse
from app.schemas.delivery import DeliveryDraftResponse, DeliveryRecordResponse
from app.schemas.document import DocumentArtifactResponse
from app.schemas.proposal import (
    ProposalDetailResponse,
    ProposalSummaryResponse,
    RejectProposalRequest,
    RequestChangesRequest,
    SectionRegenerateRequest,
    SectionUpdateRequest,
)
from app.services.activity_log_service import list_activity_for_proposal
from app.services.approval_service import (
    approve_entire_proposal,
    approve_section,
    reject_proposal,
    request_changes,
    submit_for_approval,
)
from app.services.claude_log_service import list_claude_calls_for_proposal
from app.services.delivery_service import (
    get_delivery_draft,
    list_delivery_records,
    run_delivery_job,
    start_delivery,
)
from app.services.document_service import (
    get_document_artifact,
    run_document_generation_job,
    start_document_generation,
)
from app.services.generation_service import run_generation_job, start_generation
from app.services.proposal_service import (
    get_proposal_by_id,
    list_proposals,
    update_section_content,
)
from app.services.regeneration_service import (
    run_section_regeneration_job,
    start_section_regeneration,
)

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


@router.post(
    "/{proposal_id}/generate",
    response_model=ProposalDetailResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start full-proposal Claude generation (salesperson authenticated)",
)
async def generate_proposal(
    proposal_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current: CurrentSalesperson = Depends(get_current_salesperson),
) -> ProposalDetailResponse:
    proposal = await get_proposal_by_id(db, proposal_id)
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal with ID {proposal_id} not found",
        )

    try:
        proposal = await start_generation(db, proposal)
    except InvalidTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    # Runs after the response is sent — the actual Claude calls never block
    # this request (CLAUDE.md: external calls run as background jobs, never
    # inline in a request handler).
    background_tasks.add_task(run_generation_job, proposal_id, current.email)

    return proposal


@router.patch(
    "/{proposal_id}/sections/{section_key}",
    response_model=ProposalDetailResponse,
    summary="Edit a section's content (salesperson authenticated)",
)
async def update_section(
    proposal_id: uuid.UUID,
    section_key: SectionKey,
    body: SectionUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentSalesperson = Depends(get_current_salesperson),
) -> ProposalDetailResponse:
    proposal = await get_proposal_by_id(db, proposal_id)
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal with ID {proposal_id} not found",
        )

    try:
        proposal = await update_section_content(
            db, proposal, section_key, body.content, current.email
        )
    except SectionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except SectionNotEditableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    return proposal


@router.post(
    "/{proposal_id}/sections/{section_key}/regenerate",
    response_model=ProposalDetailResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Regenerate a section via Claude (salesperson authenticated)",
)
async def regenerate_section(
    proposal_id: uuid.UUID,
    section_key: SectionKey,
    body: SectionRegenerateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current: CurrentSalesperson = Depends(get_current_salesperson),
) -> ProposalDetailResponse:
    proposal = await get_proposal_by_id(db, proposal_id)
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal with ID {proposal_id} not found",
        )

    try:
        proposal = await start_section_regeneration(
            db, proposal, section_key, body.instruction
        )
    except SectionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except (SectionNotEditableError, SectionNotRegenerableError, RegenerationCapExceededError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except RegenerationInstructionRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    # Runs after the response is sent — the actual Claude call never blocks
    # this request (CLAUDE.md: external calls run as background jobs, never
    # inline in a request handler).
    background_tasks.add_task(
        run_section_regeneration_job, proposal_id, section_key, body.instruction, current.email
    )

    return proposal


@router.get(
    "/{proposal_id}/claude-calls",
    response_model=List[ClaudeCallLogResponse],
    summary="List Claude API calls made for this proposal (salesperson authenticated)",
)
async def get_claude_calls(
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: CurrentSalesperson = Depends(get_current_salesperson),
) -> List[ClaudeCallLogResponse]:
    proposal = await get_proposal_by_id(db, proposal_id)
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal with ID {proposal_id} not found",
        )
    return await list_claude_calls_for_proposal(db, proposal_id)


@router.post(
    "/{proposal_id}/sections/{section_key}/approve",
    response_model=ProposalDetailResponse,
    summary="Approve a single section (salesperson authenticated)",
)
async def approve_section_endpoint(
    proposal_id: uuid.UUID,
    section_key: SectionKey,
    db: AsyncSession = Depends(get_db),
    current: CurrentSalesperson = Depends(get_current_salesperson),
) -> ProposalDetailResponse:
    proposal = await get_proposal_by_id(db, proposal_id)
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal with ID {proposal_id} not found",
        )

    try:
        proposal = await approve_section(db, proposal, section_key, current.email)
    except SectionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except SectionNotApprovableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    return proposal


@router.post(
    "/{proposal_id}/submit-for-approval",
    response_model=ProposalDetailResponse,
    summary="Submit a proposal for final approval (salesperson authenticated)",
)
async def submit_for_approval_endpoint(
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentSalesperson = Depends(get_current_salesperson),
) -> ProposalDetailResponse:
    proposal = await get_proposal_by_id(db, proposal_id)
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal with ID {proposal_id} not found",
        )

    try:
        proposal = await submit_for_approval(db, proposal, current.email)
    except InvalidTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    return proposal


@router.post(
    "/{proposal_id}/approve",
    response_model=ProposalDetailResponse,
    summary="Approve the entire proposal — approves every remaining pending section in one action (salesperson authenticated)",
)
async def approve_proposal_endpoint(
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentSalesperson = Depends(get_current_salesperson),
) -> ProposalDetailResponse:
    proposal = await get_proposal_by_id(db, proposal_id)
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal with ID {proposal_id} not found",
        )

    try:
        proposal = await approve_entire_proposal(db, proposal, current.email)
    except (InvalidTransitionError, ApprovalGuardError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    return proposal


@router.post(
    "/{proposal_id}/request-changes",
    response_model=ProposalDetailResponse,
    summary="Send a pending-approval proposal back to review (salesperson authenticated)",
)
async def request_changes_endpoint(
    proposal_id: uuid.UUID,
    body: RequestChangesRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentSalesperson = Depends(get_current_salesperson),
) -> ProposalDetailResponse:
    proposal = await get_proposal_by_id(db, proposal_id)
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal with ID {proposal_id} not found",
        )

    try:
        proposal = await request_changes(db, proposal, body.reason, current.email)
    except InvalidTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    return proposal


@router.post(
    "/{proposal_id}/reject",
    response_model=ProposalDetailResponse,
    summary="Reject a pending-approval proposal, returning it to review (salesperson authenticated)",
)
async def reject_proposal_endpoint(
    proposal_id: uuid.UUID,
    body: RejectProposalRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentSalesperson = Depends(get_current_salesperson),
) -> ProposalDetailResponse:
    proposal = await get_proposal_by_id(db, proposal_id)
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal with ID {proposal_id} not found",
        )

    try:
        proposal = await reject_proposal(db, proposal, body.reason, current.email)
    except InvalidTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    return proposal


@router.post(
    "/{proposal_id}/generate-document",
    response_model=ProposalDetailResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate the branded PDF — only valid from APPROVED, exactly once (salesperson authenticated)",
)
async def generate_document_endpoint(
    proposal_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current: CurrentSalesperson = Depends(get_current_salesperson),
) -> ProposalDetailResponse:
    proposal = await get_proposal_by_id(db, proposal_id)
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal with ID {proposal_id} not found",
        )

    try:
        proposal = await start_document_generation(db, proposal)
    except InvalidTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    # Runs after the response is sent — rendering + upload never block this
    # request (CLAUDE.md: external calls run as background jobs, never
    # inline in a request handler).
    background_tasks.add_task(run_document_generation_job, proposal_id, current.email)

    return proposal


@router.get(
    "/{proposal_id}/document",
    response_model=DocumentArtifactResponse,
    summary="Get the generated document's metadata + a fresh signed download link (salesperson authenticated)",
)
async def get_document_endpoint(
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: CurrentSalesperson = Depends(get_current_salesperson),
) -> DocumentArtifactResponse:
    proposal = await get_proposal_by_id(db, proposal_id)
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal with ID {proposal_id} not found",
        )

    artifact = await get_document_artifact(db, proposal_id)
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal {proposal_id} has no generated document yet",
        )

    try:
        download_url = await get_signed_url(artifact.storage_path)
    except StorageUploadError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not create a download link: {exc}",
        ) from exc

    return DocumentArtifactResponse(
        id=artifact.id,
        file_size_bytes=artifact.file_size_bytes,
        page_count=artifact.page_count,
        created_at=artifact.created_at,
        download_url=download_url,
    )


@router.get(
    "/{proposal_id}/delivery-draft",
    response_model=DeliveryDraftResponse,
    summary="Preview the composed delivery email before sending (salesperson authenticated)",
)
async def get_delivery_draft_endpoint(
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: CurrentSalesperson = Depends(get_current_salesperson),
) -> DeliveryDraftResponse:
    proposal = await get_proposal_by_id(db, proposal_id)
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal with ID {proposal_id} not found",
        )

    try:
        subject, body, recipient_email = await get_delivery_draft(db, proposal)
    except DocumentNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    return DeliveryDraftResponse(subject=subject, body=body, recipient_email=recipient_email)


@router.post(
    "/{proposal_id}/deliver",
    response_model=ProposalDetailResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send the proposal to the client — only from DOCUMENT_READY/DELIVERY_FAILED (salesperson authenticated)",
)
async def deliver_proposal_endpoint(
    proposal_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current: CurrentSalesperson = Depends(get_current_salesperson),
) -> ProposalDetailResponse:
    proposal = await get_proposal_by_id(db, proposal_id)
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal with ID {proposal_id} not found",
        )

    try:
        proposal = await start_delivery(db, proposal)
    except InvalidTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    # Runs after the response is sent — sending the email never blocks this
    # request (CLAUDE.md: external calls run as background jobs, never
    # inline in a request handler).
    background_tasks.add_task(run_delivery_job, proposal_id, current.email)

    return proposal


@router.get(
    "/{proposal_id}/delivery",
    response_model=List[DeliveryRecordResponse],
    summary="List delivery attempts for this proposal, newest first (salesperson authenticated)",
)
async def get_delivery_records_endpoint(
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: CurrentSalesperson = Depends(get_current_salesperson),
) -> List[DeliveryRecordResponse]:
    proposal = await get_proposal_by_id(db, proposal_id)
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal with ID {proposal_id} not found",
        )
    return await list_delivery_records(db, proposal_id)


@router.get(
    "/{proposal_id}/activity",
    response_model=List[ActivityLogEntryResponse],
    summary="List the audit trail for this proposal, newest first (salesperson authenticated)",
)
async def get_activity_endpoint(
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: CurrentSalesperson = Depends(get_current_salesperson),
) -> List[ActivityLogEntryResponse]:
    proposal = await get_proposal_by_id(db, proposal_id)
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal with ID {proposal_id} not found",
        )
    return await list_activity_for_proposal(db, proposal_id)
