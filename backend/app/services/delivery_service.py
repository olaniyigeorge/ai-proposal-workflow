"""Client delivery (Phase 7): compose the email draft for review, then send
it — email only, PDF linked (never attached), sent as a background job
(CLAUDE.md: no external call inline in a request handler).

The salesperson reviews the composed draft (GET .../delivery-draft) before
ever calling POST .../deliver — there's no auto-send from DOCUMENT_READY,
and the draft-read path never transitions state or sends anything by
itself.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.email_client import EmailSendError, send_email
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.domain.delivery import build_email_body, build_email_html, build_email_subject
from app.domain.exceptions import DocumentNotReadyError
from app.domain.ownership import assert_owns_proposal
from app.domain.proposal_transitions import transition_proposal
from app.models.activity_log import ActivityEventType
from app.models.delivery import DeliveryRecord, DeliveryStatus
from app.models.proposal import Proposal, ProposalStatus
from app.services.activity_log_service import record_activity
from app.services.document_service import get_document_artifact
from app.services.proposal_service import get_proposal_by_id
from app.utils.logger import logger


def build_document_link(proposal_id: uuid.UUID) -> str:
    """The link embedded in the delivery email. Points at this backend's own
    public redirect endpoint (see api/v1/endpoints/public.py), never at a
    raw signed Storage URL directly — a signed URL expires, and the client
    has no way to get a fresh one themselves (no client portal/login,
    CLAUDE.md: "clients never authenticate into this system"). The redirect
    endpoint regenerates a fresh signed URL on every visit, so the emailed
    link never goes stale.
    """
    return f"{settings.PUBLIC_BASE_URL}{settings.API_V1_STR}/public/proposals/{proposal_id}/document"


async def list_delivery_records(
    db: AsyncSession, proposal_id: uuid.UUID
) -> List[DeliveryRecord]:
    stmt = (
        select(DeliveryRecord)
        .where(DeliveryRecord.proposal_id == proposal_id)
        .order_by(DeliveryRecord.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_delivery_draft(db: AsyncSession, proposal: Proposal) -> Tuple[str, str, str]:
    """Pure read: composes and returns (subject, body, recipient_email) for
    the salesperson to review. Never mutates state, never sends anything.
    """
    artifact = await get_document_artifact(db, proposal.id)
    if artifact is None:
        raise DocumentNotReadyError(proposal.id, proposal.status)

    link = build_document_link(proposal.id)
    subject = build_email_subject(proposal)
    body = build_email_body(proposal, link)
    return subject, body, proposal.client_email


async def start_delivery(
    db: AsyncSession, proposal: Proposal, actor_account_id: Optional[uuid.UUID] = None
) -> Proposal:
    """Validate + apply the DOCUMENT_READY/DELIVERY_FAILED -> DELIVERING
    transition synchronously. Raises InvalidTransitionError (via
    transition_proposal) if the proposal isn't in a state delivery can start
    from.
    """
    assert_owns_proposal(proposal, actor_account_id)
    transition_proposal(proposal, ProposalStatus.DELIVERING)
    await db.commit()
    await db.refresh(proposal)
    return proposal


async def deliver_proposal(
    db: AsyncSession, proposal: Proposal, actor: Optional[str] = None
) -> None:
    """The actual send + DeliveryRecord write, given an already-open db
    session and loaded proposal. Split out from run_delivery_job so it can
    be exercised in tests against the test DB session directly (mirrors
    generation_service.py's job-wrapper split).
    """
    artifact = await get_document_artifact(db, proposal.id)
    if artifact is None:
        # BACKGROUND_JOB_FAILED: greppable tag (Phase 9 hardening), matching
        # the intake-monitoring pattern in app/main.py.
        logger.error(
            "BACKGROUND_JOB_FAILED job=delivery proposal=%s error=no_document_to_deliver",
            proposal.id,
        )
        transition_proposal(proposal, ProposalStatus.DELIVERY_FAILED)
        record_activity(
            db,
            proposal_id=proposal.id,
            event_type=ActivityEventType.DELIVERY_FAILED,
            description="Delivery failed: no document to deliver",
            actor=actor,
        )
        await db.commit()
        return

    link = build_document_link(proposal.id)
    subject = build_email_subject(proposal)
    body = build_email_body(proposal, link)
    html_body = build_email_html(proposal, link)

    try:
        await send_email(proposal.client_email, subject, body, html_body)
    except EmailSendError as exc:
        logger.warning(
            "BACKGROUND_JOB_FAILED job=delivery proposal=%s error=%s", proposal.id, exc
        )
        db.add(
            DeliveryRecord(
                proposal_id=proposal.id,
                status=DeliveryStatus.FAILED,
                recipient_email=proposal.client_email,
                subject=subject,
                error_message=str(exc),
            )
        )
        transition_proposal(proposal, ProposalStatus.DELIVERY_FAILED)
        # No recipient email in description/metadata here — an SMTP/provider
        # error message can echo the address back (e.g. "550 rejected:
        # x@y.com"), and per docs/reference/data-retention-policy.md,
        # operational logs should avoid storing PII whenever possible. The
        # detailed error (which DOES need the recipient for someone to act
        # on it) already lives on DeliveryRecord.error_message — this entry
        # only needs to say that it happened, not repeat the PII-bearing text.
        record_activity(
            db,
            proposal_id=proposal.id,
            event_type=ActivityEventType.DELIVERY_FAILED,
            description="Delivery failed — see DeliveryRecord for details",
            actor=actor,
        )
        await db.commit()
        return

    db.add(
        DeliveryRecord(
            proposal_id=proposal.id,
            status=DeliveryStatus.SENT,
            recipient_email=proposal.client_email,
            subject=subject,
            sent_at=datetime.now(timezone.utc),
        )
    )
    transition_proposal(proposal, ProposalStatus.DELIVERED)
    # No client_email here either — same PII-minimization rule as above;
    # DeliveryRecord.recipient_email is the record of who it went to.
    record_activity(
        db,
        proposal_id=proposal.id,
        event_type=ActivityEventType.DELIVERED,
        description="Proposal delivered to client",
        actor=actor,
    )
    await db.commit()
    logger.info("Proposal %s delivered to %s", proposal.id, proposal.client_email)


async def run_delivery_job(proposal_id: uuid.UUID, actor: Optional[str] = None) -> None:
    """Background-task entry point: owns its own DB session since it runs
    outside the request's session scope (FastAPI BackgroundTasks execute
    after the response is sent). `actor` is threaded through from the
    request so the eventual activity-log entry records who asked for it.
    """
    async with AsyncSessionLocal() as db:
        proposal = await get_proposal_by_id(db, proposal_id)
        if proposal is None:
            logger.error("Delivery job: proposal %s no longer exists", proposal_id)
            return

        await deliver_proposal(db, proposal, actor)
