# System Flow

See `architecture.md` for narrative detail and `decisions.md` for the open questions referenced inline below (Qn).

## 1. System Context & Data Flow

```
Google Form (intake)
        │
        ▼
Google Sheets (raw intake store)
        │  (row watch/poll)
        ▼
   n8n workflow  ──── auth: static shared-secret header (decisions #3) ───┐
        │                                                        ▼
        │                                          FastAPI: POST /intake
        │                                                        │
        │                                                        ▼
        │                                    Supabase Postgres (system of record)
        │                                                        │
        │                                     ┌──────────────────┼──────────────────┐
        │                                     ▼                  ▼                  ▼
        │                            Proposal created     Activity Log       Notification
        │                                     │
        │                                     ▼
        │                       Salesperson Review UI (Next.js)
        │                                     │
        │                     ┌───────────────┼────────────────────┐
        │                     ▼                                    ▼
        │           Claude API (generate/               Manual section edits
        │            regenerate section)                            │
        │                     └───────────────┬────────────────────┘
        │                                     ▼
        │                          Internal Approval step
        │                                     │
        │                                     ▼
        │                       Document Generation (final artifact)
        │                                     │
        │                                     ▼
        │                        Supabase Storage (generated docs)
        │                                     │
        │                                     ▼
        │                       Client Delivery (email + PDF attachment)
        │                                     │
        └────────────────────────────►  Activity Log (every step above)
```

Everything left of the n8n boundary (Form, Sheets, n8n) is external intake tooling being integrated with, not owned. Everything right of it is inside this system.

## 2. Integration Boundaries

Each of these is a distinct adapter with its own failure mode, retry policy, and auth mechanism (see `architecture.md` §8):

- n8n → FastAPI (inbound webhook)
- FastAPI → Claude API (outbound, generation)
- FastAPI → Supabase Postgres (data)
- FastAPI → Supabase Storage (documents)
- FastAPI → email/delivery provider (outbound, client-facing)

## 3. Proposal State Machine

The diagram below tracks the **Proposal**'s state. Independently, each **ProposalSection** carries its own `pending`/`approved` flag that a salesperson can set at any point during `IN_REVIEW` — approving a section doesn't by itself move the Proposal forward. The Proposal only transitions `PENDING_APPROVAL → APPROVED` once every section is approved (either approved one at a time, or via a single "approve entire proposal" action that approves all remaining sections at once). There is no separate approver role (decisions #21) — the same salesperson who created the proposal is expected to approve it.

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
              │ (optional, if tracked — Q17)
              ▼
      ┌────────────────┐
      │    CLOSED      │  (client accepted/declined — only if in scope)
      └────────────────┘
```

Failure paths (any generation/document/delivery step) fan out to `*_FAILED` substates — omitted above for readability, but every async operation needs one, with a defined retry/recovery transition back into the preceding state. See `architecture.md` §8.

### Guard rules the service layer must enforce (never just the UI)

- `PENDING_APPROVAL → APPROVED` requires **every** `ProposalSection.approval_status == approved` — reject the transition (don't silently partial-approve) if any section is still `pending`. Self-approval by the proposal's creator is allowed (decisions #14); any authenticated salesperson may perform it (decisions #21, default pending confirmation).
- Any section regeneration while `PENDING_APPROVAL` or later forces a transition back to `IN_REVIEW` (or a dedicated `APPROVAL_INVALIDATED` state) and resets that section's `approval_status` to `pending` — rather than leaving a stale approval in place against changed content. (Default assumed; confirm per decisions #9.)
- `DOCUMENT_READY → DELIVERED` must be structurally unreachable from `IN_REVIEW` or `PENDING_APPROVAL` — this is a server-side invariant, not a UI gate.
- A section regeneration call is rejected once `GenerationEvent` count for that section hits 3 (decisions #13) — the API must return a clear "cap reached" error, not silently no-op.
