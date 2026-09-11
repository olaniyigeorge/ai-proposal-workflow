"""
Client delivery email composition (Phase 7). Pure domain logic: builds
subject/text/HTML strings, no I/O, no email-provider import.

Matches docs/reference/client-email-template.md exactly — every field here
is a pinned fact (client_name, company_name, salesperson_name, the document
link), not free-generated text, so this is template filling, not a Claude
call. There's nothing here for a model to paraphrase or get wrong: the
template is already short, professional boilerplate.

The HTML version reuses app/domain/design_tokens.py's shared tokens (the
same source domain/document.py's PDF reads from) so the email and the PDF
it links to read as one brand, not two. Header/card treatment (resolved
2026-09-11, docs/design-system-redesign-and-ownership-concerns.md §6-§8): a
light card on a soft background echoes the dashboard's surface/border
language rather than the dark banner this used to open with — email clients
are a constrained medium (§7 point 3), so this stays to plain nested tables/
divs with inline styles and no assumption that anything beyond basic
box-model CSS survives rendering. The document link is the one "creative"
element: a styled CTA button rather than a bare URL, since most inboxes
render the plain-text fallback's raw link anyway but the HTML version is
what most clients actually see.
"""

import html

from app.domain.design_tokens import (
    ACCENT,
    BORDER,
    BRAND_NAME,
    CARD_RADIUS,
    CARD_RADIUS_LG,
    FONT_STACK,
    INK,
    MUTED,
    SURFACE_BASE,
    SURFACE_CARD,
)
from app.models.proposal import Proposal


def _esc(value: str) -> str:
    return html.escape(value or "")


def build_email_subject(proposal: Proposal) -> str:
    return f"Proposal for {proposal.company_name}"


def _signature(proposal: Proposal) -> str:
    """`salesperson_name` is nullable (decisions #20 — a client can submit
    intake directly with no salesperson on the call). Sign as the brand
    rather than leaving a blank line or a literal "None" in a client-facing
    email when it's unset.
    """
    return proposal.salesperson_name or f"The {BRAND_NAME} Team"


def build_email_body(proposal: Proposal, document_link: str) -> str:
    """Plain-text fallback — every email client that ignores/strips HTML
    (or a bounce/spam filter that only ever reads the text part) still gets
    a complete, working message with the link as a literal URL.
    """
    signature = _signature(proposal)

    return (
        f"Hi {proposal.client_name},\n\n"
        "Thanks again for taking the time to speak with us. Based on our "
        "conversation, we have put together a customized proposal for your "
        "review.\n\n"
        f"You can view the proposal here: {document_link}\n\n"
        "This document outlines the project scope, timeline, pricing "
        "details, and recommended approach.\n\n"
        "If you have any questions or would like to make adjustments, feel "
        "free to reach out. We are happy to iterate with you.\n\n"
        "Looking forward to hearing your thoughts.\n\n"
        "Best regards,\n\n"
        f"{signature}\n\n"
        f"{BRAND_NAME}"
    )


def build_email_html(proposal: Proposal, document_link: str) -> str:
    """Branded HTML companion to build_email_body — same copy, styled with
    koyatalent.com's own tokens and a CTA button linking to the document
    (docs/reference/client-email-template.md's "You can view the proposal
    here: {{proposal_link}}" line, rendered as a button rather than bare
    text). Inline styles throughout: email clients strip or ignore <style>
    blocks unpredictably, inline is the only style that reliably survives.
    """
    client_name = _esc(proposal.client_name)
    signature = _esc(_signature(proposal))
    link = _esc(document_link)

    return f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:{SURFACE_BASE};font-family:{FONT_STACK};">
<div style="max-width:560px;margin:0 auto;padding:32px 16px;">
  <div style="background:{SURFACE_CARD};border:1px solid {BORDER};border-radius:{CARD_RADIUS_LG};overflow:hidden;">
    <div style="background:{SURFACE_CARD};padding:20px 28px;border-bottom:1px solid {BORDER};">
      <span style="display:inline-block;color:{ACCENT};font-weight:700;letter-spacing:0.08em;text-transform:uppercase;font-size:12px;background:rgba(37,99,235,0.08);border:1px solid rgba(37,99,235,0.25);border-radius:999px;padding:5px 12px;">{_esc(BRAND_NAME)}</span>
    </div>
    <div style="padding:28px;color:{INK};font-size:15px;line-height:1.6;">
      <p style="margin:0 0 16px 0;">Hi {client_name},</p>
      <p style="margin:0 0 16px 0;">Thanks again for taking the time to speak with us. Based on our conversation and your feedback, we have put together a customized proposal for your review.</p>
      <p style="text-align:center;margin:28px 0;">
        <a href="{link}" style="display:inline-block;background:{ACCENT};color:#ffffff;text-decoration:none;font-weight:600;font-size:14px;padding:13px 30px;border-radius:{CARD_RADIUS};">View Your Proposal</a>
      </p>
      <p style="margin:0 0 16px 0;color:{MUTED};font-size:13px;">This document outlines the project scope, timeline, pricing details, and recommended approach.</p>
      <p style="margin:0 0 16px 0;">If you have any questions or would like to make adjustments, feel free to reach out. We are happy to iterate with you.</p>
      <p style="margin:0 0 24px 0;">Looking forward to hearing your thoughts.</p>
      <p style="margin:0;">Best regards,<br>{signature}<br>{_esc(BRAND_NAME)}</p>
    </div>
  </div>
</div>
</body>
</html>"""
