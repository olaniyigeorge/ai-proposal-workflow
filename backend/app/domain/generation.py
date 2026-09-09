"""
Full-proposal generation — assembling what Claude needs to write the sections
that are not pure pinned-fact passthroughs. Pure domain logic: no I/O, no
anthropic import (that lives in adapters/claude_client.py).

Per docs/intake-schema.md's "Proposal sections" list, only three of the six
template sections require an actual generation call — the rest are canonical
facts reproduced verbatim by intake_service.py at intake time and are never
touched here:

  1. Introduction          — fully generated (no pinned field maps to it)
  2. Proposed Solution     — `project_scope` verbatim + generated `recommended_approach`
  3. Deliverables          — generated from `recommended_services`
  4. Timeline              — pinned verbatim (no generation)
  5. Pricing               — pinned verbatim (no generation)
  6. Next Steps            — static boilerplate (no generation)
"""

from app.models.proposal import Proposal, SectionKey

# Sections a full-generation job must call Claude for. Every other SectionKey
# keeps the template_default content intake_service.py already wrote.
GENERATED_SECTION_KEYS: frozenset[SectionKey] = frozenset(
    {SectionKey.INTRODUCTION, SectionKey.PROPOSED_SOLUTION, SectionKey.DELIVERABLES}
)

# Fixed house tone derived from the reference proposal template (CLAUDE.md /
# architecture.md §4 point 2). Stored once, layered under any future per-call
# salesperson instruction for regeneration — never replaced by it.
HOUSE_TONE = (
    "Confident, professional, and client-focused sales writing. Clear and "
    "concrete rather than generic — reference the client's actual stated "
    "needs and goals rather than boilerplate phrasing. Warm but not casual; "
    "no exclamation points, no marketing hyperbole, no emoji. Write in "
    "complete paragraphs, not bullet lists, unless the section is explicitly "
    "a list."
)


def _canonical_facts_block(proposal: Proposal) -> str:
    """The canonical facts layer — every pinned intake field, presented as
    facts the model must treat as ground truth and never contradict or
    invent alternatives for (architecture.md §4 point 4).
    """
    return (
        f"Client name: {proposal.client_name}\n"
        f"Company: {proposal.company_name}\n"
        f"Date of discovery call: {proposal.date_of_call}\n"
        f"Client's stated needs: {proposal.client_needs_summary}\n"
        f"Project scope: {proposal.project_scope}\n"
        f"Goals and objectives: {proposal.goals_and_objectives}\n"
        f"Recommended services/deliverables (raw sales notes): {proposal.recommended_services}\n"
        f"Proposed timeline: {proposal.proposed_timeline}\n"
        f"Estimated pricing: {proposal.estimated_pricing}\n"
    )


def build_system_prompt() -> str:
    return (
        "You are drafting one section of a sales proposal for an internal "
        "proposal-review tool. The salesperson will review and edit your "
        "output before anything is sent to the client.\n\n"
        f"House tone:\n{HOUSE_TONE}\n\n"
        "Rules:\n"
        "- Use only the facts given to you. Never invent client details, "
        "dates, prices, or commitments not present in the facts provided.\n"
        "- Never restate pricing, dates, or the client/company name as your "
        "own paraphrase if a pinned section elsewhere already states them "
        "verbatim — focus on the narrative this section is asked for.\n"
        "- Output only the section's prose. No heading, no markdown, no "
        "preamble like \"Here is the section\".\n"
    )


def build_user_prompt(proposal: Proposal, section_key: SectionKey) -> str:
    facts = _canonical_facts_block(proposal)

    if section_key == SectionKey.INTRODUCTION:
        task = (
            "Write the Introduction section of the proposal. Open the "
            "document, thank the client for the discovery call, and briefly "
            "frame the engagement in terms of their stated needs and goals. "
            "2-3 short paragraphs."
        )
    elif section_key == SectionKey.PROPOSED_SOLUTION:
        task = (
            "Write the 'recommended approach' narrative for the Proposed "
            "Solution section — do not restate the project scope verbatim "
            "(it is shown to you for context only and is inserted separately "
            "above your text). Explain, in 2-3 paragraphs, the approach "
            "recommended to address the project scope and goals given."
        )
    elif section_key == SectionKey.DELIVERABLES:
        task = (
            "Write the Deliverables section. The raw sales notes on "
            "recommended services above fold services and deliverables "
            "together — separate and expand them into a clear list of "
            "concrete deliverables the client will receive, one per line, "
            "as short phrases (not full sentences)."
        )
    else:
        raise ValueError(
            f"build_user_prompt called for a non-generated section: {section_key.value}"
        )

    return f"{task}\n\nFacts:\n{facts}"


def assemble_section_content(section_key: SectionKey, pinned_content: str, generated_text: str) -> str:
    """Combine a section's pinned/verbatim prefix (if any) with Claude's
    generated text. Only PROPOSED_SOLUTION has a pinned prefix (`project_scope`
    verbatim) that must survive alongside the generated `recommended_approach`
    — introduction and deliverables are pure generated content.
    """
    generated_text = generated_text.strip()
    if section_key == SectionKey.PROPOSED_SOLUTION:
        return f"{pinned_content}\n\n{generated_text}"
    return generated_text
