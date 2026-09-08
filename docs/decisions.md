# Decision Log — Open Questions

**Status:** Unresolved. Nothing below has a default baked in — these must be answered before the phase that depends on them (see `architecture.md` §9) begins. Fill in the "Decision" column as each is resolved and record the date.

Legend: 🔴 blocking (forks the core architecture) · 🟡 secondary (shapes one subsystem, not the whole design)

## Identity & tenancy

| # | Question | Why it matters | Decision | Date |
|---|----------|-----------------|----------|------|
| 1 🔴 | Single-org (your own sales team) or multi-tenant SaaS (multiple client orgs, each with their own salespeople/approvers)? | Determines whether an `Organization` boundary and row-level tenant isolation exist at all. Highest-leverage decision in the whole doc. | | |
| 2 🟡 | Are clients ever authenticated users (e.g. a portal to view/accept), or purely external recipients who only receive email/a document? | Determines if `Client` is a system actor or just a data record. | | |

## Intake & n8n boundary

| # | Question | Why it matters | Decision | Date |
|---|----------|-----------------|----------|------|
| 3 🔴 | How does FastAPI authenticate/verify a request genuinely came from your n8n instance? (shared secret header, HMAC signature, mTLS, IP allowlist, scoped API key) | Unauthenticated intake endpoint = anyone who finds the URL can inject fake proposals. | | |
| 4 🟡 | Is the Form → Sheets → n8n → FastAPI hop idempotent? Does FastAPI need to detect/reject a duplicate intake row on retry? | n8n *will* retry failed webhook deliveries; without an idempotency key you get duplicate proposals. | | |
| 5 🟡 | What's the canonical intake schema, and who owns keeping Form fields / Sheet columns / FastAPI request body in sync? | Three places the same shape must match; nothing today catches drift when a form question is edited. | | |
| 6 🟡 | Is n8n the permanent intake mechanism, or a bridge until a native intake form exists? | Doesn't change Phase 1, but changes how much hardening the n8n step deserves. | | |

## Document generation

| # | Question | Why it matters | Decision | Date |
|---|----------|-----------------|----------|------|
| 7 🔴 | Final document format — PDF, DOCX, HTML-to-PDF, branded template? | Determines the entire Phase 6 tooling choice (rendering library/service, fidelity requirements). | | |
| 8 🟡 | Fixed proposal template (consistent sections/order/branding) or does structure vary per client/engagement type? | Determines whether "sections" are a fixed enum or a dynamic, salesperson-defined list. | | |
| 9 🟡 | Once approved and converted to a final document, is that document immutable? If a change is needed after approval, full re-approval or a "revise after approval" path? | Affects whether `DocumentArtifact` is append-only or can be superseded quietly. | | |

## AI generation

| # | Question | Why it matters | Decision | Date |
|---|----------|-----------------|----------|------|
| 10 🔴 | Does section regeneration take salesperson instructions ("make this more formal," "shorten this"), or is it always "redo from scratch"? | Shapes the regeneration API contract and UI entirely. | | |
| 11 🟡 | Source of "tone" — fixed house style, per-client setting, or inferred from intake free-text? | Directly feeds the context/tone mechanism in `architecture.md` §6. | | |
| 12 🟡 | Do you need deterministic/reproducible output (e.g. for compliance), or is variation across regenerations fine? | Affects prompt/temperature strategy and whether outputs need to be pinned/cached. | | |
| 13 🟡 | Is there a cap on regenerations per section, or a cost budget per proposal? | Unbounded "regenerate" is a direct, uncapped cost/abuse surface. | | |

## Approval & delivery

| # | Question | Why it matters | Decision | Date |
|---|----------|-----------------|----------|------|
| 14 🔴 | Can the salesperson who created a proposal also approve it, or is segregation of duties required? | This is a server-side authorization rule, not a UI convention. | | |
| 15 🟡 | Single-approver or a chain/multi-approver? Any dollar threshold requiring a second approval? | Shapes `ApprovalDecision` and the state machine's approval branch. | | |
| 16 🔴 | How is the final proposal actually delivered — email attachment, hosted/viewable link, e-signature integration? | "Send to client" is one line in the workflow but a meaningfully different build per answer. | | |
| 17 🟡 | Do you need delivery confirmation/tracking (opened/viewed/downloaded), or does responsibility end at "sent"? | Determines whether `DeliveryRecord` needs webhook/pixel tracking integration. | | |

## Data & compliance

| # | Question | Why it matters | Decision | Date |
|---|----------|-----------------|----------|------|
| 18 🟡 | Will proposals contain PII or commercially sensitive client data? If so, retention/redaction/access-control requirements? | Shapes logging policy (§ audit log) and Supabase RLS design. | | |
| 19 🟡 | What must "activity and status must be logged" satisfy operationally — an internal audit trail, or something exportable for a client/compliance function? | Determines whether the audit log needs export tooling and tamper-evidence, or is purely internal. | | |

---

**Resolve before Phase 2** (per `architecture.md` §9): #1, #3, #7, #10, #14, #16. Everything else can be decided incrementally but should be settled before the phase that consumes it starts.
