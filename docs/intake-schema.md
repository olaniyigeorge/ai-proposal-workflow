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

## Template ≠ intake fields (must reconcile)

The reference proposal template uses two placeholders that do **not** exist in the intake schema:

| Template placeholder | Derived from | How |
|---|---|---|
| `{{recommended_approach}}` | `recommended_services` (+ `project_scope` for context) | Claude-synthesized narrative, not passed through verbatim — this is *generated* content, not a canonical fact. |
| `{{deliverables}}` | `recommended_services` | Same — the sheet folds "Deliverables" into one column with services; Claude needs to separate/expand it into a deliverables list for this section. |

Everything else in the template (`{{client_name}}`, `{{company_name}}`, `{{date_of_call}}`, `{{salesperson_name}}`, `{{client_needs_summary}}`, `{{project_scope}}`, `{{goals_and_objectives}}`, `{{proposed_timeline}}`, `{{estimated_pricing}}`) maps directly to a canonical intake field and should be treated as a **pinned fact** the generation prompt is constrained to reproduce verbatim (per `architecture.md` §4, item 4) — never left to the model to paraphrase.

## Proposal sections (from the reference template)

Informs decisions #8 — six sections, fixed order. Reference template now on disk at `docs/reference/proposal-template.md` — read it before touching generation prompts, since it settles exactly which sections are generated vs. pinned-only (Introduction has **no** generated placeholder at all, unlike what an earlier draft of this doc assumed):

1. Introduction (pinned only — boilerplate wraps `client_needs_summary` + `goals_and_objectives` verbatim; assembled at intake, never calls Claude)
2. Proposed Solution (contains `project_scope` verbatim + generated `recommended_approach`)
3. Deliverables (generated from `recommended_services`)
4. Timeline (`proposed_timeline` verbatim)
5. Pricing (`estimated_pricing` verbatim)
6. Next Steps (static boilerplate — no per-proposal generation)

Only **Proposed Solution** and **Deliverables** ever call Claude (`GENERATED_SECTION_KEYS` in `backend/app/domain/generation.py`).

## Generated-section length targets

Set against `docs/reference/proposal-template.md` and `docs/reference/client-email-template.md` — both are notably short (each section is one to two sentences of boilerplate around a pinned fact; the whole email is ~10 lines). There is no "few paragraphs per section" target — that was an earlier assumption before the reference docs existed, and it's why an earlier version of Phase 2 produced sections several times longer than intended (see `docs/edge-cases.md`). Targets below are prompt guidance (`WORD_TARGETS` in `backend/app/domain/generation.py`) plus a visible word-count check in the UI, not hard schema caps.

| Section | Target length | Notes |
|---|---|---|
| Introduction | n/a — not generated | Pure boilerplate + verbatim facts, assembled at intake. No word target needed since nothing is free-generated. |
| Proposed Solution | 120–200 words (generated portion only) | `project_scope` verbatim goes in above this; the generated `recommended_approach` is 1-2 tight paragraphs, not a brainstorm dump. |
| Deliverables | 60–120 words | Short list, one line per deliverable. `recommended_services` expanded/formatted here — if it's already a clean list, generation just formats it, it doesn't inflate it. |
| Timeline | n/a — not generated | `proposed_timeline` verbatim, no generation. |
| Pricing | n/a — not generated | `estimated_pricing` verbatim, no generation. |
| Next Steps | n/a — not generated | Static boilerplate. |

Practical check: if a section comes back well over its target, the regenerate instruction can be "shorten to ~150 words, keep all facts" — cheaper than editing a wall of text by hand. The UI word-count badge (still open, see `docs/edge-cases.md`) makes the over-length sections visible at a glance so the salesperson knows where to spend edit time.
