# Edge Cases Log

Working log of edge cases discovered while building this project — the "gotchas" that aren't obvious from `CLAUDE.md`/`docs/architecture.md`/`docs/system-flow.md`/`docs/decisions.md` alone, but shaped an implementation choice. Newest first. When an edge case changes a documented decision, update the source doc (`decisions.md`, `intake-schema.md`, etc.) too — this file explains *why*, the source docs state *what's current*.

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

**The gap (business view):** A proposal that reads like a white paper gets skimmed and set aside. Long AI sections look thorough but bury the client's actual problem and your answer in padding. The salesperson then spends edit time cutting, not improving — negating the time save Phase 2 was supposed to deliver. No length target exists in the schema or prompt today.

**The fix (proposed):** Set target word ranges per section (see `intake-schema.md` §"Generated-section length targets") and feed them into the generation prompt as guidance, not hard caps — "Introduction: ~100 words, one paragraph." Add a visible word-count badge next to each section in the UI so the salesperson sees at a glance which sections need trimming. Cap regeneration at 3 (already decided #13) so "shorten" instructions don't infinite-loop.

**Where it lives:** generation prompt (Phase 2 service), UI word-count badge (Phase 3/4 SectionEditor), regenerate instruction prefill suggestions (Phase 4). No schema change.

**Open follow-up:** if Claude consistently exceeds the targets for a given section type, the prompt needs tuning per section — treat as prompt-iteration work, not a code bug.

---

## 2026-09-09 — Email sent without a human reviewing the draft

**The gap (business view):** If "send" fires automatically from DOCUMENT_READY or APPROVED, a wrong recipient, a stale link, a generic email body, or a pricing error in the body goes out before anyone sees it. For a proposal that's a sales document, a bad send is a lost opportunity or a damaged first impression — higher cost than a delayed send.

**The fix (proposed):** Email draft is composed (storage link embedded) but not sent until the salesperson reviews and confirms it in the UI. The send button is disabled until the draft is reviewed. Delivery status (sent/bounced/failed) tracked in DeliveryRecord as already planned (decisions #17). This is a Phase 7 change: the "review email draft" step sits between DOCUMENT_READY and DELIVERING. See `decisions.md` #16 follow-up.

**Where it lives:** Phase 7 delivery service + UI (email draft review component). Storage: Supabase Storage default; link embedded in email body, not attachment.

**Open follow-up:** confirm whether the email body is templated (house tone, project-specific merge fields) or fully free-form per send. Templated + editable is the sweet spot — a starting draft the salesperson tweaks, not a blank box and not a locked text.

---

## 2026-09-09 — Human edits lost when a section is regenerated without warning

**The gap (business view):** A salesperson spends 10 minutes tightening a section's wording, then hits regenerate (or a background job does), and the edit vanishes — the section goes back to the AI version. The time spent editing is wasted and the salesperson loses trust in the edit feature. This is the highest-friction failure mode in the review flow because it punishes the exact action (editing) that's supposed to be the value add.

**The fix (proposed):** content_origin tracking (already in schema: `human_edited`, `human_edited_after_generation`) gates regeneration. Regenerating a `human_edited` section requires explicit confirmation in the UI ("this section has manual edits — regenerate will replace them"). The 3-attempt cap (decisions #13) limits how often this can happen per section. Sibling sections must not be touched by a single-section regenerate (CLAUDE.md constraint) — that protects the rest of the proposal from collateral damage.

**Where it lives:** already partially in schema + transition rules; the UI confirmation dialog is the missing piece in Phase 4 (RegenerateSectionButton).

**Open follow-up:** confirm whether regenerating a human-edited section should auto-set content_origin back to `ai_generated` or to `human_edited_after_generation` — the latter preserves the record that a human touched it before the regenerate, which is useful for audit. Current enum has both; pick one and document it.

---

## 2026-09-09 — Salesperson attribution breaks when the client fills the form

**The gap (business view):** The Google Form can be filled by the salesperson OR the client. `salesperson_name` is free text — if the client types their own name or a different spelling, string-matching it to a `User` account misassigns the proposal or leaves it unassigned. The wrong salesperson (or nobody) ends up reviewing a proposal that's sitting in the queue, delaying it.

**The fix (proposed):** Defer to a manual "claim/assign" step in the review queue as the default fallback (decisions #20, open). Until resolved, a proposal with an unrecognised `salesperson_name` shows as "unassigned" in the list with a claim action, rather than being silently misassigned. Phase 3 doesn't need this yet (no mutation endpoints), but any ownership-gated action after Phase 3 needs it.

**Where it lives:** decisions.md #20 (open), future claim/assign UI + service. No schema change needed yet — `salesperson_name` stays free text; a separate `assigned_to` FK to `users` (when that table exists) is the likely resolved shape.

**Open follow-up:** confirm the User table exists / is planned before Phase 5 (approval needs an actor). If Supabase Auth users are the actor model, the `User` entity may not need a separate table — confirm before adding one.

---

## 2026-09-09 — Regeneration loses the salesperson's instruction context across attempts

**The gap (business view):** A salesperson regenerates a section 2–3 times to get it right, each time typing a fresh instruction from memory ("more formal", "shorter", "focus on ROI"). There's no record of what they asked on previous attempts, so they repeat themselves, refine by guesswork, or give up after the cap. The 3-attempt cap (#13) becomes frustrating rather than a useful constraint — and the salesperson can't tell whether the last regeneration actually addressed what they meant. For a creative-writing task that's meant to converge, losing the instruction trail per section wastes attempts and degrades the output.

**The fix (proposed):** The regeneration endpoint (Phase 4) supports a per-section regeneration-suggestion log: each regeneration call records the instruction supplied + a short note/context the salesperson optionally attaches, so the UI can show the attempt history for that section ("attempt 1: 'make more formal' → attempt 2: 'shorten, keep pricing facts' → attempt 3: 'lead with the ROI line'"). This is not auto-generated content — it's the salesperson's own instruction trail, surfaced so they don't lose what they're trying to say across attempts. The cap (3) still applies; the log just makes each attempt informed rather than amnesiac. Storage: a small per-section list on the section (or a separate regenerate-history table) — confirm schema shape in Phase 4. The instruction itself is already mandatory per #13; the log is the visibility layer on top.

**Where it lives:** Phase 4 regeneration service + endpoint (records instruction per call), Phase 4/regenerate UI (shows attempt history + current instruction). No schema change required if stored as a JSON list on ProposalSection; a separate table if queryability/audit matters. Decide in Phase 4.

**Open follow-up:** whether the suggestion log is editable/deletable by the salesperson (likely yes — it's their notes) vs append-only (cleaner audit). Default: append-only for the instruction that was actually sent, editable note field optional — confirm before building.

---

## YYYY-MM-DD — Short title

```
## YYYY-MM-DD — Short title

**The gap:** What broke / what wasn't handled, concretely (an input, a sequence of actions).

**The fix:** What was changed and why this approach over alternatives.

**Where it lives:** Code, tests, and doc locations touched.

**Open follow-up:** Anything still not handled, so it doesn't get silently forgotten.
```
