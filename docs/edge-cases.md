# Edge Cases Log

Working log of edge cases discovered while building this project — the "gotchas" that aren't obvious from `CLAUDE.md`/`docs/architecture.md`/`docs/system-flow.md`/`docs/decisions.md` alone, but shaped an implementation choice. Newest first. When an edge case changes a documented decision, update the source doc (`decisions.md`, `intake-schema.md`, etc.) too — this file explains *why*, the source docs state *what's current*.

---

## 2026-09-10 — A flaky Claude call must not burn one of the salesperson's 3 regeneration attempts

**The gap (business view):** The 3-attempt cap (decisions #13) exists to force a directed, converging regeneration rather than aimless retries — but if a transient failure (rate limit, timeout, a momentary API outage) eats one of only 3 attempts, the salesperson is punished for infrastructure flakiness, not their own instruction quality. Losing a third of their budget to something entirely outside their control is exactly the kind of "the tool wasted my time" moment that kills trust in an AI feature, especially right when they're trying to get a proposal out the door.

**The fix (implemented 2026-09-10, Phase 4):** `ProposalSection.regeneration_count` — the value the 3-attempt cap actually checks — is only incremented in `regeneration_service.regenerate_section()` *after* `generate_text()` succeeds. A `ClaudeGenerationError` (rate limit, timeout, refusal, empty response) is caught, recorded in `regeneration_log` with `outcome: "failed"` and the error message (so the salesperson can still see it happened and roughly why), and the function returns without touching `regeneration_count`, `content`, `version`, or `approval_status` — the section is left exactly as it was, per CLAUDE.md's "a failed call must leave the prior state intact."

**Where it lives:** `backend/app/services/regeneration_service.py` (`regenerate_section`), test `test_regeneration_job_failure_does_not_burn_cap_attempt`.

**Open follow-up:** a salesperson who mistypes an instruction (e.g. a typo that produces a *technically successful* but useless Claude response) still burns a real attempt — there's no distinction between "Claude failed to respond" and "Claude responded but the salesperson didn't like it," nor should there be; only genuine call failures are free retries by design. The escape hatch for a cap-exhausted section is unchanged and unlimited: manual editing (Phase 3) has no attempt cap.

---

## 2026-09-10 — Concurrent writers can silently clobber each other's section edits or regenerations

**The gap (business view):** Nothing in Phase 3 or Phase 4 detects two people (or one person in two tabs) changing the same section at nearly the same time. If salesperson A edits a section by hand while salesperson B's regeneration job for that same section is still in flight, whichever write commits last simply overwrites the other with no warning — the loser's work vanishes without any error, undo, or record that a conflict even happened. This is exactly the "optimistic concurrency" risk architecture.md §6 already named as a general requirement ("use a version/updated-at check... surface a conflict rather than losing data"), now concrete: Phase 4 introduced a second, *asynchronous* writer (the regeneration background job) racing against Phase 3's synchronous edit endpoint on the same row, which is a materially higher-probability collision than two synchronous edits ever were, since the regeneration job can be in flight for several seconds while its target section stays fully editable in the UI the whole time.

**The fix:** not implemented — both `update_section_content()` and `regenerate_section()` read-modify-write a `ProposalSection` with no version check, so this remains a real, live gap, not a theoretical one. Flagged here explicitly rather than silently deferred, per architecture.md §6.

**Where it lives:** `backend/app/services/proposal_service.py::update_section_content`, `backend/app/services/regeneration_service.py::regenerate_section` — both would need to compare an expected `version` (or `updated_at`) against the current row inside the same transaction and raise a conflict (409) instead of writing, if a caller's read is stale.

**Open follow-up:** given the single-tenant, single-role, no-ownership-restriction design (decisions #21), the realistic collision is "two tabs of the same salesperson" or "salesperson edits while their own earlier regeneration for that section is still running" more often than two different salespeople — worth confirming whether that narrower risk still justifies the extra complexity of version-checked writes before building it. Note `RegenerateSectionButton`'s `isRegenerating` state only disables *its own* trigger while a job is in flight — it does not currently disable the sibling `SectionEditor`'s "Edit Content" button for the same section (the two components don't share state), so a salesperson can still start a manual edit on a section while that section's own regeneration job is still running. A shared "this section is busy" flag between the two components would close that specific window cheaply, without needing full version-checked writes.

---

## 2026-09-10 — Truncated sibling summaries could still let a regenerated section drift narratively

**The gap (business view):** Per architecture.md §4 point 3, a regeneration call includes short summaries of every other section (not full text) so the new text doesn't contradict the rest of the proposal. Those summaries are a blunt character-count truncation (`content[:160]`) of each sibling section's actual content, not a real summary — if a sibling's most relevant detail happens to fall after character 160, the regenerated section never sees it and could still narratively drift (e.g. Deliverables lists something Proposed Solution's cut-off tail actually promised). The canonical facts layer (client name, dates, pricing) is unaffected — those are passed verbatim regardless — so this is a narrative-consistency risk only, not a numeric/factual one.

**The fix (accepted, not eliminated):** architecture.md §4 point 8 explicitly marks a real consistency pass (a secondary check that flags contradictions) as optional/deferred, and this project has only two sections that are ever AI-generated (Proposed Solution, Deliverables — see `docs/edge-cases.md` "Generated sections run long"), which narrows the realistic collision surface considerably versus the general N-section case the architecture doc was written for. Truncation was chosen over a real summarization call to avoid doubling Claude spend (one summarization call per sibling, per regeneration) for a low-probability, low-severity failure mode.

**Where it lives:** `backend/app/domain/generation.py::_sibling_summary_block`.

**Open follow-up:** if this turns out to cause visible contradictions in practice, the cheapest fix is raising the truncation length before reaching for a real summarization call or a consistency-check pass — no evidence yet that 160 characters is actually too short for either of the two generated sections' summaries.

---

## 2026-09-09 — Duplicate intake beyond webhook retries

**The gap:** The original idempotency key (`hash(timestamp + email_address)`, `docs/decisions.md` #4) only protects against *n8n retrying a failed delivery of the same Sheet row* — the `Timestamp` column is identical on a retry because it's the same row. It does **not** protect against a human genuinely submitting the same request twice (e.g. a salesperson re-filling the Google Form for the same client because they weren't sure the first one went through, or the client verbally re-requesting the same thing). That second submission gets a *new* `Timestamp` from Google Forms, so the old key treats it as a brand-new proposal — duplicate `Proposal` rows for what is substantively one request.

**The fix:** Idempotency key is now `hash(company_name + normalize(project_scope) + respondent_email)` — no `timestamp` in the key at all. Rationale: a true duplicate (whether a retry or a re-submission) shares these three fields; a genuinely different request from the same person on the same day will describe a different `project_scope`. `normalize()` = lowercase, trim, collapse internal whitespace, strip trailing punctuation, so a re-typed submission with cosmetic differences (extra space, re-cased text, trailing period) still dedupes.

**Where it lives:**
- Computed in FastAPI: `compute_intake_key()` / `normalize_text()` in `backend/app/services/intake_service.py`.
- n8n's Code node does **not** compute the hash — it only does Sheet-column → canonical-key translation (per the existing n8n/FastAPI boundary in `CLAUDE.md`). Keeping the hash algorithm in one place (Python) avoids a second implementation drifting from the first.
- Tests: `test_intake_idempotency_survives_resubmission_with_new_timestamp`, `test_intake_idempotency_ignores_cosmetic_differences` in `backend/tests/test_intake.py`.
- Doc updates: `docs/decisions.md` #4 (marked revised), `docs/intake-schema.md` "Idempotency key" section.

**Open follow-up:** `project_scope` is free text from a Google Form long-answer field — two submissions describing the *same* project in genuinely different wording (not just whitespace/casing) will still fork into two proposals. Current normalization only catches cosmetic differences, not semantic ones. Revisit if this turns out to happen in practice (e.g. fuzzy-match or a Claude-based dedupe check before create) — no evidence yet that it's a real problem, so not building it preemptively.

---

## 2026-09-09 — Generated sections run long; client skim reading suffers

**The gap (business view):** A proposal that reads like a white paper gets skimmed and set aside. Long AI sections look thorough but bury the client's actual problem and your answer in padding. The salesperson then spends edit time cutting, not improving — negating the time save Phase 2 was supposed to deliver. Original prompts had no length target at all (asked for "2-3 paragraphs" per section with no word ceiling), and `CLAUDE_MAX_TOKENS` was set to 2048 — enough headroom for Claude to write several times longer than the reference template ever does.

**The fix (implemented 2026-09-09):** `docs/reference/proposal-template.md` (the actual PRD reference, now on disk) shows every section as one to two short sentences of boilerplate around a pinned fact — there was never a "few paragraphs per section" target to begin with. Reset to match: `WORD_TARGETS` in `backend/app/domain/generation.py` sets 120-200 words for Proposed Solution's generated narrative and 60-120 words for Deliverables, stated explicitly in the prompt ("going over it is treated as a failure to follow instructions, not thoroughness"), and `CLAUDE_MAX_TOKENS` dropped from 2048 to 500. Also found while re-reading the template: **Introduction has no generated placeholder in it at all** — it's fixed boilerplate wrapping `client_needs_summary` and `goals_and_objectives` verbatim — so it's been moved out of the Claude-call path entirely and assembled at intake like Timeline/Pricing. Net effect: one fewer Claude call per proposal (lower cost, faster generation, zero hallucination risk on that section) plus tighter output on the two sections that do need a model call.

**Where it lives:** `backend/app/domain/generation.py` (`WORD_TARGETS`, `GENERATED_SECTION_KEYS` now excludes Introduction), `backend/app/services/intake_service.py` (Introduction content assembled from template boilerplate), `backend/app/core/config.py` (`CLAUDE_MAX_TOKENS = 500`), tests in `backend/tests/test_generation.py`. Word-count badge in the UI (Phase 3/4 SectionEditor) is still the open UI-side follow-up below.

**Open follow-up:** the visible word-count badge next to each section (so the salesperson sees at a glance which sections still need trimming after an edit) is still Phase 3/4 UI work, not yet built. If Claude consistently exceeds the new targets in practice, tune the prompt per section — treat as prompt-iteration work, not a code bug. Cap regeneration at 3 (already decided #13) so a "shorten this" instruction can't infinite-loop.

---

## 2026-09-09 — Email sent without a human reviewing the draft

**The gap (business view):** If "send" fires automatically from DOCUMENT_READY or APPROVED, a wrong recipient, a stale link, a generic email body, or a pricing error in the body goes out before anyone sees it. For a proposal that's a sales document, a bad send is a lost opportunity or a damaged first impression — higher cost than a delayed send.

**The fix (proposed):** Email draft is composed (storage link embedded) but not sent until the salesperson reviews and confirms it in the UI. The send button is disabled until the draft is reviewed. Delivery status (sent/bounced/failed) tracked in DeliveryRecord as already planned (decisions #17). This is a Phase 7 change: the "review email draft" step sits between DOCUMENT_READY and DELIVERING. See `decisions.md` #16 follow-up.

**Where it lives:** Phase 7 delivery service + UI (email draft review component). Storage: Supabase Storage default; link embedded in email body, not attachment.

**Open follow-up:** confirm whether the email body is templated (house tone, project-specific merge fields) or fully free-form per send. Templated + editable is the sweet spot — a starting draft the salesperson tweaks, not a blank box and not a locked text.

---

## 2026-09-09 — Human edits lost when a section is regenerated without warning

**The gap (business view):** A salesperson spends 10 minutes tightening a section's wording, then hits regenerate (or a background job does), and the edit vanishes — the section goes back to the AI version. The time spent editing is wasted and the salesperson loses trust in the edit feature. This is the highest-friction failure mode in the review flow because it punishes the exact action (editing) that's supposed to be the value add.

**The fix (implemented 2026-09-10, Phase 4):** `RegenerateSectionButton` (`web-app/components/proposals/RegenerateSectionButton.tsx`) shows a `window.confirm` warning before submitting a regenerate call against any section whose `content_origin` is `human_edited` or `human_edited_after_generation` — "this section has manual edits — regenerating will replace them, this cannot be undone." The 3-attempt cap (decisions #13) limits how often this can happen per section. Sibling sections are never touched by a single-section regenerate (CLAUDE.md constraint; covered by `test_regeneration_job_success_updates_only_targeted_section`).

**Where it lives:** `web-app/components/proposals/RegenerateSectionButton.tsx` (confirm dialog), `backend/app/domain/content_origin.py` (the origin-flip rules this confirmation is warning about).

**Open follow-up — this guard is UI-only, not backend-enforced.** The FastAPI endpoint (`POST /proposals/{id}/sections/{key}/regenerate`) does not itself require any confirmation or check prior content_origin before overwriting — "hiding a button isn't access control" (CLAUDE.md) technically doesn't apply here since this isn't a security boundary, but it does mean a second frontend, a script, or a direct API call bypasses the warning entirely and silently destroys the human edit. If a second client ever calls this API, revisit whether the backend should require an explicit `confirm_overwrite: true` flag when `content_origin` is already human-touched, rather than relying on any one frontend to ask.

---

## 2026-09-09 — Salesperson attribution breaks when the client fills the form

**The gap (business view):** The Google Form can be filled by the salesperson OR the client. `salesperson_name` is free text — if the client types their own name, a different spelling, or leaves it blank, string-matching it to a `User` account misassigns the proposal or leaves it unassigned. The wrong salesperson (or nobody) ends up reviewing a proposal that's sitting in the queue, delaying revenue. Worse, requiring the field at all forces a discovery call to happen before intake — the exact friction step self-serve clients don't need.

**The fix (implemented 2026-09-09):** `salesperson_name` is now optional end-to-end — `IntakePayload.salesperson_name: Optional[str]`, the `proposals.salesperson_name` DB column is nullable (migration `209e98a651b7`), and a blank/whitespace Sheet cell is normalized to `NULL` ("unassigned") by a Pydantic validator rather than stored as a literal empty string. This is a deliberate tradeoff: it removes attribution-at-intake in exchange for removing the discovery-call requirement entirely — a client with an existing form can self-serve straight into the pipeline, shortening the sales cycle. The alternative (exact-match against `User.name`) was rejected — it still misassigns on any spelling difference and does nothing for the "client filled it, no salesperson exists yet" case, which is now the common path this unblocks. Assignment happens after intake via a manual claim/assign step in the review queue — not attempted automatically. See `decisions.md` #20 (now ✅).

**Where it lives:** `backend/app/schemas/intake.py` (`Optional[str]` + `blank_salesperson_name_is_unassigned` validator), `backend/app/models/proposal.py` (nullable column), `backend/migrations/versions/209e98a651b7_make_salesperson_name_nullable.py`, `backend/app/schemas/proposal.py` (response models), tests in `backend/tests/test_intake.py`.

**Open follow-up:** the claim/assign UI + service itself doesn't exist yet — needed before/alongside Phase 5 approval (approval needs an actor). Auto-assignment criteria (round-robin, territory, current load) are explicitly deferred — manual claim is the only mechanism for now, and that's a real ongoing labor cost worth revisiting once proposal volume makes manual triage slow. Confirm whether Supabase Auth users are the actor model before adding a separate `User` table.

---

## 2026-09-09 — Regeneration loses the salesperson's instruction context across attempts

**The gap (business view):** A salesperson regenerates a section 2–3 times to get it right, each time typing a fresh instruction from memory ("more formal", "shorter", "focus on ROI"). There's no record of what they asked on previous attempts, so they repeat themselves, refine by guesswork, or give up after the cap. The 3-attempt cap (#13) becomes frustrating rather than a useful constraint — and the salesperson can't tell whether the last regeneration actually addressed what they meant. For a creative-writing task that's meant to converge, losing the instruction trail per section wastes attempts and degrades the output.

**The fix (implemented 2026-09-10, Phase 4):** `ProposalSection.regeneration_log` (JSON column, migration `8277db7b3a4f`) — an append-only list, one entry per regeneration attempt: `{instruction, attempted_at, outcome, resulting_version | error}`. `RegenerateSectionButton` renders the full history above the instruction textarea whenever a section already has attempts, each one tagged succeeded/failed. The cap (3) counts against the section's `regeneration_count`, not the log length, so a failed attempt still shows in the trail (see the "failed regeneration must not burn a cap attempt" entry below) without spending one of the 3 real tries.

**Where it lives:** `backend/app/models/proposal.py` (`regeneration_log` column), `backend/app/services/regeneration_service.py` (appends an entry on both success and failure), `backend/app/schemas/proposal.py` (`RegenerationLogEntry`), `web-app/components/proposals/RegenerateSectionButton.tsx` (renders it). Tests: `test_regeneration_job_success_updates_only_targeted_section`, `test_regeneration_job_failure_does_not_burn_cap_attempt`.

**Resolved follow-up (decisions #13b):** append-only, no edit/delete — matches "cleaner audit" over "salesperson's editable notes," since the log records what was actually *sent* to Claude, not a scratchpad. If a salesperson wants to revise their intent, that's simply their next attempt's instruction.

---

## YYYY-MM-DD — Short title

```
## YYYY-MM-DD — Short title

**The gap:** What broke / what wasn't handled, concretely (an input, a sequence of actions).

**The fix:** What was changed and why this approach over alternatives.

**Where it lives:** Code, tests, and doc locations touched.

**Open follow-up:** Anything still not handled, so it doesn't get silently forgotten.
```
