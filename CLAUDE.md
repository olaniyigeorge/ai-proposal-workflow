# CLAUDE.md

Full design detail lives in `docs/architecture.md`, `docs/system-flow.md`, `docs/decisions.md`, and `docs/intake-schema.md`. This file is the quick-reference summary — check those before making a structural decision, and check `docs/decisions.md` before assuming an open question has been resolved.

## Project Purpose

Internal, single-tenant tool (one organization, one role — see Auth below) that turns inbound sales-proposal requests into AI-drafted, section-based proposals a salesperson reviews/edits/approves, then renders to a branded PDF and emails to the client. Intake arrives via Google Form → Sheets → n8n, not through this app's own UI.

## Architecture

Two independently deployable services, no shared code between them:

- `backend/` — FastAPI, layered: `routers/` (HTTP only) → `services/` (use-case orchestration, enforces the state machine) → `domain/` (entities, transition rules, no I/O) → `adapters/` (Supabase, Claude, Storage, email, n8n-webhook-verification — each behind a narrow interface). Long-running work (Claude calls, PDF rendering, email) runs as background jobs, never inline in a request.
- `web-app/` — Next.js, layered: route/page layer (thin) → feature components (`SectionEditor`, `RegenerateSectionButton`, `ApprovalPanel`, `ActivityTimeline`) → a single typed API client for the backend. Every route requires authentication; there's no role-based view split since there's only one role.

Data flow: Google Form → Sheets → n8n → `POST /intake` (FastAPI) → Supabase Postgres → salesperson review (generate/edit/regenerate sections via Claude, approve section-by-section or all at once) → PDF generation → Supabase Storage → email delivery, with every step writing to the activity log. Full diagram in `docs/system-flow.md`.

## Tech Stack

- Frontend: Next.js + TypeScript
- Backend: FastAPI + Python
- Database: PostgreSQL via Supabase (also source of Auth + RLS)
- File storage: Supabase Storage (generated PDFs)
- AI generation: Claude API
- Intake automation: Google Forms → Google Sheets → n8n (normalizes to canonical schema) → FastAPI webhook

## Important Architectural Constraints

- **State transitions are enforced in the backend service layer, never the frontend.** Hiding a button is not access control.
- **n8n → FastAPI intake is authenticated via a static shared-secret header** (env var on both sides, never inlined in the n8n workflow JSON) and is idempotent: dedupe on `hash(timestamp + email_address)` before creating a `Proposal` (upsert, no-op on retry). See `docs/decisions.md` #3–#4 and `docs/intake-schema.md`.
- **The canonical intake schema is FastAPI's Pydantic model; n8n owns Form/Sheet → canonical-key translation** via a Code node. The exact field list is still being finalized — `docs/intake-schema.md` is the working draft, not yet frozen (decisions #5). FastAPI rejects (422) anything that doesn't validate rather than accepting nulls.
- **Clients never authenticate into this system.** They're either the form-filler or a pure email/PDF recipient — no client portal, no client login.
- **`salesperson_name` is free text and not a reliable `User` foreign key** (sales/admin *or the client* may submit the form). Do not auto-assign proposal ownership by string-matching this field — unresolved, see `docs/decisions.md` #20.
- **There is exactly one role: `salesperson`.** No `approver` role exists — admin staff preparing a proposal also hold this role. Self-approval (a salesperson approving their own proposal) is the expected path, not something to reject.
- **Every external call (Claude, Storage, email) runs as an async/retryable job**, not inline in a request handler. A failed call must leave the prior state intact — never a blank or half-written section/document.
- **Regeneration must never silently discard human edits.** A section's content-origin (`ai_generated` / `human_edited` / `human_edited_after_generation`) must be checked before regenerating it.
- **Every regeneration call requires a salesperson-supplied instruction** (e.g. "make this more formal") — this is mandatory input, not optional, and is capped at **3 attempts per section**. Reject a 4th attempt with a clear error, don't silently no-op.
- **Regeneration context is assembled, not free-form**: proposal context object + house tone (from the template) layered with the per-call instruction + sibling-section summaries (not full sibling text) + a canonical facts layer for anything that must stay verbatim (pricing, dates, client name — see `docs/intake-schema.md` for what's pinned vs. generated). See `docs/architecture.md` §4 before touching generation prompts.
- **Approval has two granularities**: a section can be approved individually, or the whole proposal approved in one action. The Proposal only reaches `APPROVED` once every section's approval status is `approved` — never partial.
- **Post-approval regeneration invalidates the existing approval** (default rule, confirm per decisions #9) — it must force a transition back to `IN_REVIEW` and reset that section's approval status, never leave a stale `APPROVED` state pointing at changed content.
- **The PDF is generated exactly once, only after `APPROVED`.** Content stays mutable up to that point — there is no "draft PDF."
- **Delivery is unreachable except from `APPROVED`/`DOCUMENT_READY`**, is email-only with the PDF as an attachment, and delivery status (sent/bounced/failed) must be tracked in `DeliveryRecord`.
- Section-level regeneration must only touch the targeted section — sibling sections' `content`, version number, and origin flag must remain untouched by a regeneration call.

## Proposal States

`DRAFT → GENERATING → IN_REVIEW ⇄ PENDING_APPROVAL → APPROVED → DOCUMENT_READY → DELIVERED → CLOSED`, with `REJECTED` looping back to `IN_REVIEW` and a `*_FAILED` substate defined for every async step (generation, document rendering, delivery). Section-level approval (`pending`/`approved` per `ProposalSection`) is tracked independently of this diagram and gates the `PENDING_APPROVAL → APPROVED` transition. Full diagram and guard rules: `docs/system-flow.md` §3. Do not add a transition that isn't in that diagram without updating it first.

## Coding Conventions

- Backend: type-hint everything; request/response shapes are Pydantic models; routers contain no business logic — that belongs in `services/`; adapters are the only place that import a third-party SDK (`anthropic`, `supabase`, etc.) directly.
- Frontend: all backend calls go through the single typed API client — no ad hoc `fetch` calls in components; one feature component per workflow action (don't fold multiple actions into one generic component).
- No silent fallbacks around failure states described above — surface failures as explicit states/errors, not swallowed exceptions.

## Testing Requirements

- Every state-machine transition and guard rule (`docs/system-flow.md` §3) needs a test proving illegal transitions are rejected, not just that legal ones succeed — including that `APPROVED` is unreachable with any section still `pending`.
- Authorization tests confirm authentication is required on every protected route, and that self-approval succeeds (it's the expected path, not a rejection case).
- Intake idempotency: a duplicate webhook delivery with the same `(timestamp, email_address)` must not create a second `Proposal`.
- Regeneration tests: sibling sections unmodified after a single-section regenerate call; a 4th regeneration attempt on the same section is rejected; a regeneration call missing an instruction is rejected.
- PDF rendering needs explicit fidelity tests (branding, page breaks, long-content overflow) — there's no earlier point in the flow where a rendering bug would surface, since the PDF is generated exactly once.
- Test framework choice for both services is not yet decided — confirm before Phase 1 test scaffolding begins.

## Commands

**Frontend** (`web-app/`)
```
npm run dev      # local dev server
npm run build    # production build
npm run start    # run production build
npm run lint     # eslint
```

**Backend** (`backend/`)
```
source venv/bin/activate
pip install -r requirements.txt   # once dependencies are pinned
uvicorn main:app --reload         # local dev server
```
No dependencies are installed yet — `requirements.txt`/`pyproject.toml` and the FastAPI app itself still need to be created (Phase 0/1, see `docs/architecture.md` §7).

## Important Business Rules

- The PDF is only generated after full approval and is not silently replaced afterward — but whether a post-approval edit forces a new PDF + re-approval cycle is still open (decisions #9's follow-up).
- Claude regeneration is capped at 3 attempts per section, and every attempt requires a salesperson instruction — do not ship a bare "regenerate" action with no instruction field or no cap.
- Any authenticated salesperson may approve any proposal, including their own — there is no segregation of duties and no separate approver role. (Whether a salesperson may act on a proposal they didn't create is a working default, not yet explicitly confirmed — decisions #21.)
- Delivery is email only, with the branded PDF as an attachment; delivery status (sent/bounced/failed) must be recorded, not just fired-and-forgotten.
- Proposals contain PII (client name, email, company info) — treat retention and access-control as a real requirement even though the specific policy isn't finalized yet (decisions #18).
- Activity logging is required for every state-relevant action (created, edited, regenerated, section approved, proposal approved, rejected, document generated, delivered), must be viewable in the dashboard, and must be exportable for compliance — this is a product requirement, not an optional observability nice-to-have.
