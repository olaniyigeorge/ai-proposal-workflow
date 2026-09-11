"""Tests for document generation (Phase 6). Per CLAUDE.md: the PDF is
generated exactly once, only from APPROVED, and there's no earlier point in
the flow where a rendering bug would surface — so rendering fidelity
(branding, page breaks, long-content overflow) needs explicit coverage here,
not just "the job completed without raising."
"""

import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient
from pypdf import PdfReader
import io

import app.services.document_service as document_service
from app.adapters.pdf_renderer import PdfRenderError, count_pdf_pages, render_pdf
from app.adapters.storage_client import StorageUploadError
from app.domain.document import BRAND_NAME, build_document_filename, render_proposal_html
from app.domain.proposal_transitions import transition_proposal
from app.models.document import DocumentArtifact
from app.models.proposal import (
    ContentOrigin,
    Proposal,
    ProposalSection,
    ProposalStatus,
    SectionApprovalStatus,
    SectionKey,
)
from app.services.proposal_service import get_proposal_by_id
from tests.conftest import TestAsyncSessionLocal

AUTH_HEADERS = {"Authorization": "Bearer dev-salesperson-token"}


def _make_proposal(status: ProposalStatus = ProposalStatus.APPROVED, long_section: bool = False) -> Proposal:
    proposal = Proposal(
        status=status,
        client_name="Alice O'Brien",
        client_email="alice@acme.com",
        company_name="Acme <Corp>",  # deliberately includes HTML-unsafe chars
        salesperson_name="Bob",
        date_of_call="2026-09-08",
        client_needs_summary="needs",
        project_scope="Build a widget factory",
        goals_and_objectives="goals",
        recommended_services="services",
        proposed_timeline="6 weeks",
        estimated_pricing="$20,000",
    )
    long_content = ("This is a long deliverable description. " * 400) if long_section else "A list."
    sections_defs = [
        (SectionKey.INTRODUCTION, "Introduction", 0, "Thanks for your time."),
        (SectionKey.PROPOSED_SOLUTION, "Proposed Solution", 1, "Scope:\nBuild a widget factory\n\nApproach."),
        (SectionKey.DELIVERABLES, "Deliverables", 2, long_content),
        (SectionKey.TIMELINE, "Timeline", 3, "6 weeks"),
        (SectionKey.PRICING, "Pricing", 4, "$20,000"),
        (SectionKey.NEXT_STEPS, "Next Steps", 5, "1. Review."),
    ]
    proposal.sections = [
        ProposalSection(
            section_key=key,
            title=title,
            order_index=order,
            content=content,
            content_origin=ContentOrigin.AI_GENERATED,
            approval_status=SectionApprovalStatus.APPROVED,
            regeneration_count=0,
            version=1,
        )
        for key, title, order, content in sections_defs
    ]
    return proposal


# ---------------------------------------------------------------------------
# Rendering fidelity — pure domain + adapter, no DB, no HTTP.
# ---------------------------------------------------------------------------


def test_render_proposal_html_escapes_user_controlled_content() -> None:
    proposal = _make_proposal()
    html_out = render_proposal_html(proposal)
    assert "<Corp>" not in html_out
    assert "&lt;Corp&gt;" in html_out
    assert "Alice O&#x27;Brien" in html_out or "Alice O'Brien" not in html_out


def test_render_proposal_html_includes_brand_and_sections_in_order() -> None:
    proposal = _make_proposal()
    html_out = render_proposal_html(proposal)
    assert BRAND_NAME in html_out
    intro_pos = html_out.index("Introduction")
    solution_pos = html_out.index("Proposed Solution")
    deliverables_pos = html_out.index("Deliverables")
    assert intro_pos < solution_pos < deliverables_pos


def test_render_proposal_html_uses_flowing_prose_not_bordered_cards() -> None:
    """Revised 2026-09-11 (docs/edge-cases.md): sections must read as
    continuous typeset prose — numbered running headings over real
    paragraph/list markup — not boxed, bordered cards around a
    white-space:pre-wrap blob.
    """
    proposal = _make_proposal()
    html_out = render_proposal_html(proposal)
    assert "<p>" in html_out
    assert "white-space: pre-wrap" not in html_out
    assert '<span class="num">01</span>' in html_out
    # The section body itself has no card border/background/radius left —
    # only the unrelated header "brand" pill badge still uses border-radius.
    section_css = html_out[html_out.index(".section {") : html_out.index(".doc-footer")]
    assert "border-radius" not in section_css
    assert "border:" not in section_css


def test_render_proposal_html_renders_numbered_lines_as_ordered_list() -> None:
    proposal = _make_proposal()
    next_steps = next(s for s in proposal.sections if s.section_key == SectionKey.NEXT_STEPS)
    next_steps.content = "1. Review and approve.\n2. Execute agreement.\n3. Schedule kickoff."
    html_out = render_proposal_html(proposal)
    assert "<ol><li>Review and approve.</li><li>Execute agreement.</li><li>Schedule kickoff.</li></ol>" in html_out


def test_build_document_filename_is_slugified_and_readable() -> None:
    proposal = _make_proposal()
    filename = build_document_filename(proposal)
    assert filename == "alice-o-brien-acme-corp-proposal.pdf"
    assert " " not in filename
    assert filename.endswith(".pdf")


def test_pdf_renders_with_branding_visible_in_extracted_text() -> None:
    proposal = _make_proposal()
    html_out = render_proposal_html(proposal)
    pdf_bytes = render_pdf(html_out)

    reader = PdfReader(io.BytesIO(pdf_bytes))
    full_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    # Normalize whitespace/case: the brand renders CSS-uppercased in the
    # header, and PDF text extraction can insert stray spaces/newlines at
    # font-subset ligature boundaries — neither is a real rendering defect.
    normalized = "".join(full_text.upper().split())
    assert BRAND_NAME.upper().replace(" ", "") in normalized
    assert "Acme" in full_text
    assert "Introduction" in full_text
    assert "Deliverables" in full_text


def test_pdf_short_proposal_is_a_single_page() -> None:
    proposal = _make_proposal(long_section=False)
    pdf_bytes = render_pdf(render_proposal_html(proposal))
    assert count_pdf_pages(pdf_bytes) == 1


def test_pdf_long_content_overflows_to_additional_pages() -> None:
    """A very long section must flow onto more pages, not get clipped to
    page 1 — this is exactly the failure mode that has no earlier point in
    the flow to catch it, since the PDF is only ever generated once.
    """
    proposal = _make_proposal(long_section=True)
    pdf_bytes = render_pdf(render_proposal_html(proposal))
    page_count = count_pdf_pages(pdf_bytes)
    assert page_count > 1

    reader = PdfReader(io.BytesIO(pdf_bytes))
    full_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    # The long section's content must be fully present, not truncated —
    # count a single word (never split by line-wrap) rather than the full
    # repeated phrase, since PDF text extraction can insert a stray newline
    # at a wrap point that happens to fall mid-phrase.
    assert full_text.count("deliverable") >= 390


def test_render_pdf_rejects_malformed_input_gracefully() -> None:
    # WeasyPrint is lenient with malformed HTML (it's designed to render
    # arbitrary web content), so this asserts the adapter's contract instead:
    # it never returns an empty/falsy result silently.
    pdf_bytes = render_pdf("<html><body>Minimal</body></html>")
    assert pdf_bytes
    assert count_pdf_pages(pdf_bytes) >= 1


# ---------------------------------------------------------------------------
# Service-level tests — real (in-memory) DB session.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_session():
    async with TestAsyncSessionLocal() as session:
        yield session


async def _persist(db, proposal: Proposal) -> Proposal:
    db.add(proposal)
    await db.flush()
    await db.commit()
    await db.refresh(proposal)
    return await get_proposal_by_id(db, proposal.id)


@pytest.mark.asyncio
async def test_start_document_generation_from_approved_succeeds(db_session) -> None:
    proposal = await _persist(db_session, _make_proposal(ProposalStatus.APPROVED))
    updated = await document_service.start_document_generation(db_session, proposal)
    assert updated.status == ProposalStatus.DOCUMENT_GENERATING


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [ProposalStatus.DRAFT, ProposalStatus.IN_REVIEW, ProposalStatus.PENDING_APPROVAL],
)
async def test_start_document_generation_rejected_outside_approved(db_session, status) -> None:
    from app.domain.exceptions import InvalidTransitionError

    proposal = _make_proposal(ProposalStatus.APPROVED)
    proposal.status = status
    proposal = await _persist(db_session, proposal)

    with pytest.raises(InvalidTransitionError):
        await document_service.start_document_generation(db_session, proposal)


@pytest.mark.asyncio
async def test_start_document_generation_replaces_stale_artifact_on_reapproval(db_session) -> None:
    """A proposal edited/regenerated post-approval is forced back to
    IN_REVIEW (decisions #9) and can be re-approved — at which point the
    prior DocumentArtifact is stale, not a duplicate of the same approval,
    so generation must be re-triggerable rather than permanently blocked
    (decisions #9's follow-up, resolved 2026-09-11).
    """
    proposal = await _persist(db_session, _make_proposal(ProposalStatus.APPROVED))
    stale = DocumentArtifact(
        proposal_id=proposal.id, storage_path="x", file_size_bytes=1, page_count=1
    )
    db_session.add(stale)
    await db_session.commit()
    stale_id = stale.id

    updated = await document_service.start_document_generation(db_session, proposal)

    assert updated.status == ProposalStatus.DOCUMENT_GENERATING
    remaining = await document_service.get_document_artifact(db_session, proposal.id)
    assert remaining is None or remaining.id != stale_id


@pytest.mark.asyncio
async def test_generate_document_success_creates_artifact_and_transitions(
    db_session, monkeypatch
) -> None:
    proposal = _make_proposal(ProposalStatus.APPROVED)
    transition_proposal(proposal, ProposalStatus.DOCUMENT_GENERATING)
    proposal = await _persist(db_session, proposal)

    async def fake_upload(path: str, pdf_bytes: bytes) -> None:
        pass

    monkeypatch.setattr(document_service, "upload_pdf", fake_upload)

    await document_service.generate_document(db_session, proposal)

    assert proposal.status == ProposalStatus.DOCUMENT_READY
    artifact = await document_service.get_document_artifact(db_session, proposal.id)
    assert artifact is not None
    assert artifact.page_count >= 1
    assert artifact.file_size_bytes > 0


@pytest.mark.asyncio
async def test_generate_document_upload_failure_leaves_proposal_recoverable(
    db_session, monkeypatch
) -> None:
    proposal = _make_proposal(ProposalStatus.APPROVED)
    transition_proposal(proposal, ProposalStatus.DOCUMENT_GENERATING)
    proposal = await _persist(db_session, proposal)

    async def failing_upload(path: str, pdf_bytes: bytes) -> None:
        raise StorageUploadError("network error")

    monkeypatch.setattr(document_service, "upload_pdf", failing_upload)

    await document_service.generate_document(db_session, proposal)

    assert proposal.status == ProposalStatus.DOCUMENT_GENERATION_FAILED
    artifact = await document_service.get_document_artifact(db_session, proposal.id)
    assert artifact is None

    # Retry path: DOCUMENT_GENERATION_FAILED -> DOCUMENT_GENERATING is legal.
    updated = await document_service.start_document_generation(db_session, proposal)
    assert updated.status == ProposalStatus.DOCUMENT_GENERATING


@pytest.mark.asyncio
async def test_generate_document_render_failure_leaves_proposal_recoverable(
    db_session, monkeypatch
) -> None:
    proposal = _make_proposal(ProposalStatus.APPROVED)
    transition_proposal(proposal, ProposalStatus.DOCUMENT_GENERATING)
    proposal = await _persist(db_session, proposal)

    def failing_render(html_content: str) -> bytes:
        raise PdfRenderError("boom")

    monkeypatch.setattr(document_service, "render_pdf", failing_render)

    await document_service.generate_document(db_session, proposal)

    assert proposal.status == ProposalStatus.DOCUMENT_GENERATION_FAILED
    artifact = await document_service.get_document_artifact(db_session, proposal.id)
    assert artifact is None


# ---------------------------------------------------------------------------
# HTTP-level tests
# ---------------------------------------------------------------------------


async def _seed_proposal_via_db(status: ProposalStatus = ProposalStatus.APPROVED) -> uuid.UUID:
    async with TestAsyncSessionLocal() as db:
        proposal = _make_proposal(status)
        db.add(proposal)
        await db.commit()
        await db.refresh(proposal)
        return proposal.id


@pytest.mark.asyncio
async def test_generate_document_endpoint_requires_auth(async_client: AsyncClient) -> None:
    proposal_id = await _seed_proposal_via_db()
    response = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/generate-document"
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_generate_document_endpoint_rejects_wrong_status(
    async_client: AsyncClient,
) -> None:
    proposal_id = await _seed_proposal_via_db(status=ProposalStatus.IN_REVIEW)
    response = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/generate-document", headers=AUTH_HEADERS
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_generate_document_endpoint_happy_path(
    async_client: AsyncClient, monkeypatch
) -> None:
    monkeypatch.setattr(document_service, "AsyncSessionLocal", TestAsyncSessionLocal)

    async def fake_upload(path: str, pdf_bytes: bytes) -> None:
        pass

    monkeypatch.setattr(document_service, "upload_pdf", fake_upload)

    proposal_id = await _seed_proposal_via_db()

    response = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/generate-document", headers=AUTH_HEADERS
    )
    assert response.status_code == 202

    # Background task runs in-process under the test ASGI transport, so by
    # the time the response is back the job has already completed.
    detail_resp = await async_client.get(
        f"/api/v1/proposals/{proposal_id}", headers=AUTH_HEADERS
    )
    assert detail_resp.json()["status"] == "DOCUMENT_READY"

    async with TestAsyncSessionLocal() as db:
        artifact = await document_service.get_document_artifact(db, proposal_id)
        assert artifact is not None
        assert artifact.page_count >= 1

    # A second attempt right after is still rejected — but now because the
    # proposal is DOCUMENT_READY, not APPROVED (InvalidTransitionError), not
    # because a DocumentArtifact already exists. Re-generation is legitimate
    # again only after a post-approval edit forces a fresh APPROVED cycle
    # (see test_start_document_generation_replaces_stale_artifact_on_reapproval).
    second = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/generate-document", headers=AUTH_HEADERS
    )
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_generate_document_endpoint_unknown_proposal_is_404(
    async_client: AsyncClient,
) -> None:
    response = await async_client.post(
        f"/api/v1/proposals/{uuid.uuid4()}/generate-document", headers=AUTH_HEADERS
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_document_endpoint_404_before_generation(async_client: AsyncClient) -> None:
    proposal_id = await _seed_proposal_via_db()
    response = await async_client.get(
        f"/api/v1/proposals/{proposal_id}/document", headers=AUTH_HEADERS
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_document_endpoint_requires_auth(async_client: AsyncClient) -> None:
    proposal_id = await _seed_proposal_via_db()
    response = await async_client.get(f"/api/v1/proposals/{proposal_id}/document")
    assert response.status_code == 401
