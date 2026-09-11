"""
Client response recording (unauthenticated) — accept / decline / feedback on a
delivered proposal (week-3 feature).

The public client page POSTs here; there is no JWT. Identity is the proposal_id
in the URL. The first substantive response (ACCEPTED or DECLINED) is recorded;
a second is treated as a no-op (the existing row is returned, not duplicated).
NO_RESPONSE is available for analytics but is not the primary path.

Accepted/declined responses are recorded as ClientResponseRecord rows AND
written to the activity log under PROPOSAL_ACCEPTED / PROPOSAL_DECLINED. The
distinction between won (accepted) and lost (declined) is carried by the
response record and the activity entry — KPIs compute won-rate from response
records, not from a new proposal status value.
"""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_log import ActivityEventType
from app.models.client_feedback import ClientResponseRecord, ClientResponseType
from app.models.proposal import Proposal
from app.services.activity_log_service import record_activity
from app.utils.logger import logger


async def record_client_response(
    db: AsyncSession,
    proposal: Proposal,
    *,
    response_type: ClientResponseType,
    feedback_text: Optional[str] = None,
    client_ip: Optional[str] = None,
    actor: Optional[str] = None,
) -> ClientResponseRecord:
    """Record (or return existing) a client response on a proposal.

    - ACCEPTED/DECLINED: creates a row if none of that type exists for this
      proposal, otherwise returns the existing one (no duplicate rows). Writes
      an activity log entry so the salesperson sees the client decision in the
      proposal timeline and KPIs can treat ACCEPTED as won.
    - NO_RESPONSE: creates a row (idempotent) and writes an activity entry, but
      does not imply any proposal state change — it is an analytics signal only.
    """
    if response_type != ClientResponseType.NO_RESPONSE:
        existing = await _existing_response(db, proposal.id, response_type)
        if existing is not None:
            logger.info(
                "Client response replay: proposal=%s type=%s existing=%s",
                proposal.id, response_type.value, existing.id,
            )
            return existing

    record = ClientResponseRecord(
        proposal_id=proposal.id,
        response_type=response_type,
        feedback_text=feedback_text,
        client_ip=client_ip,
    )
    db.add(record)
    await db.flush()

    event = _activity_event_for(response_type)
    description = _response_description(proposal, response_type, feedback_text)

    record_activity(
        db,
        proposal_id=proposal.id,
        event_type=event,
        description=description,
        actor=actor or "client",
        metadata={
            "response_type": response_type.value,
            "feedback_present": bool(feedback_text),
            "client_ip_present": bool(client_ip),
        },
    )
    await db.commit()
    await db.refresh(record)
    logger.info(
        "Client response recorded proposal=%s type=%s feedback=%s",
        proposal.id, response_type.value, bool(feedback_text),
    )
    return record


async def _existing_response(
    db: AsyncSession, proposal_id: UUID, response_type: ClientResponseType
) -> Optional[ClientResponseRecord]:
    """Return an existing response row of the given type for this proposal, or None."""
    stmt = (
        select(ClientResponseRecord)
        .where(ClientResponseRecord.proposal_id == proposal_id)
        .where(ClientResponseRecord.response_type == response_type)
        .order_by(ClientResponseRecord.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def _activity_event_for(response_type: ClientResponseType) -> ActivityEventType:
    if response_type == ClientResponseType.ACCEPTED:
        return ActivityEventType.CLIENT_ACCEPTED
    if response_type == ClientResponseType.DECLINED:
        return ActivityEventType.CLIENT_DECLINED
    return ActivityEventType.CLIENT_NO_RESPONSE


def _response_description(
    proposal: Proposal, response_type: ClientResponseType, feedback_text: Optional[str]
) -> str:
    label = (
        "accepted"
        if response_type == ClientResponseType.ACCEPTED
        else "declined"
        if response_type == ClientResponseType.DECLINED
        else "opened (no response)"
    )
    base = f"Client {label} proposal"
    if feedback_text:
        snippet = feedback_text[:120].replace("\n", " ")
        return f"{base} — client feedback: {snippet}"
    return base
