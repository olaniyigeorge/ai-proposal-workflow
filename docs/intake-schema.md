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
| `salesperson_name` | `Salesperson Name` | Salesperson Name | Free text; see decisions #20 for the attribution risk. |
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

Informs decisions #8 — six sections, fixed order:

1. Introduction
2. Proposed Solution (contains `project_scope` verbatim + generated `recommended_approach`)
3. Deliverables (generated from `recommended_services`)
4. Timeline (`proposed_timeline` verbatim)
5. Pricing (`estimated_pricing` verbatim)
6. Next Steps (static boilerplate — likely doesn't need per-proposal generation at all)

## Generated-section length targets

No reference doc with an expected average proposal/email length exists in this repo yet (no PRD, no email sample on disk). The targets below are set against the fixed 6-section template and the assumption that a client skim-reads a proposal — set them as prompt guidance and a visible word-count check in the UI, not hard schema caps. Revisit when a real reference (PRD / email sample) lands.

| Section | Target length | Notes |
|---|---|---|
| Introduction | ~80–150 words | One short paragraph: who you are, why you're writing, what you understood the client wants. No fluff. |
| Proposed Solution | ~200–400 words | The meat — what you'll do, why it fits their stated needs, what's in scope. `project_scope` verbatim goes in here; the generated `recommended_approach` stays a tight narrative, not a brainstorm dump. |
| Deliverables | ~100–250 words | Short bulleted list with 1–2 line descriptions each. `recommended_services` expanded/formatted here — if it's already a clean list, generation just formats it, it doesn't inflate it. |
| Timeline | ~80–150 words | Phases + dates from `proposed_timeline` verbatim. Table or short list, not prose. |
| Pricing | ~60–120 words | `estimated_pricing` verbatim, plus a one-line note on what's included/excluded if the intake carries that. No padding. |
| Next Steps | ~40–80 words | Static boilerplate, call-to-action. Shortest section. |

Practical check: if a section comes back well over its target (e.g. 900 words), the regenerate instruction can be "shorten to ~250 words, keep all facts" — cheaper than editing a wall of text by hand. The UI word-count badge makes the over-length sections visible at a glance so the salesperson knows where to spend edit time.
