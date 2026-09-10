# Canonical Intake Schema & Proposal Template Mapping

Reference source: PRD "Proposal Intake Fields" + reference Google Form (`https://forms.gle/5GXAVU92sqJf3EAKA`), the live Sheet's column headers, and the PRD "Proposal Template". This file is the single place all three (Form/Sheet/API/Template) get reconciled — update it first whenever a form question changes, then update the n8n mapping, then let FastAPI's Pydantic model be the enforcement backstop (see `decisions.md` #5).

## Field mapping

| Canonical key (FastAPI/Pydantic) | Sheet column header (as observed) | PRD field | Notes |
|---|---|---|---|
| *(none — see idempotency key below)* | `Timestamp` | not in PRD field table | Auto-stamped by Google Forms at submission. Not client data — used only for the idempotency key. |
| *(none — see attribution, decisions #20)* | `Email Address` | not in PRD field table | Auto-captured respondent email — may be the salesperson's or the client's, depending on who filled the form. Do not assume this is the salesperson. |
| `client_name` | `Client Name` | Client Name | |
| `client_email` | `Client Email` | Client Email | Used for delivery (Q16) — distinct from the respondent `Email Address` above. |
| `company_name` | `Company Name` | Company Name | |
| `date_of_call` | `Date Of Call` | Date of Call | Sheet header differs in casing/spacing from PRD's suggested key — n8n mapping must normalize this. |
| `salesperson_name` | `Salesperson Name` | Salesperson Name | **Optional** — free text when present, `NULL`/unassigned when the client filled the form directly or left it blank (decisions #20, resolved 2026-09-09). Never string-match this to a `User`. |
| `client_needs_summary` | `Summary of Client's Needs` | Summary of Client's Needs | |
| `project_scope` | `Project Scope` | Project Scope | |
| `goals_and_objectives` | `Goals & Objectives` | Goals and Objectives | Sheet uses `&`, PRD table says "and" — cosmetic but must be handled explicitly in the n8n mapping, not assumed. |
| `recommended_services` | `Recommended Services/Deliverables` | Recommended Services or Deliverables | Note the sheet header folds "Deliverables" into this column name — see template mismatch below. |
| `proposed_timeline` | `Proposed Timeline` | Proposed Timeline | |
| `estimated_pricing` | `Estimated Pricing` | Estimated Pricing | |

## Idempotency key

`intake_key = hash(company_name + normalize(project_scope) + respondent_email)` — computed by FastAPI (`compute_intake_key` in `intake_service.py`) from three canonical fields, **not** `timestamp`. `normalize()` lowercases, trims, collapses internal whitespace, and strips trailing punctuation so re-typed casing/spacing doesn't fork the key. Enforced as a DB unique constraint on `IntakeSubmission`; `POST /intake` is an upsert (return the existing `Proposal` id on conflict) so both n8n retries *and* a salesperson resubmitting the same form are safe no-ops. Supersedes the original `hash(timestamp + email_address)` scheme, which only caught the former. See `decisions.md` #4 and `edge-cases.md` "Duplicate intake beyond webhook retries".

## Schema drift (form/Sheet changing out from under n8n's mapping)

This file is the source of truth and must be updated *first* whenever a Google Form question changes — before touching the n8n Code node, before assuming FastAPI's Pydantic model needs to change. Three drift shapes:

- **A required field is renamed/removed on the form** → the Sheet column n8n's Code node looks for disappears → the Code node's own required-field check throws before the HTTP call is even made. **Real gap:** that throw has no `onError` routing in n8n today, so it fails the execution silently rather than reaching n8n's `Alert` node or FastAPI's `INTAKE_SCHEMA_DRIFT` logging (`backend/app/main.py`) — see `edge-cases.md` for the two options being weighed (wire the Code node's error output, or have it forward instead of throw so the 422 path is the single detector).
- **A new field is added to the form** → n8n's Code node passes the extra column through under its raw (unmapped) header rather than dropping it, so it hits `IntakePayload`'s `extra="forbid"` and 422s — caught, both by n8n's `Alert`-node error branch (once wired to a real channel) and by the backend's `INTAKE_SCHEMA_DRIFT` log tag.
- **A question's wording changes but the column header/canonical key doesn't** → completely undetectable technically; a semantic drift, not a structural one. Process fix only (update this doc → n8n mapping → confirm against Pydantic) — no code or log tag will ever catch this.

FastAPI's 422 (logged as `INTAKE_SCHEMA_DRIFT`) plus a bad/missing shared secret (logged as `INTAKE_AUTH_FAILED`) are the structural backstops (decisions #5) — both independent of whether n8n's own alerting is wired for a given failure. See `edge-cases.md` for the full writeup and the one still-open gap.

## Template ≠ intake fields (must reconcile)

The reference proposal template uses two placeholders that do **not** exist in the intake schema:

| Template placeholder | Derived from | How |
|---|---|---|
| `{{recommended_approach}}` | `recommended_services` (+ `project_scope` for context) | Claude-synthesized narrative, not passed through verbatim — this is *generated* content, not a canonical fact. |
| `{{deliverables}}` | `recommended_services` | Same — the sheet folds "Deliverables" into one column with services; Claude needs to separate/expand it into a deliverables list for this section. |

Most of the rest of the template (`{{client_name}}`, `{{company_name}}`, `{{date_of_call}}`, `{{project_scope}}` in Proposed Solution, `{{proposed_timeline}}`, `{{estimated_pricing}}`) maps directly to a canonical intake field and is a **pinned fact** the generation prompt is constrained to reproduce verbatim (per `architecture.md` §4, item 4) — never left to the model to paraphrase, since these are exactly the numbers/dates/identifiers where drift would be a real business risk.

**`{{client_needs_summary}}` and `{{goals_and_objectives}}` are the one deliberate exception** (revised 2026-09-10 — see `edge-cases.md` "Client's raw intake wording reached the client verbatim via the pinned Introduction"): these are free-text narrative, not facts with a single correct value, and the client's own form-answer wording can carry bad grammar or unclear phrasing that shouldn't reach a client-facing document unedited. Introduction is generated (not pinned) specifically so Claude paraphrases these two fields into clean prose — explicitly instructed to paraphrase wording, never invent a need/goal the client didn't state.

## Proposal sections (from the reference template)

Informs decisions #8 — six sections, fixed order. Reference template now on disk at `docs/reference/proposal-template.md` — read it before touching generation prompts, since it settles exactly which sections are generated vs. pinned-only:

1. Introduction (generated — paraphrases `client_needs_summary` + `goals_and_objectives` into clean prose rather than quoting them verbatim; see the note above and `edge-cases.md`)
2. Proposed Solution (contains `project_scope` verbatim + generated `recommended_approach`)
3. Deliverables (generated from `recommended_services`)
4. Timeline (`proposed_timeline` verbatim)
5. Pricing (`estimated_pricing` verbatim)
6. Next Steps (static boilerplate — no per-proposal generation)

**Introduction**, **Proposed Solution**, and **Deliverables** call Claude (`GENERATED_SECTION_KEYS` in `backend/app/domain/generation.py`).

## Generated-section length targets

Set against `docs/reference/proposal-template.md` and `docs/reference/client-email-template.md` — both are notably short (each section is one to two sentences of boilerplate around a pinned fact; the whole email is ~10 lines). There is no "few paragraphs per section" target — that was an earlier assumption before the reference docs existed, and it's why an earlier version of Phase 2 produced sections several times longer than intended (see `docs/edge-cases.md`). Targets below are prompt guidance (`WORD_TARGETS` in `backend/app/domain/generation.py`) plus a visible word-count check in the UI, not hard schema caps.

| Section | Target length | Notes |
|---|---|---|
| Introduction | 60–100 words | Generated: thanks the client, then paraphrases `client_needs_summary`/`goals_and_objectives` into clean prose (not a verbatim quote of the client's own wording — see the note above). No pinned prefix survives into the final section text. |
| Proposed Solution | 120–200 words (generated portion only) | `project_scope` verbatim goes in above this (adds its own length on top, depending on the intake answer); the generated `recommended_approach` is 1-2 tight paragraphs, not a brainstorm dump. |
| Deliverables | 60–120 words | Short list, one line per deliverable. `recommended_services` expanded/formatted here — if it's already a clean list, generation just formats it, it doesn't inflate it. |
| Timeline | n/a — not generated | `proposed_timeline` verbatim, no generation. |
| Pricing | n/a — not generated | `estimated_pricing` verbatim, no generation. |
| Next Steps | n/a — not generated | Static boilerplate. |

A full proposal's total length is dominated by how long the pinned-verbatim intake answers are (`project_scope`, `proposed_timeline`, `estimated_pricing`) plus ~180 words of fixed template frame — the content this project's own prompting controls is the three generated sections above, so that's what the word targets constrain.

Practical check: if a generated piece comes back well over target, the regenerate instruction can be "shorten to ~150 words, keep all facts" — cheaper than editing a wall of text by hand. The UI word-count badge (still open, see `docs/edge-cases.md`) makes the over-length sections visible at a glance so the salesperson knows where to spend edit time.
