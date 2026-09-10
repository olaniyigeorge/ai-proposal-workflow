# AI Proposal Workflow

Internal, single-tenant tool for one organization that turns inbound sales-proposal requests into AI-drafted, section-based proposals a salesperson reviews, edits, approves, then renders to a branded PDF and emails to the client. Intake arrives via **Google Form → Google Sheets → n8n → FastAPI webhook**, not through this app's own UI.

## What it does

1. **Intake** — n8n watches a Google Sheet for new form submissions, normalizes the Sheet columns to canonical API keys, and POSTs them to FastAPI's `/api/v1/intake` endpoint over HTTPS with a shared-secret header. FastAPI validates the payload against its Pydantic model, enforces idempotency (duplicate submissions are no-ops, not duplicates), creates a `Proposal` in `DRAFT` with template-prefilled sections, and logs an `IntakeSubmission` record of the raw payload for schema-drift debugging.
2. **Generation** — a salesperson triggers full-proposal AI generation via Claude. Only two of the six template sections are generated (Proposed Solution and Deliverables); the rest are pinned verbatim from intake fields or static boilerplate. Generation runs as a background job, never inline in a request.
3. **Review & edit** — salesperson edits sections by hand (content origin tracked per section: `ai_generated` / `human_edited` / `human_edited_after_generation`) or regenerates a single section with a mandatory instruction (capped at 3 attempts per section). Regeneration assembles context from the proposal-level context object, house tone from the template, the per-call instruction, and sibling-section summaries — never free-form prompting.
4. **Approval** — sections can be approved individually or all at once. The Proposal only reaches `APPROVED` once every section is approved. Self-approval is the expected path (one role only — `salesperson`, no separate approver). Post-approval edits/regenerations invalidate the existing approval and force the Proposal back to `IN_REVIEW`.
5. **Document generation** — once `APPROVED`, the branded PDF is rendered exactly once and stored in Supabase Storage. No draft PDF exists before approval; content stays mutable up to that point.
6. **Delivery** — email-only, with the PDF uploaded to storage and a link embedded in the email body (not an attachment). The salesperson reviews the composed draft (with the link) before sending — no auto-send from `DOCUMENT_READY`. Delivery status (sent/bounced/failed) is tracked in `DeliveryRecord`.
7. **Activity logging** — every state-relevant action is logged (created, edited, regenerated, section approved, proposal approved, rejected, document generated, delivered), viewable in the dashboard, and exportable for compliance.

## Architecture

Two independently deployable services, no shared code:

- **`backend/`** — FastAPI, layered: `routers/` (HTTP only) → `services/` (use-case orchestration, enforces the state machine) → `domain/` (entities, transition rules, no I/O) → `adapters/` (Supabase, Claude, Storage, email, n8n-webhook-verification — each behind a narrow interface). Long-running work (Claude calls, PDF rendering, email) runs as background jobs.
- **`web-app/`** — Next.js, layered: route/page layer (thin) → feature components → a single typed API client for the backend. Every route requires authentication; there's only one role (`salesperson`), so no role-based view split.

Data flow: Google Form → Sheets → n8n → `POST /intake` (FastAPI) → Supabase Postgres → salesperson review → PDF generation → Supabase Storage → email delivery, with every step writing to the activity log.

## Tech stack

- Frontend: Next.js + TypeScript
- Backend: FastAPI + Python
- Database: PostgreSQL via Supabase (also source of Auth + RLS)
- File storage: Supabase Storage (generated PDFs)
- AI generation: Claude API
- Intake automation: Google Forms → Google Sheets → n8n (normalizes to canonical schema) → FastAPI webhook

## Proposal states

```
DRAFT → GENERATING → IN_REVIEW ⇄ PENDING_APPROVAL → APPROVED → DOCUMENT_READY → DELIVERED → CLOSED
```

with `REJECTED` looping back to `IN_REVIEW` and a `*_FAILED` substate defined for every async step (generation, document rendering, delivery). Full diagram and guard rules are in `docs/system-flow.md`. State transitions are enforced in the backend service layer, never the frontend.

## Six template sections (fixed order)

1. Introduction (pinned only — boilerplate wraps intake facts verbatim; assembled at intake, never calls Claude)
2. Proposed Solution (contains `project_scope` verbatim + generated `recommended_approach`)
3. Deliverables (generated from `recommended_services`)
4. Timeline (`proposed_timeline` verbatim)
5. Pricing (`estimated_pricing` verbatim)
6. Next Steps (static boilerplate — no per-proposal generation)

Only **Proposed Solution** and **Deliverables** ever call Claude.

## Key design decisions

- **Idempotency key:** `hash(company_name + normalize(project_scope) + respondent_email)` — computed by FastAPI, not n8n. Covers both n8n retries and a salesperson genuinely resubmitting the same form. Supersedes the earlier `hash(timestamp + email_address)` scheme. See `docs/decisions.md` #4.
- **n8n auth:** static shared-secret header (`X-Webhook-Secret`), env var on both sides, never inlined in the n8n workflow JSON. See `docs/decisions.md` #3.
- **n8n is a bridge, not permanent:** a future native intake form connects directly to FastAPI using the same canonical schema, bypassing n8n entirely. See `docs/decisions.md` #6.
- **One role only:** `salesperson`. No `approver` role. Self-approval is normal. Any authenticated salesperson may act on any proposal (working default until confirmed otherwise — see `docs/decisions.md` #21).
- **Regeneration cap:** 3 attempts per section, every attempt requires a salesperson-supplied instruction (mandatory, not optional). See `docs/decisions.md` #13.
- **Regeneration preserves siblings:** a single-section regenerate call must not touch sibling sections' content, version, or origin flag.
- **Delivery is email-only with a link, not an attachment:** PDF uploaded to storage, link embedded in email body. Salesperson reviews the draft before sending.

## Environment variables

Copy `backend/.env.example` and fill in real values. The key ones:

- `DATABASE_URL` — PostgreSQL connection string (Supabase)
- `SUPABASE_URL` / `SUPABASE_KEY` / `SUPABASE_JWT_SECRET` — Supabase Auth + Storage
- `WEBHOOK_SECRET` — shared secret between n8n and FastAPI for intake webhook auth
- `ANTHROPIC_API_KEY` — Claude API key
- `CLAUDE_MODEL` — model to use for generation

## Running it

```bash
# Backend
cd backend
pip install -r requirements.txt   # or uv sync, depending on project setup
uvicorn app.main:app --reload

# Frontend
cd web-app
npm install
npm run dev
```

Run `make test` and `make lint` to verify (project Makefile).

## Docs

- `docs/architecture.md` — full architecture, risks, domain model, regeneration strategy, auth model, failure handling, phased implementation plan
- `docs/system-flow.md` — data-flow and state-machine diagrams, integration boundaries, guard rules
- `docs/decisions.md` — decision log (open questions, resolved items, status legend)
- `docs/intake-schema.md` — canonical intake schema & Form/Sheet/API field mapping (update this first when a form question changes)
- `docs/edge-cases.md` — recorded edge cases and the gaps they surfaced
- `docs/reference/proposal-template.md` — reference proposal template (read before touching generation prompts)
- `docs/reference/client-email-template.md` — reference client email template

## Intake schema drift

If someone edits the Google Form (adds/removes/renames a question), the Sheet column shifts, and it silently breaks the n8n → FastAPI mapping. The workflow: update `docs/intake-schema.md` first, then update the n8n Code node mapping, then let FastAPI's Pydantic model be the enforcement backstop (422s on anything that doesn't validate). The n8n Code node does Sheet-column → canonical-key translation only — it does **not** compute the idempotency hash (that stays in one place, Python, to avoid a second implementation drifting from the first).

## Duplicate submissions

n8n will retry failed webhook deliveries, a user may double-submit the Google Form, or someone may manually re-run the n8n workflow. All three produce the same `(company_name, project_scope, respondent_email)` and are safe no-ops thanks to the upsert + DB unique constraint on the intake key. The original `hash(timestamp + email_address)` scheme only caught the first case (n8n retries) — the current scheme catches all three.

## Open items

See `docs/decisions.md` for the genuinely still-open items in priority order:

- #5 — lock the exact canonical field list (intake schema freeze)
- #9 follow-up — post-approval revision handling (implemented against the assumed default, not explicitly stakeholder-confirmed; PDF-level consequences still unaddressed)
- #21 follow-up — confirm whether any authenticated salesperson may approve any proposal, or only the proposal's own owner (working default: any)
- #20 — assignment criteria for the claim/assign step in the review queue (manual for now)
- Activity logging exportability and PII retention policy (needed before Phase 8 with real client data)
