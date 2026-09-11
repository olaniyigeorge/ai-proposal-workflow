"""
Branded proposal HTML — rendered to PDF by adapters/pdf_renderer.py. Pure
domain logic: builds a string, no I/O, no weasyprint import.

Structure mirrors docs/reference/proposal-template.md (6 sections, in
`ProposalSection.order_index` order). Colors/fonts come from
app/domain/design_tokens.py (see that module for why this backend can't
literally import the dashboard's own token source). Font stack matches the
dashboard's `--font` custom property exactly (`Geist Sans` first, falling
back to system sans-serif) — WeasyPrint has no network access to Google's
font CDN during rendering, so this intentionally never fetches a font file;
if "Geist Sans" isn't installed where this runs, it silently falls back
rather than failing the render.

Section rendering (revised again 2026-09-11, superseding the bordered-card
layout from docs/design-system-redesign-and-ownership-concerns.md §6-§8 —
see docs/edge-cases.md "Pinned sections read as pasted-in fragments, not
part of one document"): a client proposal reading as six boxed cards stacked
on a page looks like sections were joined rather than written as one
document — closer to a component library than a piece of business writing.
Sections now render as continuous typeset prose: a numbered running heading
(an accent-colored index + title under a thin rule, no card chrome around
the body) followed by real `<p>`/`<ul>`/`<ol>` markup instead of one
`white-space:pre-wrap` blob. Brand tokens (color/font) are unchanged from
the card version — this is a layout change, not a rebrand.

Every user-controlled string (client name, company name, section content —
anything that ultimately traces back to a Google Form answer) is HTML-escaped
before insertion. This is the one place in the codebase that assembles raw
HTML from those fields, so it's also the one place an unescaped client answer
could break the document's structure or, worse, inject markup — escaping is
not optional here.
"""

import html
import re
from datetime import datetime

from app.domain.design_tokens import ACCENT, BORDER, BRAND_NAME, FONT_STACK, INK, MUTED
from app.models.proposal import Proposal, ProposalSection

_CSS = f"""
@page {{
    size: A4;
    margin: 2.2cm 2cm 2.5cm 2cm;
    @bottom-center {{
        content: "Page " counter(page) " of " counter(pages);
        font-size: 9px;
        color: {MUTED};
    }}
}}
* {{ box-sizing: border-box; }}
body {{
    font-family: {FONT_STACK};
    color: {INK};
    font-size: 11pt;
    line-height: 1.5;
}}
.doc-header {{
    border-bottom: 1px solid {BORDER};
    padding-bottom: 12px;
    margin-bottom: 20px;
}}
/* rgba(37, 99, 235, ...) is ACCENT's rgb() decomposition — WeasyPrint's CSS
   engine doesn't support the color-mix() shorthand a browser would use here. */
.brand {{
    display: inline-block;
    font-size: 9.5pt;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: {ACCENT};
    background: rgba(37, 99, 235, 0.08);
    border: 1px solid rgba(37, 99, 235, 0.25);
    border-radius: 999px;
    padding: 4px 12px;
    margin-bottom: 12px;
}}
.doc-header h1 {{
    font-size: 22pt;
    margin: 0 0 6px 0;
    color: {INK};
}}
.doc-header .meta {{
    font-size: 10pt;
    color: {MUTED};
    margin: 0;
}}
.section {{
    margin: 0 0 22px 0;
}}
.section h2 {{
    display: flex;
    align-items: baseline;
    gap: 10px;
    font-size: 13pt;
    color: {INK};
    margin: 0 0 10px 0;
    padding-bottom: 6px;
    border-bottom: 1.5px solid {ACCENT};
    break-after: avoid-page;
}}
.section h2 .num {{
    color: {ACCENT};
    font-weight: 700;
    font-size: 10.5pt;
    letter-spacing: 0.04em;
}}
.section .content {{
    color: {INK};
}}
.section .content p {{
    margin: 0 0 10px 0;
}}
.section .content p:last-child {{
    margin-bottom: 0;
}}
.section .content ul,
.section .content ol {{
    margin: 0 0 10px 0;
    padding-left: 20px;
}}
.section .content li {{
    margin-bottom: 4px;
}}
.doc-footer {{
    margin-top: 36px;
    padding-top: 10px;
    border-top: 1px solid {BORDER};
    font-size: 9pt;
    color: {MUTED};
    text-align: center;
}}
"""


def _esc(value: str) -> str:
    return html.escape(value or "")


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "untitled"


def build_document_filename(proposal: Proposal) -> str:
    """A human-readable, unique-enough filename — client name + company
    name (there's no distinct "project name" field in the intake schema;
    `project_scope` is a free-text sentence, not a short name, so it's not a
    good filename component). Uniqueness in the strict sense comes from the
    proposal's UUID in the storage path this filename sits under
    (services/document_service.py) — this is about readability for whoever
    downloads it, not collision-avoidance.
    """
    return f"{_slugify(proposal.client_name)}-{_slugify(proposal.company_name)}-proposal.pdf"


_NUMBERED_LINE = re.compile(r"^\d+[.)]\s+")


def _render_paragraphs(content: str) -> str:
    """Turn a section's plain-text content into real prose markup instead of
    one `white-space: pre-wrap` blob — a blank line starts a new `<p>`; a
    block of short lines that are all numbered ("1. ...") or all bare
    (Deliverables' one-phrase-per-line convention) renders as a list. This is
    a formatting pass only — every word still comes from `section.content`
    unchanged, just escaped and wrapped.
    """
    blocks = [b.strip() for b in re.split(r"\n\s*\n", content.strip()) if b.strip()]
    parts = []
    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if len(lines) > 1 and all(_NUMBERED_LINE.match(line) for line in lines):
            items = "".join(
                f"<li>{_esc(_NUMBERED_LINE.sub('', line))}</li>" for line in lines
            )
            parts.append(f"<ol>{items}</ol>")
        elif len(lines) > 1 and all(len(line.split()) <= 12 for line in lines):
            items = "".join(f"<li>{_esc(line)}</li>" for line in lines)
            parts.append(f"<ul>{items}</ul>")
        else:
            parts.append(f"<p>{_esc(block).replace(chr(10), '<br>')}</p>")
    return "".join(parts)


def _render_section(index: int, section: ProposalSection) -> str:
    return (
        f'<section class="section">'
        f'<h2><span class="num">{index:02d}</span>{_esc(section.title)}</h2>'
        f'<div class="content">{_render_paragraphs(section.content)}</div>'
        f"</section>"
    )


def render_proposal_html(proposal: Proposal) -> str:
    """The full HTML document for one proposal's PDF. Every section renders
    in `order_index` order regardless of what order they happen to be loaded
    in — the template's fixed 6-section structure (decisions #8) is what the
    document must reflect, not incidental DB ordering.
    """
    ordered_sections = sorted(proposal.sections, key=lambda s: s.order_index)
    sections_html = "".join(
        _render_section(i, section) for i, section in enumerate(ordered_sections, start=1)
    )
    generated_on = datetime.now().strftime("%B %d, %Y")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Proposal for {_esc(proposal.company_name)}</title>
<style>{_CSS}</style>
</head>
<body>
<header class="doc-header">
    <div class="brand">{_esc(BRAND_NAME)}</div>
    <h1>Proposal for {_esc(proposal.client_name)}</h1>
    <p class="meta">
        Prepared for {_esc(proposal.company_name)} &middot;
        Discovery call: {_esc(proposal.date_of_call)} &middot;
        Document generated: {_esc(generated_on)}
    </p>
</header>
{sections_html}
<footer class="doc-footer">{_esc(BRAND_NAME)} &mdash; Confidential Proposal</footer>
</body>
</html>"""
