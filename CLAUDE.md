# CLAUDE.md

Full design detail lives in `docs/architecture.md`, `docs/system-flow.md`, and `docs/decisions.md`. This file is the quick-reference summary — check those three before making a structural decision, and check `docs/decisions.md` before assuming an open question has been resolved.

## Project Purpose

Internal tool that turns inbound sales-proposal requests into AI-drafted, section-based proposals a salesperson reviews/edits, an internal approver signs off on, and the system then renders to a final document and delivers to the client. Intake arrives via Google Form → Sheets → n8n, not through this app's own UI.

## Architecture

Two independently deployable services, no shared code between them:

- `backend/` — FastAPI, layered: `routers/` (HTTP only) → `services/` (use-case orchestration, enforces the state machine) → `domain/` (entities, transition rules, no I/O) → `adapters/` (Supabase, Claude, Storage, email, n8n-webhook-verification — each behind a narrow interface). Long-running work (Claude calls, document rendering, email) runs as background jobs, never inline in a request.
- `web-app/` — Next.js, layered: route/page layer (thin) → feature components (`SectionEditor`, `RegenerateSectionButton`, `ApprovalPanel`, `ActivityTimeline`) → a single typed API client for the backend. Role-gated routes are UX only.

Data flow: Google Form → Sheets → n8n → `POST /intake` (FastAPI) → Supabase Postgres → salesperson review (generate/edit/regenerate sections via Claude) → internal approval → document generation → Supabase Storage → client delivery, with every step writing to the activity log. Full diagram in `docs/system-flow.md`.

## Tech Stack

- Frontend: Next.js + TypeScript
- Backend: FastAPI + Python
- Database: PostgreSQL via Supabase (also source of Auth + RLS)
- File storage: Supabase Storage (generated proposal documents)
- AI generation: Claude API
- Intake automation: Google Forms → Google Sheets → n8n → FastAPI webhook

## Important Architectural Constraints

- **State transitions are enforced in the backend service layer, never the frontend.** Hiding a button is not access control.
- **n8n → FastAPI intake must be authenticated and idempotent.** Verify the caller (shared secret/HMAC — mechanism TBD, see decisions #3) and dedupe on a stable intake identifier before creating a `Proposal`.
- **Every external call (Claude, Storage, email) runs as an async/retryable job**, not inline in a request handler. A failed call must leave the prior state intact — never a blank or half-written section/document.
- **Authorization is checked at two independent layers**: FastAPI dependency checks (role + ownership) and Supabase Postgres RLS. Neither layer alone is sufficient.
- **Regeneration must never silently discard human edits.** A section's content-origin (`ai_generated` / `human_edited` / `human_edited_after_generation`) must be checked before regenerating it.
- **Regeneration context is assembled, not free-form**: proposal-level context object + tone profile + sibling-section summaries (not full sibling text) + a canonical facts layer for anything that must stay verbatim (pricing, dates, client name). See `docs/architecture.md` §4 before touching generation prompts.
- **Post-approval regeneration invalidates the existing approval** — it must force a transition back to `IN_REVIEW`, never leave a stale `APPROVED` state pointing at changed content.
- **Delivery is unreachable except from `APPROVED`/`DOCUMENT_READY`.** This must be a structural guard in the service layer, not a route ordering assumption.
- Section-level regeneration must only touch the targeted section — sibling sections' `content`, version number, and origin flag must remain untouched by a regeneration call.

## Proposal States

`DRAFT → GENERATING → IN_REVIEW ⇄ PENDING_APPROVAL → APPROVED → DOCUMENT_READY → DELIVERED → CLOSED`, with `REJECTED` looping back to `IN_REVIEW` and a `*_FAILED` substate defined for every async step (generation, document rendering, delivery). Full diagram and guard rules: `docs/system-flow.md` §3. Do not add a transition that isn't in that diagram without updating it first.

## Coding Conventions

- Backend: type-hint everything; request/response shapes are Pydantic models; routers contain no business logic — that belongs in `services/`; adapters are the only place that import a third-party SDK (`anthropic`, `supabase`, etc.) directly.
- Frontend: all backend calls go through the single typed API client — no ad hoc `fetch` calls in components; one feature component per workflow action (don't fold multiple actions into one generic component).
- No silent fallbacks around failure states described above — surface failures as explicit states/errors, not swallowed exceptions.

## Testing Requirements

- Every state-machine transition and guard rule (`docs/system-flow.md` §3) needs a test proving illegal transitions are rejected, not just that legal ones succeed.
- Authorization rules (role checks, self-approval rejection once decided, RLS policies) require tests at both the FastAPI and Postgres layers — don't rely on one to prove the other.
- Intake idempotency (duplicate webhook delivery → no duplicate `Proposal`) needs an explicit test once the idempotency key mechanism is decided.
- Regeneration must have a test confirming sibling sections are unmodified after a single-section regenerate call.
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

- A generated proposal document, once delivered, is not silently replaced — see decisions #9 for the immutability/revision policy once decided.
- Claude regeneration is not unlimited — a per-section or per-proposal cap/budget is required once decided (decisions #13); do not ship an uncapped "regenerate" action.
- Whether a salesperson can approve their own proposal is undecided (decisions #14) — until resolved, treat segregation of duties as required (safer default: reject self-approval) rather than permissive.
- Client delivery mechanism (email/link/e-signature) is undecided (decisions #16) — do not hardcode an assumption into the `DeliveryRecord` schema or delivery service before this is settled.
- Activity logging is required for every state-relevant action (created, edited, regenerated, approved, rejected, document generated, delivered) — this is a product requirement, not an optional observability nice-to-have.
