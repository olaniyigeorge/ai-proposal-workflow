import hashlib
import re
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.proposal import (
    ContentOrigin,
    IntakeSubmission,
    Proposal,
    ProposalSection,
    ProposalStatus,
    SectionApprovalStatus,
    SectionKey,
)
from app.schemas.intake import IntakePayload


def normalize_text(value: str) -> str:
    """Deterministic normalization for idempotency-key inputs.

    Lowercases, trims, collapses internal whitespace, and strips trailing
    sentence punctuation so cosmetic differences (extra spaces, a trailing
    period, re-typed casing) don't produce a different key for what is
    substantively the same submission.
    """
    collapsed = re.sub(r"\s+", " ", value.strip().lower())
    return collapsed.rstrip(".,;:!")


def compute_intake_key(company_name: str, project_scope: str, respondent_email: str) -> str:
    """Idempotency key = hash(company_name + normalized project_scope + respondent_email).

    Deliberately excludes `timestamp`: a duplicate n8n webhook retry and a
    salesperson resubmitting the same form both carry the same
    (company_name, project_scope, respondent_email) but a *different*
    timestamp, so keying on timestamp alone (the original scheme) only
    caught the former, not the latter. See docs/decisions.md #4 and
    docs/edge-cases.md "Duplicate intake beyond webhook retries".
    """
    raw = "|".join(
        [
            normalize_text(company_name),
            normalize_text(project_scope),
            normalize_text(respondent_email),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def process_intake(
    db: AsyncSession, payload: IntakePayload
) -> tuple[Proposal, bool]:
    key = compute_intake_key(
        payload.company_name, payload.project_scope, payload.respondent_email
    )

    stmt = select(IntakeSubmission).where(IntakeSubmission.intake_key == key)
    res = await db.execute(stmt)
    existing_sub = res.scalar_one_or_none()

    if existing_sub is not None:
        prop_stmt = select(Proposal).where(Proposal.id == existing_sub.proposal_id)
        prop_res = await db.execute(prop_stmt)
        existing_prop = prop_res.scalar_one()
        return existing_prop, False

    proposal = Proposal(
        status=ProposalStatus.DRAFT,
        client_name=payload.client_name,
        client_email=payload.client_email,
        company_name=payload.company_name,
        salesperson_name=payload.salesperson_name,
        date_of_call=payload.date_of_call,
        client_needs_summary=payload.client_needs_summary,
        project_scope=payload.project_scope,
        goals_and_objectives=payload.goals_and_objectives,
        recommended_services=payload.recommended_services,
        proposed_timeline=payload.proposed_timeline,
        estimated_pricing=payload.estimated_pricing,
    )
    db.add(proposal)
    await db.flush()

    introduction_content = (
        f"Thank you for taking the time to speak with us. Based on our recent "
        f"conversation, we have put together this customized proposal to help "
        f"{payload.company_name} address the following needs:\n\n"
        f"{payload.client_needs_summary}\n\n"
        f"We are excited about the opportunity to support you and believe "
        f"this solution will help {payload.goals_and_objectives}."
    )

    sections_defs = [
        (SectionKey.INTRODUCTION, "Introduction", 0, introduction_content),
        (
            SectionKey.PROPOSED_SOLUTION,
            "Proposed Solution",
            1,
            f"Scope:\n{payload.project_scope}",
        ),
        (
            SectionKey.DELIVERABLES,
            "Deliverables",
            2,
            f"Services & Deliverables:\n{payload.recommended_services}",
        ),
        (SectionKey.TIMELINE, "Timeline", 3, payload.proposed_timeline),
        (SectionKey.PRICING, "Pricing", 4, payload.estimated_pricing),
        (
            SectionKey.NEXT_STEPS,
            "Next Steps",
            5,
            "1. Review and approve the proposal.\n2. Execute agreement.\n3. Schedule kickoff meeting.",
        ),
    ]

    for key_enum, title, order, content in sections_defs:
        section = ProposalSection(
            proposal_id=proposal.id,
            section_key=key_enum,
            title=title,
            order_index=order,
            content=content,
            content_origin=ContentOrigin.TEMPLATE_DEFAULT,
            approval_status=SectionApprovalStatus.PENDING,
            regeneration_count=0,
            version=1,
        )
        db.add(section)

    intake_sub = IntakeSubmission(
        intake_key=key,
        raw_payload=payload.model_dump(mode="json"),
        proposal_id=proposal.id,
    )
    db.add(intake_sub)

    await db.commit()
    await db.refresh(proposal)

    return proposal, True
