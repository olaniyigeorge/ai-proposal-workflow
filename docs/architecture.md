# AI-Powered Proposal Workflow — Architecture & Design Doc

**Status:** Discovery — no code written
**Scope:** Architecture only, per request. This document identifies open questions, risks, proposed structure, domain model, state machine, regeneration strategy, auth model, failure handling, and a phased implementation plan.

---

## 0. Environment Note

I checked the current environment for an existing repository (`/home/claude`, `/mnt/user-data/uploads`, and searched for `.git` directories) and found none — no code, no scaffolding, no config files. There's nothing to "explore" yet: this is either a **greenfield project**, or you meant to attach/connect a repo (upload, or a GitHub connector) that isn't present in this session.

I'm proceeding on the assumption this is **greenfield**. If there's an existing codebase you want factored into this design, share it (upload the files, or connect GitHub) and I'll revise the architecture against what's actually there instead of a clean slate.

---

## 1. Unresolved Architectural Questions

These are decisions the requirements don't answer. I'm not picking defaults silently — see Section 10 for the consolidated list you need to resolve.

**Identity & tenancy**
1. Is this single-org (your own sales team) or multi-tenant SaaS (multiple client organizations, each with their own salespeople/approvers/proposals)? This changes the entire data model (need for an `Organization`/`Account` boundary, row-level isolation) and is the single highest-leverage decision in this doc.
2. Who are the "clients" — are they ever authenticated users of the system (e.g., a client portal to view/accept proposals), or purely external recipients who only ever receive an email/document?

**Intake & n8n boundary**
3. How does FastAPI authenticate/verify that an incoming request genuinely came from your n8n instance and not a spoofed caller? (shared secret header, HMAC signature, mTLS, IP allowlist, or an API key scoped to n8n only?)
4. Is the Google Form → Sheets → n8n → FastAPI hop idempotent? If n8n retries a webhook delivery (which it will, on failure), does FastAPI need to detect and reject a duplicate intake row?
5. What's the canonical intake schema? Google Forms fields, sheet columns, and the FastAPI request body are three places the same shape has to stay in sync — who owns that contract, and how do you catch drift when a form question is edited?
6. Does n8n run indefinitely watching the sheet as the permanent intake mechanism, or is this a bridge until you build a native intake form? (Doesn't change Phase 1, but changes how much you invest in making the n8n step robust vs. disposable.)

**Document generation**
7. What's the actual output format for the "final document" — PDF, DOCX, HTML-to-PDF, a branded template? This determines the generation library/service and whether formatting fidelity (client logos, letterhead, page breaks) is a requirement.
8. Is there a fixed proposal template (consistent sections, order, branding) or does structure vary per client/engagement type? This affects whether "sections" are a fixed enum or a dynamic, salesperson-defined list.
9. Once approved and converted to a final document, is that document immutable? If someone needs a change after approval, does that force a full re-approval cycle, or is there a "revise after approval" path?

**AI generation**
10. Section regeneration — is it "regenerate this entire section from scratch" only, or does the salesperson give instructions per regeneration ("make this more formal," "shorten this")? This changes the prompt contract and UI significantly.
11. What's the source of "tone" — a fixed house style, a per-client tone setting, or inferred from the intake form free-text? (Directly relevant to Section 6.)
12. Do you need deterministic/reproducible output (e.g., for compliance, so a given input always produces comparable output), or is variation across regenerations acceptable/desirable?
13. Cost and rate control: is there a ceiling on how many times a section can be regenerated, or a cost budget per proposal? Claude calls are not free, and an unbounded "regenerate" button is an easy cost leak.

**Approval & delivery**
14. Can the salesperson who created the proposal also be its approver, or is segregation of duties required (a different person must approve)? This is a real authorization rule, not just UI convention.
15. Is approval single-approver or a chain/multi-approver? Any threshold (e.g., proposals above $X need a second approval)?
16. How is the final proposal actually delivered to the client — email with attachment, a link to a hosted/viewable document, e-signature integration? "Send to client" is one line in your workflow but is a meaningfully different build depending on the answer.
17. Do you need delivery confirmation/tracking (opened, viewed, downloaded), or is "sent" the end of the system's responsibility?

**Data & compliance**
18. Will proposals contain PII or commercially sensitive client data? If so, what are the retention, redaction (e.g., in logs), and access-control requirements?
19. What does "activity and status must be logged" mean operationally — an internal audit trail visible to admins, or something a client/compliance function might need to export?

I'll treat items 1, 3, 7, 10, 14, and 16 as **blocking** — the architecture below flags where each one forks the design, but you should decide them before Phase 2 in the plan (Section 9) begins.

---

## 2. Risks & Edge Cases

**Intake layer**
- **Duplicate submissions**: n8n retrying a failed webhook delivery, a user double-submitting the Google Form, or a manual re-run of the n8n workflow can all create duplicate `Proposal` records for the same intake unless intake rows carry a stable identifier and FastAPI enforces idempotency on it.
- **Schema drift**: someone edits the Google Form (adds/removes/renames a question) and the Sheet column shifts, silently breaking the n8n → FastAPI mapping. Nothing in this chain except a runtime error will surface that.
- **Partial/malformed intake data**: required fields missing or malformed (e.g., an email field with no `@`) reaching FastAPI with no validation upstream.
- **Unauthenticated webhook endpoint**: if the FastAPI intake endpoint isn't authenticated, anyone who discovers the URL can inject fake proposals.

**Generation layer**
- **Claude API unavailability or rate limiting** mid-generation, especially for a proposal with many sections generated in sequence or parallel.
- **Token/context limits**: a proposal with many long sections plus full-document context for regeneration can exceed model context limits; the strategy in Section 6 needs a ceiling.
- **Tone/fact drift between sections**: regenerating one section in isolation without shared context can contradict facts stated in a sibling section (pricing mentioned differently, a scope item described inconsistently).
- **Lost manual edits**: if a salesperson hand-edits a section and someone (or a background job) triggers a regeneration of that section, the edit is silently discarded unless the system distinguishes "AI-generated" from "human-edited" state per section.
- **Non-deterministic cost**: unlimited regeneration attempts with no cap is a direct cost/abuse risk.

**Review / approval layer**
- **Concurrent editing**: two people (or a salesperson and a background regeneration job) editing the same section at once — last-write-wins will silently drop changes without optimistic concurrency control.
- **Approval bypass**: a client-facing "send" action must be structurally impossible before `Approved` state — this has to be enforced server-side, not just hidden in the UI.
- **Self-approval**: if segregation of duties matters (see Q14), the API must reject an approval performed by the same user who owns/created the proposal, not just discourage it in the UI.
- **Stale approval**: a section is regenerated *after* internal approval but *before* delivery — does approval get invalidated automatically, or can a proposal be delivered with content nobody actually approved? This needs an explicit rule.

**Delivery & logging**
- **Delivery failures**: email bounces, invalid client address, attachment size limits — "sent" and "delivered" are different states and need to be tracked separately.
- **Document generation failures**: partial documents (e.g., a broken template merge) being delivered as if complete.
- **Logging sensitive content**: naively logging full proposal text/PII in activity logs creates a compliance liability; logs should generally reference entities and diffs, not always embed full content.
- **Audit log integrity**: if logs are just another table with normal CRUD permissions, they're editable/deletable by anyone with DB access — undermining their value as an audit trail.
- **Clock/ordering**: relying on client-supplied or ambiguous timestamps for a legal/audit-relevant log; use server-generated, timezone-aware timestamps only.

---

## 3. Proposed Architecture

### 3.1 System Context & Data Flow

```
Google Form (intake)
        │
        ▼
Google Sheets (raw intake store)
        │  (row watch/poll)
        ▼
   n8n workflow  ──── auth: shared secret / HMAC header ───┐
        │                                                   ▼
        │                                        FastAPI: POST /intake
        │                                                   │
        │                                                   ▼
        │                                   Supabase Postgres (system of record)
        │                                                   │
        │                                      ┌────────────┼─────────────┐
        │                                      ▼            ▼             ▼
        │                              Proposal created  Activity Log  Notification
        │                                      │
        │                                      ▼
        │                        Salesperson Review UI (Next.js)
        │                                      │
        │                     ┌────────────────┼─────────────────┐
        │                     ▼                                  ▼
        │           Claude API (generate/          Manual section edits
        │            regenerate section)                        │
        │                     └──────────────┬───────────────────┘
        │                                    ▼
        │                         Internal Approval step
        │                                    │
        │                                    ▼
        │                      Document Generation (final artifact)
        │                                    │
        │                                    ▼
        │                       Supabase Storage (generated docs)
        │                                    │
        │                                    ▼
        │                          Client Delivery (email/link)
        │                                    │
        └───────────────────────────►  Activity Log (every step above)
```

Every box on the right of the n8n boundary is inside your system; everything to the left (Form, Sheets, n8n) is external intake tooling you're integrating with, not owning.

### 3.2 Backend (FastAPI) — Layering

A pragmatic layered/hexagonal split — not full DDD ceremony, but enough separation that Claude, Supabase, and email are swappable and testable in isolation:

- **API layer** (`routers/`): HTTP concerns only — request/response models, status codes, auth dependency injection. No business logic.
- **Application/service layer** (`services/`): use-case orchestration — `IntakeService`, `ProposalGenerationService`, `RegenerationService`, `ApprovalService`, `DeliveryService`, `AuditService`. This is where the state machine (Section 5) is enforced.
- **Domain layer** (`domain/`): entities and pure logic — state transition rules, validation, what makes a proposal "ready for approval." No I/O.
- **Infrastructure/adapters** (`adapters/`): concrete integrations — `SupabaseRepository`, `ClaudeClient`, `StorageAdapter`, `EmailAdapter`, `N8nWebhookVerifier`. Each implements a narrow interface the service layer depends on, so Claude or Supabase can be mocked/replaced without touching services.
- **Background/async work** (`jobs/` or a task queue): generation calls, document rendering, and email delivery should not block the request/response cycle — these are naturally async, retryable jobs rather than inline request handling (elaborated in Section 8).

This gives you a clean seam for the biggest open question in Section 1 (multi-tenant or not) — if `Organization` gets added later, it's a change to the domain layer and repository queries, not a rewrite of the API surface.

### 3.3 Frontend (Next.js) — Layering

- **Route/page layer**: proposal list, proposal detail/review, approval queue — thin, mostly data-fetching + composition.
- **Feature components**: `SectionEditor`, `RegenerateSectionButton`, `ApprovalPanel`, `ActivityTimeline` — encapsulate one piece of workflow behavior each.
- **API client layer**: a single typed client for the FastAPI backend, so request/response shapes are defined once and shared across features.
- **Server-side auth boundary**: role-gated routes/pages (salesperson vs approver views) enforced both in middleware/route guards *and* re-checked by the backend (never trust the frontend gate alone — see Section 7).

### 3.4 Integration Boundaries

Treat each of these as a distinct adapter with its own failure mode, retry policy, and auth mechanism (detailed in Section 8):
- n8n → FastAPI (inbound webhook)
- FastAPI → Claude API (outbound, generation)
- FastAPI → Supabase Postgres (data)
- FastAPI → Supabase Storage (documents)
- FastAPI → email/delivery provider (outbound, client-facing)

---

## 4. Proposed Domain Entities

Conceptual model — attributes are illustrative, not a schema:

- **Proposal** — the central aggregate. Client/company info, current state (Section 5), owning salesperson, timestamps, links to its sections, current approval status, links to generated documents.
- **ProposalSection** — belongs to a Proposal. Type/name (e.g., "Executive Summary," "Scope," "Pricing"), ordering, current content, content origin (`ai_generated` vs `human_edited` vs `human_edited_after_generation`), generation history (see `GenerationEvent`), version number.
- **IntakeSubmission** — the raw payload received from n8n, stored as-is before being mapped into a Proposal. Keeps a durable record of "what actually came in," independent of how the Proposal model evolves — valuable for debugging schema drift (Risk in Section 2).
- **GenerationEvent** — one Claude API call: which section, prompt/context reference used, model, token usage, result, success/failure, timestamp, triggered-by-user. This is both your audit trail *and* your cost-tracking mechanism (Q13).
- **ApprovalDecision** — approver, decision (approved/rejected/changes requested), comment, timestamp, and which Proposal *version* it was made against (needed to answer the "stale approval" risk in Section 2).
- **DocumentArtifact** — a generated final-document file: format, storage path (Supabase Storage), the Proposal version it was generated from, generation timestamp. Proposals can plausibly have more than one over time if regenerated post-approval.
- **DeliveryRecord** — a client-delivery attempt: channel (email/link), recipient, status (sent/bounced/failed/delivered/viewed if trackable), timestamp, related DocumentArtifact.
- **ActivityLogEntry** — an append-only record of every state-relevant action (created, section regenerated, edited, approved, rejected, document generated, delivered) with actor, entity reference, and timestamp. This is distinct from `GenerationEvent` (which is Claude-call-specific) — the activity log is the human-readable audit trail across the whole lifecycle.
- **User** — salesperson or approver (and possibly other roles), with role assignment (Section 7).
- **Client** — the company/person the proposal is for; may or may not be a system user, depending on Q2.
- **Organization** *(conditional — only if Q1 resolves to multi-tenant)* — the tenant boundary that Users, Proposals, and Clients would need to scope under.

---

## 5. Proposed Proposal State Machine

```
                     ┌────────────────┐
   intake received   │     DRAFT      │  (Proposal created from intake,
   ─────────────────►│  (Intake)      │   no sections generated yet)
                     └───────┬────────┘
                             │ generate all sections
                             ▼
                     ┌────────────────┐
                     │  GENERATING    │◄──────────────┐
                     └───────┬────────┘                │
                             │ generation complete      │ regenerate
                             ▼                          │ section(s)
                     ┌────────────────┐                 │
              ┌─────►│  IN_REVIEW     │─────────────────┘
              │      │ (salesperson   │
              │      │  edits/regens) │
              │      └───────┬────────┘
   changes    │              │ submit for approval
   requested  │              ▼
              │      ┌────────────────┐
              └──────│PENDING_APPROVAL│
                     └───────┬────────┘
                    approve  │  reject
              ┌──────────────┴──────────────┐
              ▼                             ▼
      ┌────────────────┐           ┌────────────────┐
      │   APPROVED     │           │   REJECTED      │──► back to IN_REVIEW
      └───────┬────────┘           └────────────────┘
              │ generate final document
              ▼
      ┌────────────────┐
      │DOCUMENT_READY  │
      └───────┬────────┘
              │ send to client
              ▼
      ┌────────────────┐
      │   DELIVERED    │
      └───────┬────────┘
              │ (optional, if tracked)
              ▼
      ┌────────────────┐
      │    CLOSED      │  (client accepted/declined — only if in scope)
      └────────────────┘

Failure paths (any generation/document/delivery step) → *_FAILED substates,
see Section 8 — these are not shown above for readability but must exist
per async operation, with a defined retry/recovery transition back into
the preceding state.
```

Key guard rules the service layer must enforce (not just the UI):
- `PENDING_APPROVAL → APPROVED` requires the approver role, and — pending Q14 — must reject if approver == proposal owner.
- Any section regeneration while `PENDING_APPROVAL` or later should force a transition back to `IN_REVIEW` (or a dedicated `APPROVAL_INVALIDATED` state) rather than silently leaving a stale approval in place — this directly closes the "stale approval" risk in Section 2.
- `DOCUMENT_READY → DELIVERED` should be blocked entirely if the state is anything other than `APPROVED`/`DOCUMENT_READY` — delivery must not be reachable from `IN_REVIEW` or `PENDING_APPROVAL` under any code path.

---

## 6. Section-Level Regeneration: Preserving Context, Tone, and Consistency

Regenerating one section without a shared context mechanism is exactly how you get contradictions between sections (Risk in Section 2). Proposed approach:

1. **A Proposal-level context object, built once at intake/first generation.** This captures the durable facts a regeneration should never contradict: client name/industry, the raw intake answers, and a distilled "brief" (goals, constraints, key facts, pricing basis) extracted from intake. This is generated once, stored, and reused — not regenerated per section, so it acts as a stable anchor.
2. **A tone/style profile, set once per proposal (or per client/org, depending on Q11).** Rather than re-deriving tone from scratch each regeneration, define it explicitly (formality level, voice guidelines, terminology preferences) and pass it into every generation/regeneration call as a fixed instruction block.
3. **Sibling-section summaries, not full text, passed as context.** Passing every other section's full content into each regeneration call is expensive and risks hitting context limits (Risk in Section 2) as proposals grow. Instead, maintain a short auto-generated summary per section (a few sentences: key claims/numbers stated) and include *those* summaries — plus the full text of directly adjacent sections where continuity matters most (e.g., Scope and Pricing) — rather than the entire document.
4. **A canonical facts/glossary layer for anything that must never vary.** Client name, agreed pricing figures, dates, scope boundaries — these should be structured fields the generation prompt is *constrained* to use verbatim, not left to the model to reproduce consistently from prose context alone. This is the strongest lever against numeric/factual drift across regenerations.
5. **Regeneration instructions as an explicit, separate input from the base context.** If a salesperson wants "make this more concise" or "add a case study reference," that instruction should be a distinct parameter merged with (not replacing) the proposal context and tone profile — otherwise ad hoc instructions silently drift the tone away from the rest of the document over repeated regenerations.
6. **Version + diff tracking per section**, so a regeneration is never destructive: keep the prior version retrievable, and mark whether the current content is AI-original, AI-regenerated, or human-edited (directly addresses the "lost manual edits" risk in Section 2) — a regeneration triggered on a `human_edited` section should probably require explicit confirmation, since it discards a human's work.
7. **(Optional, if quality bar demands it) A lightweight consistency pass** after any regeneration — a secondary, cheaper check (rules-based or a smaller/cheaper model call) that flags obvious contradictions (a price mentioned in the regenerated section that doesn't match the Pricing section) rather than trying to prevent all drift purely through prompt engineering.

This whole mechanism hinges on Q10 and Q11 from Section 1 — the shape of "regeneration instructions" and "tone source" need to be decided before this is buildable.

---

## 7. Authentication & Authorization

**Authentication**: Given the stack already includes Supabase, Supabase Auth is the path of least resistance (issues JWTs, integrates natively with Postgres row-level security) — but this is a decision point (not in Section 1's blocking list, but worth naming): you could equally run your own auth in FastAPI. I'd default to Supabase Auth unless you have a reason not to, since it avoids building session/password/token management from scratch, but confirm this is acceptable before Phase 1.

**Authorization model**:
- Role-based, minimum two roles: `salesperson` and `approver` (a user could plausibly hold both roles, which is itself a decision — see Q14 on self-approval).
- Roles carried as JWT claims (or a `user_roles` lookup FastAPI checks per request) — never trust a role passed from the frontend directly.
- **Defense in depth, two layers**:
  - **Application layer**: FastAPI dependency/middleware checks role + ownership before allowing state-changing actions (e.g., only the assigned salesperson or an admin can trigger regeneration; only users with `approver` role — and, per Q14, not the proposal's own creator — can call the approve/reject endpoint).
  - **Data layer**: Supabase Postgres row-level security (RLS) policies as a second, independent enforcement point, so a bug in the FastAPI authorization check isn't the *only* thing standing between a user and unauthorized data — especially relevant if a client-facing or multi-tenant surface is ever added (Q1).
- **Frontend role gating is UX only** — hiding the "Approve" button from a salesperson's UI is good practice but must never be the actual security boundary; the backend must independently re-verify on every request.
- **Segregation of duties (Q14)** — if required, this is an explicit rule in the approval service (`approver.id != proposal.owner_id`), not something achievable through role assignment alone, since both roles could be held by the same user.

---

## 8. Failure Handling

General principle: every external call (Claude, Supabase Storage, email) is a **potential point of failure that must not corrupt the Proposal's state**, and every inbound integration (n8n) must be **safe to retry**.

- **n8n → FastAPI intake**: validate the payload against the expected intake schema and reject (4xx, not silently accept) malformed submissions; require an idempotency key (or use the Sheet row's unique identifier) so a retried webhook delivery updates/no-ops rather than creating a duplicate Proposal; return clear error responses so n8n's own retry/alerting can surface failures instead of them disappearing silently.
- **FastAPI → Claude API**: wrap generation calls with retry + exponential backoff for transient failures (rate limits, timeouts); on persistent failure, mark the specific `GenerationEvent` as failed and leave the section in its last-known-good state — never leave a section blank or half-written because a call failed mid-stream. Run generation as an async/background job (not inline in the request-response cycle) so a slow or failed Claude call doesn't hang an HTTP request; the frontend polls or subscribes for completion.
- **FastAPI → Supabase Storage / document generation**: treat document generation as its own job with its own failure state (`DOCUMENT_GENERATION_FAILED`) distinct from proposal approval — a failed render must not be interpreted as "no document exists yet" vs. "generation was attempted and broke," which are operationally different (the second needs alerting, the first doesn't).
- **FastAPI → email/delivery**: track delivery as a distinct entity (`DeliveryRecord`) with its own status separate from the Proposal's state — "Approved" and "Document generated" should not silently imply "successfully delivered." Failed sends need to be retryable without regenerating the document or re-triggering approval.
- **Data integrity under concurrent access**: use optimistic concurrency (a version/updated-at check) on section edits so two simultaneous writers don't silently overwrite each other — surface a conflict to the user rather than losing data.
- **Audit logging failures shouldn't block the underlying action**, but also shouldn't be best-effort-and-forgotten — logging should be reliable enough that "the log doesn't match what happened" isn't a routine occurrence (a transactional outbox or at-least-once delivery pattern is the standard fix if this becomes a real gap).
- **User-facing failure visibility**: every long-running/async operation (generation, document rendering, delivery) needs a status the salesperson can see in the UI — including "failed, retry available" — rather than a silent spinner with no resolution.

---

## 9. Implementation Plan (Phased)

Each phase should be independently shippable/demoable — this is not a single monolithic build.

**Phase 0 — Foundations**
Repo scaffolding (Next.js + FastAPI as separate services/deployables), Supabase project setup, environments (dev/staging/prod), CI basics, auth provider decision finalized and wired end-to-end with a trivial protected route.

**Phase 1 — Intake ingestion (no AI yet)**
FastAPI intake endpoint with schema validation and idempotency; n8n → FastAPI auth mechanism (Q3) implemented; Postgres schema for `Proposal`, `ProposalSection` (empty/manual), `IntakeSubmission`; a proposal appears in a basic Next.js list view purely from intake data. Validates the entire left half of the workflow diagram before any AI cost is incurred.

**Phase 2 — Full-proposal AI generation**
Claude integration for generating all sections from an intake submission; `GenerationEvent` logging; the proposal-level context object (Section 6, item 1) established here since every later phase depends on it existing.

**Phase 3 — Salesperson review & manual editing**
Section editor UI; edit persistence; content-origin tracking (`ai_generated`/`human_edited`) per section — this distinction has to exist before Phase 4 touches regeneration, or edits will be silently at risk.

**Phase 4 — Section-level regeneration**
Regeneration endpoint and UI; sibling-summary context assembly; regeneration-instruction input (pending Q10); version history per section; the "regenerating a human-edited section requires confirmation" guard.

**Phase 5 — Internal approval workflow**
Approval/reject endpoints with the authorization rules from Section 7 (including segregation-of-duties if Q14 requires it); state machine transitions and guards from Section 5 enforced; approval-invalidation-on-regeneration behavior.

**Phase 6 — Document generation**
Final document rendering to the format decided in Q7; storage in Supabase Storage; `DocumentArtifact` records; failure/retry handling from Section 8.

**Phase 7 — Client delivery**
Delivery mechanism per Q16; `DeliveryRecord` tracking; failure/retry handling; delivery status visible in the UI.

**Phase 8 — Activity logging & audit trail (cross-cutting, but hardened here)**
While individual actions should already be logging as each phase ships, this phase is dedicated to making the `ActivityLogEntry` trail complete, queryable, and reviewable end-to-end — plus resolving Q18/Q19 (retention, redaction, access control) before real client data flows through the system.

**Phase 9 — Hardening**
Rate limiting/cost controls on Claude usage (Q13); load/error-path testing on every integration boundary from Section 3.4; monitoring/alerting on failed jobs; security review of the auth model, especially RLS policies if Supabase Auth was adopted; a final pass on every risk in Section 2 to confirm each has a concrete mitigation in place, not just a design intention.

---

## 10. Decisions You Need to Make (Consolidated)

Pulled from Section 1 — these are the ones I'd resolve before committing to Phase 2:

| # | Decision | Why it's blocking |
|---|----------|-------------------|
| 1 | Single-tenant or multi-tenant (Organization boundary)? | Changes the entire data model and RLS design |
| 3 | How does FastAPI authenticate the n8n webhook? | Security gap if unresolved |
| 7 | Final document format (PDF/DOCX/etc.) and templating approach? | Determines the Phase 6 tooling entirely |
| 10 | Does section regeneration take user instructions, or is it always "redo from scratch"? | Shapes the regeneration API contract and UI |
| 14 | Can a salesperson approve their own proposal, or is segregation of duties required? | This is an authorization rule, not a UI convention |
| 16 | How is the proposal actually delivered to the client (email/link/e-signature)? | Determines the entire Phase 7 build |

Secondary, non-blocking but worth deciding early: Q2 (client as system user or not), Q4/Q5 (intake idempotency + schema contract ownership), Q9 (immutability of approved documents), Q12 (determinism requirements), Q13 (regeneration cost ceiling), Q15 (single vs. multi-approver), Q18/Q19 (data compliance posture).