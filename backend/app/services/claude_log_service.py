"""Persists one row per Claude API call — prompts, response, token usage,
latency — so the team can see what's actually being sent/spent and use it to
improve prompts over time. Observability only; nothing else in the system
reads this back.
"""

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.claude_call_log import ClaudeCallLog, ClaudeCallStatus, ClaudeCallType


async def record_claude_call(
    db: AsyncSession,
    *,
    proposal_id: uuid.UUID,
    section_key: str,
    call_type: ClaudeCallType,
    status: ClaudeCallStatus,
    system_prompt: str,
    user_prompt: str,
    duration_ms: int,
    instruction: Optional[str] = None,
    model: Optional[str] = None,
    response_text: Optional[str] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    stop_reason: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    """Commits its own row independently of the caller's proposal/section
    mutation — a logging write failing (or the caller's own commit later
    failing) should never be the reason a call doesn't get logged, and vice
    versa. Best-effort but not swallowed: any DB error here propagates, since
    this function is only ever called from within a try/except boundary that
    already treats the Claude call itself as the risky part.
    """
    db.add(
        ClaudeCallLog(
            proposal_id=proposal_id,
            section_key=section_key,
            call_type=call_type,
            status=status,
            instruction=instruction,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_text=response_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            stop_reason=stop_reason,
            duration_ms=duration_ms,
            error_message=error_message,
        )
    )
    await db.commit()


async def list_claude_calls_for_proposal(
    db: AsyncSession, proposal_id: uuid.UUID, limit: int = 100
) -> List[ClaudeCallLog]:
    stmt = (
        select(ClaudeCallLog)
        .where(ClaudeCallLog.proposal_id == proposal_id)
        .order_by(ClaudeCallLog.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
