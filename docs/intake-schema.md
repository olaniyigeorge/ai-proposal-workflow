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

`intake_key = hash(timestamp + email_address)` — computed by FastAPI from the two Sheet-only columns above. Both are set by Google Forms at submission time and are unique per row. Enforced as a DB unique constraint on `IntakeSubmission`; `POST /intake` is an upsert (`ON CONFLICT DO NOTHING`, return the existing `Proposal` id) so n8n retries are safe no-ops. See `decisions.md` #4.

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
