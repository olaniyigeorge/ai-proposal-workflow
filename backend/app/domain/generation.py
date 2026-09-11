"""
Full-proposal generation — assembling what Claude needs to write the sections
that are not pure pinned-fact passthroughs. Pure domain logic: no I/O, no
anthropic import (that lives in adapters/claude_client.py).

Per `docs/reference/proposal-template.md` (the actual reference template —
see `docs/intake-schema.md` "Proposal sections"), every one of the six
template sections now goes through a generation call (revised 2026-09-11 —
see docs/edge-cases.md "Pinned sections read as pasted-in fragments, not
part of one document"):

  1. Introduction          — generated: paraphrases `client_needs_summary` +
                              `goals_and_objectives` into clean, professional
                              prose rather than quoting the client's raw
                              intake answers verbatim (see below)
  2. Proposed Solution     — `project_scope` verbatim + generated `recommended_approach`
  3. Deliverables          — generated from `recommended_services`
  4. Timeline              — `proposed_timeline` verbatim, prefixed by a short
                              generated lead-in so it reads as prose, not a
                              pasted date range
  5. Pricing               — `estimated_pricing` verbatim (currency-normalized,
                              see `normalize_pricing_display`), prefixed by a
                              short generated lead-in
  6. Next Steps            — fully generated closing/CTA paragraph (no
                              per-proposal facts to pin here beyond what's
                              already in the canonical facts block)

Timeline and Pricing follow the same "pin the fact, generate the frame
around it" shape as Proposed Solution — the exact dates/numbers are never
something Claude is asked to restate, only to introduce, so a regeneration
can change tone/wording without any risk of drifting the number a client
will actually be quoted.

**Introduction was pinned-only until 2026-09-10** (client_needs_summary and
goals_and_objectives inserted verbatim into the reference template's fixed
frame — see docs/edge-cases.md "Generated sections run long" for the
original reasoning: zero hallucination risk, one fewer Claude call). That
traded away too much: a client's raw form answers can carry bad grammar,
run-on phrasing, or unclear wording, and that went straight into a
client-facing document unedited. Introduction is now generated like Proposed
Solution/Deliverables, with an explicit instruction to paraphrase — not
invent — so wording gets cleaned up without the model adding needs, goals,
or commitments the client never stated. See docs/edge-cases.md "Client's raw
intake wording reached the client verbatim via the pinned Introduction".

Word-count targets below are read directly off the reference template's own
prose (each templated section is a sentence or two of boilerplate around the
pinned/generated content) — see `docs/intake-schema.md` "Generated-section
length targets" for the full rationale and the business cost of over-length
sections (edge case: "Generated sections run long; client skim reading
suffers").
"""

import re

from app.models.proposal import Proposal, SectionKey

# Every section now has a Claude call in it somewhere — either fully
# generated (Introduction, Deliverables, Next Steps) or a generated lead-in
# wrapped around a pinned/verbatim fact block (Proposed Solution, Timeline,
# Pricing). See module docstring for the 2026-09-11 revision.
GENERATED_SECTION_KEYS: frozenset[SectionKey] = frozenset(SectionKey)

# Word targets per generated section — deliberately tight, matching the
# reference template's own brevity (a client skims a proposal; padding costs
# edit time later, not less). Passed into the prompt as explicit guidance.
WORD_TARGETS: dict[SectionKey, str] = {
    SectionKey.INTRODUCTION: "60-100 words",
    SectionKey.PROPOSED_SOLUTION: "120-200 words",
    SectionKey.DELIVERABLES: "60-120 words",
    SectionKey.TIMELINE: "15-30 words",
    SectionKey.PRICING: "15-30 words",
    SectionKey.NEXT_STEPS: "40-70 words",
}

_CURRENCY_SYMBOLS = ("$", "€", "£", "¥")


def normalize_pricing_display(raw: str) -> str:
    """Prefix a bare number with `$` so pricing reads unambiguously as a
    dollar figure in the client-facing document, without double-prefixing a
    value that already carries a currency symbol.

    Deliberately conservative: only prefixes the *whole field* once, and
    only when the field, trimmed, starts with a digit — e.g. "16000 flat
    fee" -> "$16000 flat fee", but "$16,000 up front, 5000 on completion"
    (already has a symbol) and "Custom, based on final scope" (doesn't start
    with a number) are both left untouched. This intentionally does not try
    to find and prefix every individual number embedded in free text (e.g.
    a second bare number later in the same string) — `estimated_pricing` is
    unstructured free text from the intake form, not itemized line items,
    and guessing which embedded numbers are prices risks corrupting ones
    that aren't (a day count, a percentage). See docs/edge-cases.md.
    """
    stripped = raw.strip()
    if not stripped or any(symbol in stripped for symbol in _CURRENCY_SYMBOLS):
        return raw
    if re.match(r"^\d", stripped):
        return f"${stripped}"
    return raw

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
        "own paraphrase if a pinned fact block is appended after your text "
        "in this same section (you'll be told when that's the case) or "
        "already stated verbatim elsewhere in the proposal — focus on the "
        "narrative this section is asked for and let the pinned fact speak "
        "for itself.\n"
        "- This section is one part of a single proposal document the "
        "client reads start to finish, not a standalone note. Write it so "
        "it flows into the surrounding sections: don't repeat the section's "
        "own title in your text, don't use meta phrases like \"in this "
        "section\" or \"this document\", and don't re-greet or re-introduce "
        "the client if the section isn't the Introduction.\n"
        "- Stay within the word target given for this section. Going over "
        "it is treated as a failure to follow instructions, not thoroughness "
        "— the client skim-reads this, and a salesperson has to manually "
        "trim anything over target before it can go out.\n"
        "- Output only the section's prose. No heading, no markdown, no "
        "preamble like \"Here is the section\".\n"
    )


def _section_task_description(section_key: SectionKey, word_target: str) -> str:
    if section_key == SectionKey.INTRODUCTION:
        return (
            "Write the Introduction section: thank the client for their time "
            "and introduce this proposal, then summarize their stated needs "
            "(\"Client's stated needs\" below) and goals (\"Goals and "
            "objectives\" below) in clear, professional prose. The client's "
            "own wording may be informal, ungrammatical, or unclear — "
            "paraphrase it into clean prose rather than quoting it verbatim, "
            "correcting grammar and phrasing as you go. Do not add any need, "
            "goal, or commitment beyond what is stated in those two facts — "
            f"paraphrasing wording is in scope, inventing content is not. "
            f"Target length: {word_target}."
        )
    if section_key == SectionKey.PROPOSED_SOLUTION:
        return (
            "Write the 'recommended approach' narrative for the Proposed "
            "Solution section — do not restate the project scope verbatim "
            "(it is shown to you for context only and is inserted separately "
            "above your text). Explain, in 1-2 tight paragraphs, the "
            f"approach recommended to address the project scope and goals "
            f"given. Target length: {word_target}."
        )
    if section_key == SectionKey.DELIVERABLES:
        return (
            "Write the Deliverables section. The raw sales notes on "
            "recommended services above fold services and deliverables "
            "together — separate and expand them into a clear list of "
            "concrete deliverables the client will receive, one per line, "
            f"as short phrases (not full sentences). Target length: "
            f"{word_target}."
        )
    if section_key == SectionKey.TIMELINE:
        return (
            "Write a one-sentence lead-in for the Timeline section. The "
            "exact proposed timeline (dates/durations) is appended verbatim "
            "immediately after your text, so do not state, restate, or "
            "paraphrase any specific date, duration, or milestone yourself "
            "— just introduce that a timeline follows, in a way that flows "
            f"naturally from the section before it. Target length: {word_target}."
        )
    if section_key == SectionKey.PRICING:
        return (
            "Write a one- or two-sentence lead-in for the Pricing section. "
            "The exact estimated cost is appended verbatim immediately "
            "after your text, so do not state, restate, or paraphrase any "
            "specific number yourself. You may add a brief, standard note "
            "that pricing can be adjusted if the client's needs change "
            f"during the project. Target length: {word_target}."
        )
    if section_key == SectionKey.NEXT_STEPS:
        return (
            "Write the closing Next Steps section: invite the client to "
            "move forward (e.g. reviewing/signing an agreement and "
            "scheduling a kickoff), thank them, and invite questions. Do "
            "not invent a specific date, deliverable, or commitment beyond "
            f"what is already stated in the facts. Target length: {word_target}."
        )
    raise ValueError(f"No task description for section: {section_key.value}")


def build_user_prompt(proposal: Proposal, section_key: SectionKey) -> str:
    if section_key not in GENERATED_SECTION_KEYS:
        raise ValueError(
            f"build_user_prompt called for a non-generated section: {section_key.value}"
        )

    facts = _canonical_facts_block(proposal)
    word_target = WORD_TARGETS[section_key]
    task = _section_task_description(section_key, word_target)

    return f"{task}\n\nFacts:\n{facts}"


def _sibling_summary_block(proposal: Proposal, section_key: SectionKey) -> str:
    """Short context from every other section so a regenerated section doesn't
    contradict what the rest of the proposal already says (architecture.md §4
    point 3) — truncated summaries, not full text, to keep the call cheap and
    avoid the prompt growing unbounded as proposals grow. Numeric/factual
    consistency (pricing, dates, client name) is already guaranteed by the
    canonical facts layer regardless of this block — this is only a narrative
    consistency aid, so truncation losing a mid-sentence detail is an accepted
    limitation (see docs/edge-cases.md).
    """
    lines = []
    for section in proposal.sections:
        if section.section_key == section_key:
            continue
        collapsed = " ".join(section.content.split())
        summary = collapsed[:160] + ("…" if len(collapsed) > 160 else "")
        lines.append(f"- {section.title}: {summary}")
    return "\n".join(lines) if lines else "(no other sections yet)"


def build_regeneration_prompt(
    proposal: Proposal, section_key: SectionKey, instruction: str
) -> str:
    """User-turn prompt for a single-section regeneration call. Layers, per
    architecture.md §4: canonical facts (point 4) + sibling-section summaries
    (point 3) + the mandatory salesperson instruction (point 5) — the
    instruction is additive to the house tone already baked into
    build_system_prompt(), never a replacement for it (decisions #11).
    """
    if section_key not in GENERATED_SECTION_KEYS:
        raise ValueError(
            f"build_regeneration_prompt called for a non-generated section: {section_key.value}"
        )

    facts = _canonical_facts_block(proposal)
    word_target = WORD_TARGETS[section_key]
    task = _section_task_description(section_key, word_target)
    siblings = _sibling_summary_block(proposal, section_key)

    return (
        f"{task}\n\n"
        f"Facts:\n{facts}\n"
        "Other sections of this proposal, for consistency only — do not "
        f"repeat them, just don't contradict them:\n{siblings}\n\n"
        "The salesperson has asked for this specific change on top of the "
        f"house tone and task above:\n{instruction.strip()}"
    )


def pinned_prefix_for_section(proposal: Proposal, section_key: SectionKey) -> str:
    """For PROPOSED_SOLUTION, TIMELINE, and PRICING, the verbatim pinned fact
    block their final content is built around (see assemble_section_content)
    — always recomputed fresh from the live `Proposal` fields, never read
    back from a section's previous content, so a regeneration can never drift
    from the actual scope/timeline/price on file. For INTRODUCTION,
    DELIVERABLES, and NEXT_STEPS, which are pure generated content with no
    pinned fact block in the final output, this instead supplies the
    pre-generation placeholder shown in the section before Generate is first
    clicked. Single source of truth shared by intake_service.py (first
    assembly) and services/regeneration_service.py (every regeneration) so
    the two can never drift apart on the exact wording.
    """
    if section_key == SectionKey.INTRODUCTION:
        return (
            f"Needs: {proposal.client_needs_summary}\n"
            f"Goals: {proposal.goals_and_objectives}"
        )
    if section_key == SectionKey.PROPOSED_SOLUTION:
        return f"Scope:\n{proposal.project_scope}"
    if section_key == SectionKey.DELIVERABLES:
        return f"Services & Deliverables:\n{proposal.recommended_services}"
    if section_key == SectionKey.TIMELINE:
        return proposal.proposed_timeline
    if section_key == SectionKey.PRICING:
        return normalize_pricing_display(proposal.estimated_pricing)
    if section_key == SectionKey.NEXT_STEPS:
        return "1. Review and approve the proposal.\n2. Execute agreement.\n3. Schedule kickoff meeting."
    raise ValueError(f"No pinned prefix defined for section: {section_key.value}")


def assemble_section_content(section_key: SectionKey, pinned_content: str, generated_text: str) -> str:
    """Combine a section's pinned/verbatim fact block (if any) with Claude's
    generated text.

    - PROPOSED_SOLUTION: pinned scope first, generated approach after —
      established pattern, unchanged.
    - TIMELINE, PRICING: generated lead-in first, then the pinned fact
      verbatim — the fact is never something Claude was asked to restate
      (see `_section_task_description`), so it always reads as "here's the
      frame, here's the number" rather than risking the model paraphrasing
      a date or price.
    - INTRODUCTION, DELIVERABLES, NEXT_STEPS: pure generated content: the
      `pinned_content` argument is only the pre-generation placeholder, not
      part of the final assembled section.
    """
    generated_text = generated_text.strip()
    if section_key == SectionKey.PROPOSED_SOLUTION:
        return f"{pinned_content}\n\n{generated_text}"
    if section_key in (SectionKey.TIMELINE, SectionKey.PRICING):
        return f"{generated_text}\n\n{pinned_content}"
    return generated_text
