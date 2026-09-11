"""
AI-assisted delivery email drafting (week-3 feature).

Generates a draft (subject, plain-text body) for the delivery email using the
same Claude model the rest of the system uses (CLAUDE_MODEL, currently Claude
Sonnet 5 — see docs/submission/model-cost-analysis.md). This is advisory only:
it returns a draft the salesperson reviews/edits in the existing delivery-draft
flow, then sends via the existing deliver path. It never auto-sends.

The prompt is assembled from the same canonical-fact inputs the section
generation uses (project context + house tone) plus the client-email template
from docs/reference/client-email-template.md as the structural guide, so the
AI-written draft stays on-brand and on-structure rather than free-rolling a
new message each time.

Cost note (model-cost-analysis.md): this adds one more Claude call per
proposal at most (only when the salesperson explicitly asks for it), on top of
the already-budgeted generation + regeneration calls. At 2,000 proposals/month
and an assumed rough 30% draft-generation rate that is ~600 extra calls/month
— small relative to the existing ~9,000-call budget and the same Sonnet 5
price point.
"""

from app.domain.design_tokens import BRAND_NAME
from app.models.proposal import Proposal
from app.services.claude_log_service import record_claude_call
from app.adapters.claude_client import generate_text, ClaudeGenerationError
from app.utils.logger import logger


def _build_email_draft_system_prompt() -> str:
    return (
        "You are a professional sales assistant for Koya Talent. "
        "Write a short, warm, professional client-facing email that accompanies "
        "a delivered proposal PDF. "
        "Keep it concise — 4 to 8 sentences total. "
        "Use the salesperson's name for the signature if one is given; otherwise "
        f"sign as the {BRAND_NAME} Team. "
        "The email has these parts in this order: "
        "(1) a greeting using the client's name, "
        "(2) a one-to-two sentence thank-you / context line referencing the "
        "conversation, "
        "(3) a line pointing the client to the proposal with the literal marker "
        "[PROPOSAL_LINK] where the link goes (the sending layer replaces this "
        "marker with the actual signed URL — do NOT invent a URL), "
        "(4) one sentence noting what the proposal covers (scope, timeline, "
        "pricing, recommended approach), "
        "(5) an invite to ask questions or request changes, "
        "(6) a brief closing, "
        "(7) a sign-off line with the signature. "
        "Write the subject line separately as the very first line, prefixed with "
        "SUBJECT: so the caller can split it out. "
        "Do not add pleasantries beyond what is written above, do not add "
        "pricing or timeline figures — those come from the proposal, not this "
        "email. "
        "Output plain text only."
    )


def _build_email_draft_user_prompt(proposal: Proposal) -> str:
    signature = proposal.salesperson_name or f"the {BRAND_NAME} Team"
    return (
        f"Client name: {proposal.client_name}\n"
        f"Company: {proposal.company_name}\n"
        f"Salesperson: {signature}\n"
        f"Client needs summary: {proposal.client_needs_summary}\n"
        f"Project scope: {proposal.project_scope}\n"
        f"Goals and objectives: {proposal.goals_and_objectives}\n"
        f"Recommended services: {proposal.recommended_services}\n"
        f"Proposed timeline: {proposal.proposed_timeline}\n"
        f"Estimated pricing: {proposal.estimated_pricing}\n"
        "\nWrite the email now."
    )


async def generate_email_draft(
    proposal: Proposal,
) -> tuple[str, str]:
    """Return (subject, body) for an AI-written delivery email draft.

    Raises ClaudeGenerationError on Claude failure — callers should catch and
    fall back to the human-composed template rather than blocking delivery.
    A failed call still gets a ClaudeCallLog row (status=failed) so the attempt
    is visible in the call log.
    """
    system = _build_email_draft_system_prompt()
    user = _build_email_draft_user_prompt(proposal)

    try:
        result = await generate_text(system_prompt=system, user_prompt=user)
    except ClaudeGenerationError as exc:
        logger.error("Email draft generation failed for proposal %s: %s", proposal.id, exc)
        record_claude_call(
            proposal_id=proposal.id,
            section_key="delivery_email_draft",
            call_type="email_draft",
            status="failed",
            system_prompt=system,
            user_prompt=user,
            duration_ms=0,
            error_message=str(exc),
        )
        raise

    record_claude_call(
        proposal_id=proposal.id,
        section_key="delivery_email_draft",
        call_type="email_draft",
        status="succeeded",
        system_prompt=system,
        user_prompt=user,
        duration_ms=0,  # real latency available from the caller side if needed
        response_text=result.text,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        stop_reason=result.stop_reason,
        model=result.model,
    )

    subject, body = _split_subject_and_body(result.text)
    return (
        subject if subject else build_email_subject_fallback(proposal),
        body if body else build_email_body_fallback(proposal, "[PROPOSAL_LINK]"),
    )


def _split_subject_and_body(text: str) -> tuple[str | None, str | None]:
    """Split a model response that begins with SUBJECT: ... onto its own line."""
    if not text:
        return None, None
    lines = text.splitlines()
    subject_line: str | None = None
    body_lines: list[str] = []
    for line in lines:
        if line.strip().upper().startswith("SUBJECT:") and subject_line is None:
            subject_line = line.split(":", 1)[1].strip()
            continue
        body_lines.append(line)
    body = "\n".join(body_lines).strip() if body_lines else None
    return subject_line or None, body or None


def build_email_subject_fallback(proposal: Proposal) -> str:
    """Plain template fallback subject if AI generation produces nothing usable."""
    return f"Proposal for {proposal.company_name}"


def build_email_body_fallback(proposal: Proposal, document_link: str) -> str:
    """Plain template fallback body if AI generation produces nothing usable."""
    signature = proposal.salesperson_name or f"The {BRAND_NAME} Team"
    return (
        f"Hi {proposal.client_name},\n\n"
        "Thanks again for taking the time to speak with us. Based on our "
        "conversation, we have put together a customized proposal for your "
        "review.\n\n"
        f"You can view the proposal here: {document_link}\n\n"
        "This document outlines the project scope, timeline, pricing details, "
        "and recommended approach.\n\n"
        "If you have any questions or would like to make adjustments, feel free "
        "to reach out. We are happy to iterate with you.\n\n"
        "Looking forward to hearing your thoughts.\n\n"
        f"Best regards,\n\n{signature}\n\n{BRAND_NAME}"
    )
