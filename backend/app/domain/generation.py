"""
Full-proposal generation — assembling what Claude needs to write the sections
that are not pure pinned-fact passthroughs. Pure domain logic: no I/O, no
anthropic import (that lives in adapters/claude_client.py).

Per `docs/reference/proposal-template.md` (the actual reference template —
see `docs/intake-schema.md` "Proposal sections"), only **two** of the six
template sections require an actual generation call. Introduction is fixed
boilerplate wrapping two pinned facts verbatim — the template has no
generated placeholder in it at all — so intake_service.py assembles it
directly at intake time, same as Timeline/Pricing/Next Steps:

  1. Introduction          — pinned only, assembled at intake (no Claude call)
  2. Proposed Solution     — `project_scope` verbatim + generated `recommended_approach`
  3. Deliverables          — generated from `recommended_services`
  4. Timeline              — pinned verbatim (no generation)
  5. Pricing               — pinned verbatim (no generation)
  6. Next Steps            — static boilerplate (no generation)

Word-count targets below are read directly off the reference template's own
prose (each templated section is a sentence or two of boilerplate around the
pinned/generated content) — see `docs/intake-schema.md` "Generated-section
length targets" for the full rationale and the business cost of over-length
sections (edge case: "Generated sections run long; client skim reading
suffers").
"""

from app.models.proposal import Proposal, SectionKey

# Sections a full-generation job must call Claude for. Every other SectionKey
# keeps the template_default content intake_service.py already wrote —
# Introduction included, now that it's pinned-only (no free generation).
GENERATED_SECTION_KEYS: frozenset[SectionKey] = frozenset(
    {SectionKey.PROPOSED_SOLUTION, SectionKey.DELIVERABLES}
)

# Word targets per generated section — deliberately tight, matching the
# reference template's own brevity (a client skims a proposal; padding costs
# edit time later, not less). Passed into the prompt as explicit guidance.
WORD_TARGETS: dict[SectionKey, str] = {
    SectionKey.PROPOSED_SOLUTION: "120-200 words",
    SectionKey.DELIVERABLES: "60-120 words",
}

# Fixed house tone derived from the reference proposal template (CLAUDE.md /
# architecture.md §4 point 2). Stored once, layered under any future per-call
# salesperson instruction for regeneration — never replaced by it.
HOUSE_TONE = (
    "Confident, professional, and client-focused sales writing. Clear, "
    "concrete, and brief — the client skim-reads this, so favor short "
    "sentences over qualifying clauses. No exclamation points, no marketing "
    "hyperbole, no emoji. Never pad to sound thorough; a short, precise "
    "section beats a long generic one."
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
        "- Stay within the word target given for this section. Going over "
        "it is treated as a failure to follow instructions, not thoroughness "
        "— the client skim-reads this, and a salesperson has to manually "
        "trim anything over target before it can go out.\n"
        "- Output only the section's prose. No heading, no markdown, no "
        "preamble like \"Here is the section\".\n"
    )


def build_user_prompt(proposal: Proposal, section_key: SectionKey) -> str:
    if section_key not in GENERATED_SECTION_KEYS:
        raise ValueError(
            f"build_user_prompt called for a non-generated section: {section_key.value}"
        )

    facts = _canonical_facts_block(proposal)
    word_target = WORD_TARGETS[section_key]

    if section_key == SectionKey.PROPOSED_SOLUTION:
        task = (
            "Write the 'recommended approach' narrative for the Proposed "
            "Solution section — do not restate the project scope verbatim "
            "(it is shown to you for context only and is inserted separately "
            "above your text). Explain, in 1-2 tight paragraphs, the "
            f"approach recommended to address the project scope and goals "
            f"given. Target length: {word_target}."
        )
    elif section_key == SectionKey.DELIVERABLES:
        task = (
            "Write the Deliverables section. The raw sales notes on "
            "recommended services above fold services and deliverables "
            "together — separate and expand them into a clear list of "
            "concrete deliverables the client will receive, one per line, "
            f"as short phrases (not full sentences). Target length: "
            f"{word_target}."
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
    — deliverables is pure generated content.
    """
    generated_text = generated_text.strip()
    if section_key == SectionKey.PROPOSED_SOLUTION:
        return f"{pinned_content}\n\n{generated_text}"
    return generated_text
