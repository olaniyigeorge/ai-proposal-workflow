import hashlib
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


def compute_intake_key(timestamp: str, respondent_email: str) -> str:
    raw = f"{timestamp.strip().lower()}:{respondent_email.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def process_intake(
    db: AsyncSession, payload: IntakePayload
) -> tuple[Proposal, bool]:
    key = compute_intake_key(payload.timestamp, payload.respondent_email)

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

    sections_defs = [
        (SectionKey.INTRODUCTION, "Introduction", 0, ""),
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
