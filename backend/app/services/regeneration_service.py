"""Section-level regeneration (Phase 4): one Claude call for a single
GENERATED_SECTION_KEYS section, gated by the mandatory-instruction + 3-attempt
cap (domain/regeneration.py) and run as a background job — CLAUDE.md: no
external call inline in a request handler.

A failed Claude call leaves the section's prior content/version/origin
completely untouched and does NOT count against the 3-attempt cap — only a
call that actually produced new content spends an attempt (see
docs/edge-cases.md "Failed regeneration must not burn a cap attempt").
"""

import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.claude_client import ClaudeGenerationError, generate_text
from app.core.database import AsyncSessionLocal
from app.domain.content_origin import content_origin_after_regeneration
from app.domain.exceptions import DomainError, SectionNotFoundError
from app.domain.generation import (
    assemble_section_content,
    build_regeneration_prompt,
    build_system_prompt,
    pinned_prefix_for_section,
)
from app.domain.proposal_transitions import assert_section_editable, transition_proposal
from app.domain.regeneration import (
    assert_can_regenerate_section,
    assert_section_is_regenerable,
    regeneration_invalidates_approval,
)
from app.models.activity_log import ActivityEventType
from app.models.claude_call_log import ClaudeCallStatus, ClaudeCallType
from app.models.proposal import Proposal, ProposalSection, ProposalStatus, SectionApprovalStatus, SectionKey
from app.services.activity_log_service import record_activity
from app.services.claude_log_service import record_claude_call
from app.services.proposal_service import get_proposal_by_id
from app.utils.logger import logger


def _find_section(proposal: Proposal, section_key: SectionKey) -> ProposalSection:
    section = next((s for s in proposal.sections if s.section_key == section_key), None)
    if section is None:
        raise SectionNotFoundError(section_key)
    return section


async def start_section_regeneration(
    db: AsyncSession, proposal: Proposal, section_key: SectionKey, instruction: str
) -> Proposal:
    """Validate every regeneration guard synchronously (cheap, no I/O) and
    apply the only state change that must be visible immediately: forcing the
    Proposal back to IN_REVIEW if it was PENDING_APPROVAL/APPROVED (same rule
    as manual edits — docs/decisions.md #9). Does NOT touch the section's
    content, version, or regeneration_count — those only change once the
    Claude call in run_section_regeneration_job actually succeeds, so a
    request that never reaches a completed job (e.g. a server restart before
    the background task runs) never counts as a used attempt.
    """
    section = _find_section(proposal, section_key)
    assert_section_editable(section_key, proposal.status)
    assert_section_is_regenerable(section_key)
    assert_can_regenerate_section(section, instruction)

    if regeneration_invalidates_approval(proposal.status):
        transition_proposal(proposal, ProposalStatus.IN_REVIEW)
        await db.commit()
        await db.refresh(proposal)

    return proposal


async def regenerate_section(
    db: AsyncSession,
    proposal: Proposal,
    section_key: SectionKey,
    instruction: str,
    actor: Optional[str] = None,
) -> None:
    """The actual Claude call + section mutation, given an already-open db
    session and loaded proposal. Split out from run_section_regeneration_job
    so it can be exercised in tests against the test DB session directly
    (mirrors services/generation_service.py's generate_all_sections /
    run_generation_job split) instead of through the job wrapper's own
    AsyncSessionLocal.
    """
    try:
        section = _find_section(proposal, section_key)
    except SectionNotFoundError:
        logger.error(
            "Regeneration job: section %s not found on proposal %s",
            section_key.value,
            proposal.id,
        )
        return

    # Re-validate against state as of job-run time, not request time — it can
    # have moved (e.g. the cap was hit by a concurrent regeneration call for
    # the same section that completed first; see docs/edge-cases.md on
    # concurrent writers).
    try:
        assert_can_regenerate_section(section, instruction)
    except DomainError as exc:
        logger.warning(
            "Regeneration job: guard rejected proposal %s section %s at run time: %s",
            proposal.id,
            section_key.value,
            exc,
        )
        return

    system_prompt = build_system_prompt()
    user_prompt = build_regeneration_prompt(proposal, section_key, instruction)
    attempted_at = datetime.now(timezone.utc).isoformat()
    started_at = time.monotonic()

    try:
        result = await generate_text(system_prompt, user_prompt)
    except ClaudeGenerationError as exc:
        # BACKGROUND_JOB_FAILED: greppable tag (Phase 9 hardening), matching
        # the intake-monitoring pattern in app/main.py.
        logger.warning(
            "BACKGROUND_JOB_FAILED job=regeneration proposal=%s section=%s error=%s",
            proposal.id,
            section_key.value,
            exc,
        )
        section.regeneration_log = [
            *section.regeneration_log,
            {
                "instruction": instruction,
                "attempted_at": attempted_at,
                "outcome": "failed",
                "error": str(exc),
            },
        ]
        await record_claude_call(
            db,
            proposal_id=proposal.id,
            section_key=section_key.value,
            call_type=ClaudeCallType.REGENERATION,
            status=ClaudeCallStatus.FAILED,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            duration_ms=int((time.monotonic() - started_at) * 1000),
            instruction=instruction,
            error_message=str(exc),
        )
        # Deliberately NOT counted against the cap (docs/edge-cases.md "A
        # flaky Claude call must not burn one of the salesperson's 3
        # regeneration attempts") — logged anyway, since a failed call is
        # still a state-relevant event worth an audit trail entry.
        record_activity(
            db,
            proposal_id=proposal.id,
            event_type=ActivityEventType.REGENERATION_FAILED,
            description=f"Regeneration failed for section '{section_key.value}': {exc}",
            actor=actor,
            metadata={"section_key": section_key.value, "instruction": instruction},
        )
        await db.commit()
        return

    await record_claude_call(
        db,
        proposal_id=proposal.id,
        section_key=section_key.value,
        call_type=ClaudeCallType.REGENERATION,
        status=ClaudeCallStatus.SUCCEEDED,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        duration_ms=int((time.monotonic() - started_at) * 1000),
        instruction=instruction,
        model=result.model,
        response_text=result.text,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        stop_reason=result.stop_reason,
    )

    final_content = assemble_section_content(
        section_key, pinned_prefix_for_section(proposal, section_key), result.text
    )

    section.content = final_content
    section.content_origin = content_origin_after_regeneration()
    section.approval_status = SectionApprovalStatus.PENDING
    section.version += 1
    section.regeneration_count += 1
    section.regeneration_log = [
        *section.regeneration_log,
        {
            "instruction": instruction,
            "attempted_at": attempted_at,
            "outcome": "succeeded",
            "resulting_version": section.version,
        },
    ]
    record_activity(
        db,
        proposal_id=proposal.id,
        event_type=ActivityEventType.SECTION_REGENERATED,
        description=f"Section '{section_key.value}' regenerated (version {section.version})",
        actor=actor,
        metadata={
            "section_key": section_key.value,
            "instruction": instruction,
            "version": section.version,
        },
    )
    await db.commit()
    logger.info(
        "Section '%s' regenerated on proposal %s (attempt %s/3)",
        section_key.value,
        proposal.id,
        section.regeneration_count,
    )


async def run_section_regeneration_job(
    proposal_id: uuid.UUID,
    section_key: SectionKey,
    instruction: str,
    actor: Optional[str] = None,
) -> None:
    """Background-task entry point: owns its own DB session since it runs
    outside the request's session scope (FastAPI BackgroundTasks execute
    after the response is sent). `actor` is threaded through from the
    request so the eventual activity-log entry records who asked for it.
    """
    async with AsyncSessionLocal() as db:
        proposal = await get_proposal_by_id(db, proposal_id)
        if proposal is None:
            logger.error("Regeneration job: proposal %s no longer exists", proposal_id)
            return

        await regenerate_section(db, proposal, section_key, instruction, actor)
