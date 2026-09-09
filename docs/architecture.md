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

Nothing in the current repo pre-empts any of the open questions — there's no code pulling the design toward multi-tenant, a specific document format, etc. Most decisions have since been resolved (see `decisions.md`); this document has been updated to reflect them.

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
- **Partial section approval left dangling**: since sections can be approved individually, a proposal could plausibly sit with 4 of 6 sections approved indefinitely — the UI needs to make "what's still unapproved" visible, and the proposal-level `APPROVED` transition must require all sections to be approved (or an explicit "approve all remaining" bulk action), not silently ignore the unapproved ones.
- **Stale approval**: a section is regenerated *after* internal approval but *before* delivery — does approval get invalidated automatically, or can a proposal be delivered with content nobody actually approved? A default rule exists (see `system-flow.md` guard rules) but is not yet explicitly confirmed (decisions #9).

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

Single-tenant is now confirmed (Q1) — no `Organization` boundary or cross-tenant isolation is needed in the domain/repository layer.

### 2.2 Frontend (Next.js) — Layering

- **Route/page layer**: proposal list, proposal detail/review, approval queue — thin, mostly data-fetching + composition.
- **Feature components**: `SectionEditor`, `RegenerateSectionButton`, `ApprovalPanel`, `ActivityTimeline` — encapsulate one piece of workflow behavior each.
- **API client layer**: a single typed client for the FastAPI backend, so request/response shapes are defined once and shared across features.
- **Server-side auth boundary**: the whole dashboard requires authentication (single role, `salesperson` — see §5); route guards still exist to keep unauthenticated users out, but there's no role-based view split to enforce since every authenticated user has the same permissions.

For system context and integration boundaries, see `system-flow.md` §1–2.

---

## 3. Proposed Domain Entities

Conceptual model — attributes are illustrative, not a schema:

- **Proposal** — the central aggregate. Client/company info, current state (`system-flow.md` §3), owning salesperson (see attribution caveat, decisions #20), timestamps, links to its sections, overall approval status, links to the generated `DocumentArtifact`.
- **ProposalSection** — belongs to a Proposal. Type/name (fixed to the 6 template sections — decisions #8), ordering, current content, content origin (`ai_generated` / `human_edited` / `human_edited_after_generation`), regeneration count (capped at 3 — decisions #13), generation history (see `GenerationEvent`), version number, and its own **section-level approval status** (`pending` / `approved`) — sections can be approved individually, independent of the Proposal's overall state (decisions #15).
- **IntakeSubmission** — the raw payload received from n8n, stored as-is before being mapped into a Proposal, keyed by the idempotency key `hash(timestamp + email_address)` (decisions #4). A durable record of "what actually came in," independent of how the Proposal model evolves — valuable for debugging schema drift.
- **GenerationEvent** — one Claude API call: which section, the regeneration instruction supplied (mandatory on every call — decisions #13), model, token usage, result, success/failure, timestamp, triggered-by-user. Doubles as audit trail and cost-tracking mechanism.
- **ApprovalDecision** — records one approval action. `scope` (`section` or `whole_proposal`), `section_id` (nullable, set only when `scope = section`), approving user, decision (approved/rejected/changes requested), comment, timestamp, and which Proposal *version* it was made against. Self-approval by the proposal's own creator is expected and allowed (decisions #14) — there's only one role.
- **DocumentArtifact** — the generated final PDF: storage path (Supabase Storage), the Proposal version it was generated from, generation timestamp. Generated exactly once, only after the Proposal reaches `APPROVED` (decisions #7) — never before, since content is mutable up to that point.
- **DeliveryRecord** — a client-delivery attempt: channel (`email`, fixed — decisions #16), recipient, status (sent/bounced/failed/delivered), timestamp, related DocumentArtifact. Delivery status tracking is required (decisions #17).
- **ActivityLogEntry** — an append-only record of every state-relevant action (created, section regenerated, edited, section approved, proposal approved, rejected, document generated, delivered) with actor, entity reference, and timestamp. Must be viewable in the dashboard and exportable (decisions #19). Distinct from `GenerationEvent`: this is the human-readable audit trail across the whole lifecycle.
- **User** — a `salesperson` (the only role — decisions #21; admin staff preparing a proposal also hold this role). No separate `approver` role exists.
- **Client** — the company/person the proposal is for. Not a system user (decisions #2) — email/company/contact data only.

Single-tenant confirmed (decisions #1): no `Organization`/tenant boundary entity, no cross-org row-level isolation. All Users, Proposals, and Clients belong to the one organization running the system.

---

## 4. Section-Level Regeneration: Preserving Context, Tone, and Consistency

Regenerating one section without a shared context mechanism is exactly how you get contradictions between sections (§1). Proposed approach:

1. **A Proposal-level context object, built once at intake/first generation.** Captures the durable facts a regeneration should never contradict: client name/industry, raw intake answers, and a distilled "brief" (goals, constraints, key facts, pricing basis) extracted from intake. Generated once, stored, reused — not regenerated per section, so it acts as a stable anchor.
2. **A tone/style profile: default house tone derived from the existing template, layered with per-call salesperson instructions (decisions #11).** The house-tone default is fixed and stored once; a salesperson's instruction on a given regeneration (see point 5) is *additive* to it, not a replacement — a human is always in the loop on any tone shift, by design.
3. **Sibling-section summaries, not full text, as context.** Passing every other section's full content into each regeneration call is expensive and risks context-limit issues as proposals grow. Maintain a short auto-generated summary per section (key claims/numbers stated) and include those summaries — plus the full text of directly adjacent sections where continuity matters most (e.g. Scope and Pricing) — rather than the entire document.
4. **A canonical facts/glossary layer for anything that must never vary.** Per `docs/intake-schema.md`, most template placeholders (client name, dates, pricing, timeline, scope) map directly to an intake field and must be reproduced verbatim, not left to the model to paraphrase — the strongest lever against numeric/factual drift across regenerations. Only `recommended_approach` and `deliverables` are genuinely generated content (synthesized from `recommended_services`/`project_scope`).
5. **Regeneration instructions are mandatory, not optional (decisions #13).** Every regeneration call requires the salesperson to supply an instruction/context (e.g. "make this more formal") — merged with, not replacing, the base context and tone profile. This is also the mechanism that keeps the hard cap of 3 attempts per section meaningful: a capped, directed regeneration converges; a capped, undirected one just wastes attempts.
6. **Version + diff tracking per section**, so a regeneration is never destructive: keep the prior version retrievable, and mark whether current content is AI-original, AI-regenerated, or human-edited (addresses "lost manual edits" in §1) — regenerating a `human_edited` section should require explicit confirmation, since it discards human work.
7. **Determinism is explicitly not required (decisions #12)** — proposal writing is treated as a creative task, so regeneration output may vary run to run. The constraint is structural, not statistical: stay within the fixed 6-section template and respect the canonical facts layer (point 4), not "produce the same text twice."
8. **(Optional, if quality bar demands it) A lightweight consistency pass** after any regeneration — a secondary, cheaper check (rules-based or a smaller/cheaper model call) that flags obvious contradictions (a price mentioned in the regenerated section that doesn't match the Pricing section) rather than trying to prevent all drift purely through prompt engineering.

---

## 5. Authentication & Authorization

**Authentication**: Given the stack already includes Supabase, Supabase Auth is the path of least resistance (issues JWTs, integrates natively with Postgres row-level security). This is a decision worth naming explicitly even though it's not formally logged: you could run your own auth in FastAPI instead. Default recommendation is Supabase Auth unless there's a reason not to — confirm before Phase 0 wraps.

**Authorization model** (decisions #21 — single role, resolved 2026-09-08, supersedes the salesperson/approver split originally assumed):
- **One role only: `salesperson`.** There is no `approver` role — admin staff preparing a proposal also act under this role. Every authenticated user has identical permissions; there's no permission split to model.
- Dashboard access requires authentication; every protected frontend route and backend endpoint re-checks it — the frontend gate is UX only, the backend independently re-verifies on every request.
- **Self-approval is the expected path, not an edge case** (decisions #14) — a salesperson creating and approving the same proposal requires no special-casing or rejection logic.
- **Open default, needs confirmation**: whether any authenticated salesperson may act on *any* proposal, or only the proposal's own owner (decisions #21 follow-up). Nothing decided so far requires an ownership restriction, so the working default is **no per-proposal ownership restriction** — build against that until told otherwise.
- **Defense in depth still applies**, even with one role: FastAPI dependencies confirm authentication before any state-changing action, and Supabase Postgres RLS is a second, independent enforcement point — not for tenant isolation (single-tenant) but so a bug in the FastAPI layer isn't the only thing standing between an unauthenticated request and the data.

---

## 6. Failure Handling

General principle: every external call (Claude, Supabase Storage, email) is a potential point of failure that must not corrupt the Proposal's state, and every inbound integration (n8n) must be safe to retry.

- **n8n → FastAPI intake**: validate the payload against the expected intake schema and reject (4xx, not silently accept) malformed submissions; require an idempotency key (or use the Sheet row's unique identifier) so a retried webhook delivery updates/no-ops rather than creating a duplicate Proposal; return clear error responses so n8n's own retry/alerting can surface failures instead of them disappearing silently.
- **FastAPI → Claude API**: wrap generation calls with retry + exponential backoff for transient failures (rate limits, timeouts); on persistent failure, mark the specific `GenerationEvent` as failed and leave the section in its last-known-good state — never leave a section blank or half-written because a call failed mid-stream. Run generation as an async/background job (not inline in the request-response cycle) so a slow or failed Claude call doesn't hang an HTTP request; the frontend polls or subscribes for completion.
- **FastAPI → Supabase Storage / document generation**: treat document generation as its own job with its own failure state (`DOCUMENT_GENERATION_FAILED`) distinct from proposal approval — a failed render must not be interpreted as "no document exists yet" vs. "generation was attempted and broke," which are operationally different (the second needs alerting, the first doesn't). Since the PDF is only ever generated once, at `APPROVED` (decisions #7), rendering fidelity (branding, page breaks, long-content overflow) needs explicit test coverage before Phase 6 ships — there's no earlier point in the flow where a rendering bug would surface.
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
Section-level and whole-proposal approval endpoints (decisions #15); self-approval permitted by design (decisions #14, no special-casing needed); state machine transitions and guards from `system-flow.md` §3 enforced — proposal-level `APPROVED` requires all sections approved; approval-invalidation-on-regeneration behavior (default rule assumed, confirm per decisions #9).

**Phase 6 — Document generation**
Branded PDF rendering (decisions #7), generated exactly once at `APPROVED`; storage in Supabase Storage; `DocumentArtifact` records; explicit rendering-fidelity test pass; failure/retry handling from §6.

**Phase 7 — Client delivery**
Email delivery with PDF attachment (decisions #16); `DeliveryRecord` sent/delivered status tracking (decisions #17); failure/retry handling; delivery status visible in the UI.

**Phase 8 — Activity logging & audit trail (cross-cutting, hardened here)**
While individual actions should already be logging as each phase ships, this phase makes the `ActivityLogEntry` trail complete, queryable, dashboard-viewable, and **exportable** (decisions #19) end-to-end — plus finalizes retention/access-control policy for the PII confirmed present (decisions #18) before real client data flows through the system.

**Phase 9 — Hardening**
Enforce the 3-regeneration cap and mandatory-instruction requirement (decisions #13); load/error-path testing on every integration boundary; monitoring/alerting on failed jobs; security review of the auth model, especially RLS policies; a final pass on every risk in §1 to confirm each has a concrete mitigation, not just a design intention.

---

Remaining open items before proceeding, per `decisions.md`: #5 (lock the canonical field list), #20 (intake attribution when a client fills the form directly), and the follow-ups noted under #9 and #21.
