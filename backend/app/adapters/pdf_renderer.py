"""
The only module allowed to import `weasyprint`/`pypdf` directly (per
CLAUDE.md: "adapters are the only place that import a third-party SDK").
WeasyPrint renders HTML+CSS to PDF with full CSS Paged Media support (@page,
page breaks, running headers/footers) — the branded layout itself lives in
domain/document.py, which builds the HTML this module just renders. pypdf
reads the rendered bytes back to count pages for the DocumentArtifact record
and for rendering-fidelity tests (CLAUDE.md: page breaks, long-content
overflow need explicit coverage since the PDF is generated exactly once).
"""

import io

from pypdf import PdfReader
from weasyprint import HTML


class PdfRenderError(Exception):
    """Raised on any failure turning HTML into PDF bytes. Callers
    (services/document_service.py) treat this the same way Claude-call
    failures are treated: leave the Proposal's prior state intact and
    transition to a *_FAILED status rather than committing a partial file.
    """


def render_pdf(html_content: str) -> bytes:
    """Synchronous, CPU-bound — callers running inside the async event loop
    (the document-generation background job) should offload this via
    asyncio.to_thread rather than awaiting it directly, so one proposal's
    render doesn't stall the loop for everything else in flight.
    """
    try:
        pdf_bytes = HTML(string=html_content).write_pdf()
    except Exception as exc:  # weasyprint doesn't expose a narrow exception type
        raise PdfRenderError(f"PDF rendering failed: {exc}") from exc

    if not pdf_bytes:
        raise PdfRenderError("PDF rendering produced an empty file")

    return pdf_bytes


def count_pdf_pages(pdf_bytes: bytes) -> int:
    return len(PdfReader(io.BytesIO(pdf_bytes)).pages)
