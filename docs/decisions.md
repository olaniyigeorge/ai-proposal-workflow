# Decision Log — Open Questions

**Status:** Most items resolved as of 2026-09-08. Remaining open items are marked accordingly — check before assuming a behavior.

Legend: 🔴 blocking (forks the core architecture) · 🟡 secondary (shapes one subsystem, not the whole design) · ✅ resolved · 🟠 partially resolved / needs a follow-up decision

## Identity & tenancy

| # | Question | Why it matters | Decision | Date |
|---|----------|-----------------|----------|------|
| 1 ✅ | Single-org or multi-tenant SaaS? | Determines whether an `Organization` boundary and row-level tenant isolation exist at all. | **Single-tenant** — one organization only, no `Organization` entity/tenant boundary needed. | 2026-09-08 |
| 2 ✅ | Are clients ever authenticated users, or purely external recipients? | Determines if `Client` is a system actor or just a data record. | **External recipients only.** Sales/admin staff meet the client, then either they or the client fills the Google Form — the client never logs into the app. | 2026-09-08 |

## Intake & n8n boundary

| # | Question | Why it matters | Decision | Date |
|---|----------|-----------------|----------|------|
| 3 ✅ | How does FastAPI authenticate a request as genuinely from n8n? | Unauthenticated intake endpoint = anyone who finds the URL can inject fake proposals. | **Static shared-secret header** (e.g. `X-Intake-Secret`) sent by the n8n HTTP Request node, checked by a FastAPI dependency on `POST /intake`. Store as an env var on both sides — never inline it in the n8n workflow JSON export. HTTPS-only transport; rotate if the workflow JSON is ever shared externally. | 2026-09-08 |
| 4 ✅ | Is the intake hop idempotent? | n8n *will* retry failed webhook deliveries; without an idempotency key you get duplicate proposals. | **`hash(timestamp + email_address)`** as the idempotency key — both are auto-stamped by Google Forms and unique per submission. `company_name` deliberately excluded (redundant with email). FastAPI enforces a DB unique constraint on this key on `IntakeSubmission`; `POST /intake` is an upsert (`ON CONFLICT DO NOTHING`, return existing `Proposal` id). | 2026-09-08 |
| 5 🟠 | What's the canonical intake schema, and who keeps Form/Sheet/API in sync? | Three places the same shape must match; nothing today catches drift when a form question is edited. | **Mechanism decided:** an n8n Code node normalizes Google Sheets field names to canonical API keys before the HTTP call (see `docs/intake-schema.md`). FastAPI's Pydantic model remains the enforced contract, 422s on drift. **Still open:** the exact canonical field list isn't fully locked — `docs/intake-schema.md` is the working draft; confirm it before Phase 1 schema freeze. | 2026-09-08 |
| 6 ✅ | Is n8n the permanent intake mechanism? | Changes how much hardening the n8n step deserves. | **No — a bridge.** Flow is Form → Sheets → n8n → FastAPI for now. A future native intake form connects directly to FastAPI using the same canonical schema, bypassing n8n entirely. | 2026-09-08 |

## Document generation

| # | Question | Why it matters | Decision | Date |
|---|----------|-----------------|----------|------|
| 7 ✅ | Final document format? | Determines the entire Phase 6 tooling choice. | **Branded PDF**, generated for email delivery. Proposal content stays mutable throughout review; the PDF is generated exactly once, at the point the proposal reaches `APPROVED` — never before. PDF rendering fidelity needs explicit test coverage (see `CLAUDE.md` Testing Requirements). | 2026-09-08 |
| 8 ✅ | Fixed template or variable per client/engagement? | Determines whether "sections" are a fixed enum or a dynamic list. | **Fixed** — the existing reference template's 6 sections, in order, for the initial version (Introduction, Proposed Solution, Deliverables, Timeline, Pricing, Next Steps — see `docs/intake-schema.md`). Configurable/per-client sections deferred, not required for v1. | 2026-09-08 |
| 9 🟠 | Is the approved document immutable? Does a post-approval change require full re-approval? | Affects whether `DocumentArtifact` is append-only or can be superseded quietly. | **Partially resolved:** the PDF is only generated once `APPROVED` is reached, so there's no PDF to revise *before* that point by construction. **Still open:** if a section is regenerated/edited *after* approval (before delivery), does that invalidate the approval and require re-approval + PDF regeneration? Existing guard rule (`system-flow.md` §3: post-approval regeneration forces back to `IN_REVIEW`) is the assumed default — confirm. | 2026-09-08 |

## AI generation

| # | Question | Why it matters | Decision | Date |
|---|----------|-----------------|----------|------|
| 10 ✅ | Does regeneration take instructions, or always "redo from scratch"? | Shapes the regeneration API contract and UI entirely. | **Takes instructions.** E.g. "make this more formal." The model regenerates the section considering both the instruction and full proposal context (§4 mechanism in `architecture.md`). | 2026-09-08 |
| 11 ✅ | Source of "tone"? | Feeds the context/tone mechanism directly. | **Default house tone derived from the existing template**, with the salesperson able to layer additional per-project/per-client instructions on top. A human is always in the loop — no fully autonomous tone drift. | 2026-09-08 |
| 12 ✅ | Deterministic/reproducible output required? | Affects prompt/temperature strategy. | **Not required** — this is a creative-writing task, variation across regenerations is acceptable. Output must still stay within the fixed template structure and the safeguards defined elsewhere in this doc (canonical facts, regeneration cap). | 2026-09-08 |
| 13 ✅ | Cap on regenerations / cost budget? | Unbounded "regenerate" is a direct, uncapped cost/abuse surface. | **Hard cap of 3 regeneration attempts per section.** Every regeneration call — not just the first — **requires** a salesperson-provided instruction/context; this is now mandatory input, not optional (tightens #10). | 2026-09-08 |

## Approval & delivery

| # | Question | Why it matters | Decision | Date |
|---|----------|-----------------|----------|------|
| 14 ✅ | Can the creator also approve, or is segregation of duties required? | Server-side authorization rule, not a UI convention. | **No segregation required — there is only one role, `salesperson`** (see "Roles" below). Self-approval is the normal path, not an edge case to guard against. | 2026-09-08 |
| 15 ✅ | Single-approver or chain/multi-approver? | Shapes `ApprovalDecision` and the state machine's approval branch. | **Single-level approval.** Additionally, approval has two granularities: a salesperson can approve individual sections one at a time, or approve the entire proposal in one action. Multi-level/chain approval deferred. | 2026-09-08 |
| 16 ✅ | How is the proposal delivered to the client? | Meaningfully different build per answer. | **Email**, with the branded PDF as an attachment. Client receives (1) the proposal email, (2) the PDF. Detailed email content/format requirements to follow in the PRD. | 2026-09-08 |
| 17 ✅ | Delivery confirmation/tracking needed? | Determines `DeliveryRecord` scope. | **Yes** — track and record whether the email was successfully sent and its delivery status. | 2026-09-08 |

## Roles (new — resolved 2026-09-08, supersedes the salesperson/approver split assumed earlier)

| # | Question | Why it matters | Decision | Date |
|---|----------|-----------------|----------|------|
| 21 ✅ | Who can use the system — is there a distinct "approver" role? | Determines the entire RBAC model, not just the approval flow. | **Salespeople only, single role.** Even when admin staff prepare a proposal, they operate under the `salesperson` role for authorization purposes — there is no separate `approver` role. Dashboard access requires authentication; every protected frontend and backend request is authorized against this one role. **Open follow-up:** may any authenticated salesperson approve any proposal, or only the proposal's own owner? Everything decided so far is consistent with either — default assumption until confirmed: any authenticated salesperson may act on any proposal (no per-proposal ownership restriction), since no segregation or ownership restriction was stated. | 2026-09-08 |

## Data & compliance

| # | Question | Why it matters | Decision | Date |
|---|----------|-----------------|----------|------|
| 18 ✅ | Will proposals contain PII/sensitive data? | Shapes logging policy and Supabase RLS design. | **Yes** — client names, emails, company info, and other client-provided details. Retention and access-control policy must account for this; specific retention period/redaction rules not yet defined (needed before Phase 8). | 2026-09-08 |
| 19 ✅ | What must activity logging satisfy operationally? | Determines audit log scope/tooling. | **Internal audit trail**, viewable in the dashboard, and **exportable** for compliance purposes when needed. | 2026-09-08 |

## Intake attribution (surfaced 2026-09-08 while cross-referencing the PRD — still open)

| # | Question | Why it matters | Decision | Date |
|---|----------|-----------------|----------|------|
| 20 🟡 | Either sales/admin staff *or the client* can submit the form, and `salesperson_name` is free text — how does a submitted proposal get reliably assigned to the correct `User` account? | Ownership drives authorization. A fragile name-string match will misassign proposals. | Not yet resolved. The single-role model (#21) simplifies *what* assignment means (just needs to map to *a* `salesperson` User, no approver distinction) but not *how* the match happens when the client — not staff — fills the form. Options to consider: manual "claim/assign" step in the review queue as the default fallback, or exact-match against a `User.name` lookup with manual fallback on miss. | — |

---

**Genuinely still open**, in priority order: #5 (lock the exact canonical field list), #20 (intake attribution), #9's follow-up (post-approval revision handling — a default is assumed, confirm it), #21's follow-up (cross-salesperson approval permission — a default is assumed, confirm it). Everything else in this log is resolved.
