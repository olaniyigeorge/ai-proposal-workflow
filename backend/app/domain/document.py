"""
Branded proposal HTML — rendered to PDF by adapters/pdf_renderer.py. Pure
domain logic: builds a string, no I/O, no weasyprint import.

Structure mirrors docs/reference/proposal-template.md (6 sections, in
`ProposalSection.order_index` order). Colors/fonts are pulled from
koyatalent.com's actual compiled CSS (fetched 2026-09-10 — no design asset
existed in this repo before then): ink `#1f2429`, muted text `#5c646c`,
light section background `#eef0ee`, border `#d8dbd9`, and the site's CTA
accent blue `#2563eb` (used on-site for its own call-to-action links/borders
— see docs/edge-cases.md for the exact source). Font stack matches the
site's `--font` custom property exactly (`Geist Sans` first, falling back to
system sans-serif) — WeasyPrint has no network access to Google's font CDN
during rendering, so this intentionally never fetches a font file; if "Geist
Sans" isn't installed where this runs, it silently falls back rather than
failing the render.

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

from app.models.proposal import Proposal, ProposalSection

BRAND_NAME = "Koya Talent"

# koyatalent.com's own design tokens (see module docstring).
INK = "#1f2429"
MUTED = "#5c646c"
ACCENT = "#2563eb"
BG_LIGHT = "#eef0ee"
BORDER = "#d8dbd9"
FONT_STACK = '"Geist Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'

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
    border-bottom: 3px solid {ACCENT};
    padding-bottom: 14px;
    margin-bottom: 28px;
}}
.brand {{
    font-size: 11pt;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: {ACCENT};
    margin-bottom: 10px;
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
    margin-bottom: 22px;
    break-inside: avoid-page;
}}
.section h2 {{
    font-size: 13pt;
    color: {ACCENT};
    border-bottom: 1px solid {BORDER};
    padding-bottom: 4px;
    margin: 0 0 8px 0;
}}
.section .content {{
    white-space: pre-wrap;
    background: {BG_LIGHT};
    border-radius: 3px;
    padding: 10px 12px;
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


def _render_section(index: int, section: ProposalSection) -> str:
    content_html = _esc(section.content).replace("\n", "<br>")
    return (
        f'<section class="section">'
        f'<h2>{index}. {_esc(section.title)}</h2>'
        f'<div class="content">{content_html}</div>'
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
