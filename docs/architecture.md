# AI-Powered Proposal Workflow — Architecture & Design Doc

**Status:** Discovery — no application code written.
**Scope:** Architecture only, per request. See `decisions.md` for the open-question log and `system-flow.md` for the data-flow and state-machine diagrams — this document covers everything else: risks, proposed structure, domain model, regeneration strategy, auth model, failure handling, and the phased implementation plan.

---

## 0. Repository State (verified 2026-09-08)

This is confirmed greenfield, not assumed:

- `backend/main.py` exists but is empty (0 lines) — just a `venv/`, no FastAPI app yet.
- `web-app/` is an untouched `create-next-app` scaffold (default `page.tsx`, Tailwind, no custom routes/components).
- No `.env`/`.env.example`, no Supabase client config, no n8n workflow export, no requirements/pyproject file anywhere in the repo.
- `docs/decisions.md` and `docs/system-flow.md` existed as empty stub files before this pass — now populated as the natural home for the decision log and flow diagrams respectively.

Nothing in the current repo pre-empts any of the open questions below — there's no existing code pulling the design toward multi-tenant, a specific document format, etc. Every decision in `decisions.md` is still fully open.

---

## 1. Risks & Edge Cases

**Intake layer**
- **Duplicate submissions**: n8n retrying a failed webhook delivery, a user double-submitting the Google Form, or a manual re-run of the n8n workflow can all create duplicate `Proposal` records unless intake rows carry a stable identifier and FastAPI enforces idempotency on it (Q4).
- **Schema drift**: someone edits the Google Form (adds/removes/renames a question), the Sheet column shifts, and it silently breaks the n8n → FastAPI mapping. Nothing in this chain except a runtime error will surface that (Q5).
- **Partial/malformed intake data**: required fields missing or malformed reaching FastAPI with no upstream validation.
- **Unauthenticated webhook endpoint**: if the FastAPI intake endpoint isn't authenticated, anyone who discovers the URL can inject fake proposals (Q3).

**Generation layer**
- **Claude API unavailability or rate limiting** mid-generation, especially for a proposal with many sections generated in sequence or parallel.
- **Token/context limits**: a proposal with many long sections plus full-document context for regeneration can exceed model context limits — the strategy in §5 needs a ceiling.
- **Tone/fact drift between sections**: regenerating one section in isolation without shared context can contradict facts stated in a sibling section (pricing mentioned differently, a scope item described inconsistently).
- **Lost manual edits**: if a salesperson hand-edits a section and someone (or a background job) triggers a regeneration of that section, the edit is silently discarded unless the system distinguishes "AI-generated" from "human-edited" state per section.
- **Non-deterministic cost**: unlimited regeneration attempts with no cap is a direct cost/abuse risk (Q13).

**Review / approval layer**
- **Concurrent editing**: two people (or a salesperson and a background regeneration job) editing the same section at once — last-write-wins will silently drop changes without optimistic concurrency control.
- **Approval bypass**: a client-facing "send" action must be structurally impossible before `Approved` state — enforced server-side, not just hidden in the UI.
- **Self-approval**: if segregation of duties matters (Q14), the API must reject an approval performed by the same user who owns/created the proposal, not just discourage it in the UI.
- **Stale approval**: a section is regenerated *after* internal approval but *before* delivery — does approval get invalidated automatically, or can a proposal be delivered with content nobody actually approved? Needs an explicit rule (see `system-flow.md` guard rules).

**Delivery & logging**
- **Delivery failures**: email bounces, invalid client address, attachment size limits — "sent" and "delivered" are different states and need separate tracking.
- **Document generation failures**: partial documents (e.g. a broken template merge) being delivered as if complete.
- **Logging sensitive content**: naively logging full proposal text/PII in activity logs creates a compliance liability (Q18) — logs should generally reference entities and diffs, not always embed full content.
- **Audit log integrity**: if logs are just another table with normal CRUD permissions, they're editable/deletable by anyone with DB access, undermining their value as an audit trail.
- **Clock/ordering**: relying on client-supplied or ambiguous timestamps for a legal/audit-relevant log; use server-generated, timezone-aware timestamps only.

---

## 2. Proposed Architecture

### 2.1 Backend (FastAPI) — Layering

A pragmatic layered split — not full DDD ceremony, but enough separation that Claude, Supabase, and email are swappable and testable in isolation:

- **API layer** (`routers/`): HTTP concerns only — request/response models, status codes, auth dependency injection. No business logic.
- **Application/service layer** (`services/`): use-case orchestration — `IntakeService`, `ProposalGenerationService`, `RegenerationService`, `ApprovalService`, `DeliveryService`, `AuditService`. This is where the state machine is enforced.
- **Domain layer** (`domain/`): entities and pure logic — state transition rules, validation, what makes a proposal "ready for approval." No I/O.
- **Infrastructure/adapters** (`adapters/`): concrete integrations — `SupabaseRepository`, `ClaudeClient`, `StorageAdapter`, `EmailAdapter`, `N8nWebhookVerifier`. Each implements a narrow interface the service layer depends on, so Claude or Supabase can be mocked/replaced without touching services.
- **Background/async work** (`jobs/` or a task queue): generation calls, document rendering, and email delivery should not block the request/response cycle — naturally async, retryable jobs rather than inline request handling (§4).

This gives a clean seam for the biggest open question (Q1, multi-tenant or not) — if `Organization` gets added later, it's a change to the domain layer and repository queries, not a rewrite of the API surface.

### 2.2 Frontend (Next.js) — Layering

- **Route/page layer**: proposal list, proposal detail/review, approval queue — thin, mostly data-fetching + composition.
- **Feature components**: `SectionEditor`, `RegenerateSectionButton`, `ApprovalPanel`, `ActivityTimeline` — encapsulate one piece of workflow behavior each.
- **API client layer**: a single typed client for the FastAPI backend, so request/response shapes are defined once and shared across features.
- **Server-side auth boundary**: role-gated routes/pages (salesperson vs. approver views) enforced both in middleware/route guards *and* re-checked by the backend — never trust the frontend gate alone (§3).

For system context and integration boundaries, see `system-flow.md` §1–2.

---

## 3. Proposed Domain Entities

Conceptual model — attributes are illustrative, not a schema:

- **Proposal** — the central aggregate. Client/company info, current state (`system-flow.md` §3), owning salesperson, timestamps, links to its sections, current approval status, links to generated documents.
- **ProposalSection** — belongs to a Proposal. Type/name (e.g. "Executive Summary," "Scope," "Pricing"), ordering, current content, content origin (`ai_generated` / `human_edited` / `human_edited_after_generation`), generation history (see `GenerationEvent`), version number.
- **IntakeSubmission** — the raw payload received from n8n, stored as-is before being mapped into a Proposal. A durable record of "what actually came in," independent of how the Proposal model evolves — valuable for debugging schema drift.
- **GenerationEvent** — one Claude API call: which section, prompt/context reference used, model, token usage, result, success/failure, timestamp, triggered-by-user. Doubles as audit trail and cost-tracking mechanism (Q13).
- **ApprovalDecision** — approver, decision (approved/rejected/changes requested), comment, timestamp, and which Proposal *version* it was made against (needed for the "stale approval" risk).
- **DocumentArtifact** — a generated final-document file: format, storage path (Supabase Storage), the Proposal version it was generated from, generation timestamp. A proposal can plausibly have more than one over time if regenerated post-approval (Q9).
- **DeliveryRecord** — a client-delivery attempt: channel (email/link), recipient, status (sent/bounced/failed/delivered/viewed if trackable), timestamp, related DocumentArtifact.
- **ActivityLogEntry** — an append-only record of every state-relevant action (created, section regenerated, edited, approved, rejected, document generated, delivered) with actor, entity reference, and timestamp. Distinct from `GenerationEvent`: this is the human-readable audit trail across the whole lifecycle.
- **User** — salesperson or approver (possibly other roles), with role assignment (§3).
- **Client** — the company/person the proposal is for; may or may not be a system user, depending on Q2.
- **Organization** *(conditional — only if Q1 resolves to multi-tenant)* — the tenant boundary Users, Proposals, and Clients would need to scope under.

---

## 4. Section-Level Regeneration: Preserving Context, Tone, and Consistency

Regenerating one section without a shared context mechanism is exactly how you get contradictions between sections (§1). Proposed approach:

1. **A Proposal-level context object, built once at intake/first generation.** Captures the durable facts a regeneration should never contradict: client name/industry, raw intake answers, and a distilled "brief" (goals, constraints, key facts, pricing basis) extracted from intake. Generated once, stored, reused — not regenerated per section, so it acts as a stable anchor.
2. **A tone/style profile, set once per proposal (or per client/org, per Q11).** Define formality level, voice guidelines, terminology preferences explicitly and pass them into every generation/regeneration call as a fixed instruction block, rather than re-deriving tone from scratch each time.
3. **Sibling-section summaries, not full text, as context.** Passing every other section's full content into each regeneration call is expensive and risks context-limit issues as proposals grow. Maintain a short auto-generated summary per section (key claims/numbers stated) and include those summaries — plus the full text of directly adjacent sections where continuity matters most (e.g. Scope and Pricing) — rather than the entire document.
4. **A canonical facts/glossary layer for anything that must never vary.** Client name, agreed pricing figures, dates, scope boundaries — structured fields the generation prompt is *constrained* to use verbatim, not left to the model to reproduce consistently from prose context alone. The strongest lever against numeric/factual drift across regenerations.
5. **Regeneration instructions as an explicit, separate input from the base context.** If a salesperson wants "make this more concise" or "add a case study reference," that instruction is a distinct parameter merged with (not replacing) the proposal context and tone profile — otherwise ad hoc instructions silently drift tone away from the rest of the document over repeated regenerations.
6. **Version + diff tracking per section**, so a regeneration is never destructive: keep the prior version retrievable, and mark whether current content is AI-original, AI-regenerated, or human-edited (addresses "lost manual edits" in §1) — regenerating a `human_edited` section should require explicit confirmation, since it discards human work.
7. **(Optional, if quality bar demands it) A lightweight consistency pass** after any regeneration — a secondary, cheaper check (rules-based or a smaller/cheaper model call) that flags obvious contradictions (a price mentioned in the regenerated section that doesn't match the Pricing section) rather than trying to prevent all drift purely through prompt engineering.

This mechanism hinges on Q10 and Q11 in `decisions.md` — the shape of "regeneration instructions" and "tone source" need to be decided before this is buildable.

---

## 5. Authentication & Authorization

**Authentication**: Given the stack already includes Supabase, Supabase Auth is the path of least resistance (issues JWTs, integrates natively with Postgres row-level security). This is a decision worth naming explicitly even though it's not in the blocking list: you could run your own auth in FastAPI instead. Default recommendation is Supabase Auth unless there's a reason not to — confirm before Phase 0 wraps.

**Authorization model**:
- Role-based, minimum two roles: `salesperson` and `approver` (a user could plausibly hold both — itself a decision, see Q14 on self-approval).
- Roles carried as JWT claims (or a `user_roles` lookup FastAPI checks per request) — never trust a role passed from the frontend directly.
- **Defense in depth, two layers**:
  - **Application layer**: FastAPI dependency/middleware checks role + ownership before allowing state-changing actions (e.g. only the assigned salesperson or an admin can trigger regeneration; only users with `approver` role — and, per Q14, not the proposal's own creator — can call approve/reject).
  - **Data layer**: Supabase Postgres row-level security (RLS) policies as a second, independent enforcement point, so a bug in the FastAPI authorization check isn't the only thing standing between a user and unauthorized data — especially relevant if a client-facing or multi-tenant surface is ever added (Q1).
- **Frontend role gating is UX only** — hiding the "Approve" button from a salesperson's UI is good practice but never the actual security boundary; the backend independently re-verifies on every request.
- **Segregation of duties (Q14)** — if required, this is an explicit rule in the approval service (`approver.id != proposal.owner_id`), not something achievable through role assignment alone, since both roles could be held by the same user.

---

## 6. Failure Handling

General principle: every external call (Claude, Supabase Storage, email) is a potential point of failure that must not corrupt the Proposal's state, and every inbound integration (n8n) must be safe to retry.

- **n8n → FastAPI intake**: validate the payload against the expected intake schema and reject (4xx, not silently accept) malformed submissions; require an idempotency key (or use the Sheet row's unique identifier) so a retried webhook delivery updates/no-ops rather than creating a duplicate Proposal; return clear error responses so n8n's own retry/alerting can surface failures instead of them disappearing silently.
- **FastAPI → Claude API**: wrap generation calls with retry + exponential backoff for transient failures (rate limits, timeouts); on persistent failure, mark the specific `GenerationEvent` as failed and leave the section in its last-known-good state — never leave a section blank or half-written because a call failed mid-stream. Run generation as an async/background job (not inline in the request-response cycle) so a slow or failed Claude call doesn't hang an HTTP request; the frontend polls or subscribes for completion.
- **FastAPI → Supabase Storage / document generation**: treat document generation as its own job with its own failure state (`DOCUMENT_GENERATION_FAILED`) distinct from proposal approval — a failed render must not be interpreted as "no document exists yet" vs. "generation was attempted and broke," which are operationally different (the second needs alerting, the first doesn't).
- **FastAPI → email/delivery**: track delivery as a distinct entity (`DeliveryRecord`) with its own status separate from the Proposal's state — "Approved" and "Document generated" should not silently imply "successfully delivered." Failed sends need to be retryable without regenerating the document or re-triggering approval.
- **Data integrity under concurrent access**: use optimistic concurrency (a version/updated-at check) on section edits so two simultaneous writers don't silently overwrite each other — surface a conflict to the user rather than losing data.
- **Audit logging failures shouldn't block the underlying action**, but also shouldn't be best-effort-and-forgotten — a transactional outbox or at-least-once delivery pattern is the standard fix if "the log doesn't match what happened" becomes a routine gap.
- **User-facing failure visibility**: every long-running/async operation (generation, document rendering, delivery) needs a status the salesperson can see in the UI — including "failed, retry available" — rather than a silent spinner with no resolution.

---

## 7. Implementation Plan (Phased)

Each phase is independently shippable/demoable — not a single monolithic build.

**Phase 0 — Foundations**
Repo scaffolding as separate deployables (already true: `backend/` FastAPI, `web-app/` Next.js exist as separate dirs); Supabase project setup; environments (dev/staging/prod); CI basics; auth provider decision finalized and wired end-to-end with a trivial protected route.

**Phase 1 — Intake ingestion (no AI yet)**
FastAPI intake endpoint with schema validation and idempotency; n8n → FastAPI auth mechanism (Q3) implemented; Postgres schema for `Proposal`, `ProposalSection` (empty/manual), `IntakeSubmission`; a proposal appears in a basic Next.js list view purely from intake data. Validates the entire left half of the workflow before any AI cost is incurred.

**Phase 2 — Full-proposal AI generation**
Claude integration for generating all sections from an intake submission; `GenerationEvent` logging; the proposal-level context object (§4 item 1) established here since every later phase depends on it existing.

**Phase 3 — Salesperson review & manual editing**
Section editor UI; edit persistence; content-origin tracking (`ai_generated`/`human_edited`) per section — must exist before Phase 4 touches regeneration, or edits will be silently at risk.

**Phase 4 — Section-level regeneration**
Regeneration endpoint and UI; sibling-summary context assembly; regeneration-instruction input (pending Q10); version history per section; the "regenerating a human-edited section requires confirmation" guard.

**Phase 5 — Internal approval workflow**
Approval/reject endpoints with the authorization rules from §5 (including segregation-of-duties if Q14 requires it); state machine transitions and guards from `system-flow.md` §3 enforced; approval-invalidation-on-regeneration behavior.

**Phase 6 — Document generation**
Final document rendering to the format decided in Q7; storage in Supabase Storage; `DocumentArtifact` records; failure/retry handling from §6.

**Phase 7 — Client delivery**
Delivery mechanism per Q16; `DeliveryRecord` tracking; failure/retry handling; delivery status visible in the UI.

**Phase 8 — Activity logging & audit trail (cross-cutting, hardened here)**
While individual actions should already be logging as each phase ships, this phase makes the `ActivityLogEntry` trail complete, queryable, and reviewable end-to-end — plus resolves Q18/Q19 (retention, redaction, access control) before real client data flows through the system.

**Phase 9 — Hardening**
Rate limiting/cost controls on Claude usage (Q13); load/error-path testing on every integration boundary; monitoring/alerting on failed jobs; security review of the auth model, especially RLS policies; a final pass on every risk in §1 to confirm each has a concrete mitigation, not just a design intention.

---

See `decisions.md` for the full list of decisions to make before proceeding — #1, #3, #7, #10, #14, #16 block Phase 2.
