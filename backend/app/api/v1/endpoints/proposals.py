import uuid
from typing import List
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentSalesperson, get_current_salesperson
from app.domain.exceptions import (
    ApprovalGuardError,
    InvalidTransitionError,
    RegenerationCapExceededError,
    RegenerationInstructionRequiredError,
    SectionNotApprovableError,
    SectionNotEditableError,
    SectionNotFoundError,
    SectionNotRegenerableError,
)
from app.models.proposal import SectionKey
from app.schemas.claude_log import ClaudeCallLogResponse
from app.schemas.proposal import (
    ProposalDetailResponse,
    ProposalSummaryResponse,
    RejectProposalRequest,
    RequestChangesRequest,
    SectionRegenerateRequest,
    SectionUpdateRequest,
)
from app.services.approval_service import (
    approve_entire_proposal,
    approve_section,
    reject_proposal,
    request_changes,
    submit_for_approval,
)
from app.services.claude_log_service import list_claude_calls_for_proposal
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
    _: CurrentSalesperson = Depends(get_current_salesperson),
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
    background_tasks.add_task(run_generation_job, proposal_id)

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
    _: CurrentSalesperson = Depends(get_current_salesperson),
) -> ProposalDetailResponse:
    proposal = await get_proposal_by_id(db, proposal_id)
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal with ID {proposal_id} not found",
        )

    try:
        proposal = await update_section_content(db, proposal, section_key, body.content)
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
    _: CurrentSalesperson = Depends(get_current_salesperson),
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
        run_section_regeneration_job, proposal_id, section_key, body.instruction
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
    _: CurrentSalesperson = Depends(get_current_salesperson),
) -> ProposalDetailResponse:
    proposal = await get_proposal_by_id(db, proposal_id)
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal with ID {proposal_id} not found",
        )

    try:
        proposal = await approve_section(db, proposal, section_key)
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
    _: CurrentSalesperson = Depends(get_current_salesperson),
) -> ProposalDetailResponse:
    proposal = await get_proposal_by_id(db, proposal_id)
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal with ID {proposal_id} not found",
        )

    try:
        proposal = await submit_for_approval(db, proposal)
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
    _: CurrentSalesperson = Depends(get_current_salesperson),
) -> ProposalDetailResponse:
    proposal = await get_proposal_by_id(db, proposal_id)
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal with ID {proposal_id} not found",
        )

    try:
        proposal = await approve_entire_proposal(db, proposal)
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
    _: CurrentSalesperson = Depends(get_current_salesperson),
) -> ProposalDetailResponse:
    proposal = await get_proposal_by_id(db, proposal_id)
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal with ID {proposal_id} not found",
        )

    try:
        proposal = await request_changes(db, proposal, body.reason)
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
    _: CurrentSalesperson = Depends(get_current_salesperson),
) -> ProposalDetailResponse:
    proposal = await get_proposal_by_id(db, proposal_id)
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal with ID {proposal_id} not found",
        )

    try:
        proposal = await reject_proposal(db, proposal, body.reason)
    except InvalidTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    return proposal
