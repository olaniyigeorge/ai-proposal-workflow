import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.logger import logger
from app.adapters.claude_client import ClaudeGenerationError, generate_text
from app.core.database import AsyncSessionLocal
from app.domain.exceptions import SectionGenerationError
from app.domain.generation import (
    GENERATED_SECTION_KEYS,
    assemble_section_content,
    build_system_prompt,
    build_user_prompt,
)
from app.domain.proposal_transitions import transition_proposal
from app.models.claude_call_log import ClaudeCallStatus, ClaudeCallType
from app.models.proposal import ContentOrigin, Proposal, ProposalStatus
from app.services.claude_log_service import record_claude_call
from app.services.proposal_service import get_proposal_by_id



async def start_generation(db: AsyncSession, proposal: Proposal) -> Proposal:
    """Validate + apply the DRAFT/GENERATION_FAILED -> GENERATING transition
    and commit it. Raises InvalidTransitionError (via transition_proposal) if
    the proposal isn't in a state generation can start from — callers map
    that to a 409.

    Does not run any Claude calls itself — the actual generation work is a
    background job (run_generation_job) scheduled by the caller, so this
    request handler returns immediately per CLAUDE.md's "never inline in a
    request handler" rule.
    """
    transition_proposal(proposal, ProposalStatus.GENERATING)
    await db.commit()
    await db.refresh(proposal)
    return proposal


async def generate_all_sections(db: AsyncSession, proposal: Proposal) -> None:
    """Call Claude for every section that needs generation, then transition
    the Proposal to IN_REVIEW — or to GENERATION_FAILED if any call fails.

    All Claude calls are made and held in memory before anything is written:
    a mid-batch failure must leave every section's prior content, version,
    and origin completely untouched (CLAUDE.md — "never a blank or
    half-written section"), so nothing is applied to the ORM objects until
    every section has succeeded.
    """
    sections_by_key = {s.section_key: s for s in proposal.sections}

    generated: dict[str, str] = {}
    try:
        for section_key in GENERATED_SECTION_KEYS:
            section = sections_by_key[section_key]
            system_prompt = build_system_prompt()
            user_prompt = build_user_prompt(proposal, section_key)
            started_at = time.monotonic()
            try:
                result = await generate_text(system_prompt, user_prompt)
            except ClaudeGenerationError as exc:
                await record_claude_call(
                    db,
                    proposal_id=proposal.id,
                    section_key=section_key.value,
                    call_type=ClaudeCallType.FULL_GENERATION,
                    status=ClaudeCallStatus.FAILED,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    duration_ms=int((time.monotonic() - started_at) * 1000),
                    error_message=str(exc),
                )
                raise SectionGenerationError(section_key, str(exc)) from exc

            await record_claude_call(
                db,
                proposal_id=proposal.id,
                section_key=section_key.value,
                call_type=ClaudeCallType.FULL_GENERATION,
                status=ClaudeCallStatus.SUCCEEDED,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                duration_ms=int((time.monotonic() - started_at) * 1000),
                model=result.model,
                response_text=result.text,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                stop_reason=result.stop_reason,
            )
            generated[section_key] = assemble_section_content(
                section_key, section.content, result.text
            )
    except SectionGenerationError as exc:
        logger.warning("Generation failed for proposal %s: %s", proposal.id, exc)
        transition_proposal(proposal, ProposalStatus.GENERATION_FAILED)
        await db.commit()
        return

    for section_key, content in generated.items():
        section = sections_by_key[section_key]
        section.content = content
        section.content_origin = ContentOrigin.AI_GENERATED

    transition_proposal(proposal, ProposalStatus.IN_REVIEW)
    await db.commit()


async def run_generation_job(proposal_id: uuid.UUID) -> None:
    """Background-task entry point: owns its own DB session since it runs
    outside the request's session scope (FastAPI BackgroundTasks execute
    after the response is sent).
    """
    async with AsyncSessionLocal() as db:
        proposal = await get_proposal_by_id(db, proposal_id)
        if proposal is None:
            logger.error("Generation job: proposal %s no longer exists", proposal_id)
            return
        try:
            print("\n ==== GENERATING PROPOSAL ====\n")
            await generate_all_sections(db, proposal)
        except Exception:
            logger.exception(
                "Unexpected error during generation for proposal %s", proposal_id
            )
            await db.rollback()
            proposal = await get_proposal_by_id(db, proposal_id)
            if proposal is not None and proposal.status == ProposalStatus.GENERATING:
                transition_proposal(proposal, ProposalStatus.GENERATION_FAILED)
                await db.commit()
