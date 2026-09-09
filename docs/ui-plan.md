# UI Build Plan (`web-app/`)

**Status:** `web-app/` is still the untouched `create-next-app` scaffold (default `page.tsx`, Tailwind v4, Geist fonts, no custom routes/components, no auth wiring, no API client). This doc is the plan for turning that into the salesperson review UI described in `architecture.md` §2.2 — everything here is proposed, not yet built. Update it as pages/components land so it stays a plan, not a stale aspiration.

See `architecture.md` §2.2 (frontend layering) and §7 (phased plan) for the backend-paired context; `system-flow.md` §3 for the state machine every screen has to reflect; `intake-schema.md` for what fields exist to render.

---

## 1. What exists on the backend today (build against this, not the eventual API)

- `POST /intake` — n8n-only, not called from the UI.
- `GET /proposals` — list, salesperson-authenticated (dev bearer-token stub, not real Supabase Auth yet).
- `GET /proposals/{id}` — detail with sections, salesperson-authenticated.
- No mutation endpoints yet (no generate/edit/regenerate/approve/deliver routes) — those land as `services/` work continues (domain transition rules are done; the section-generation/regeneration/approval services are next).

**Consequence for sequencing:** the UI can only build a real list + detail *view* right now. Every interactive feature (editing, regenerating, approving) is UI work that has no backend to call yet — build it phase-by-phase, in the same order the backend exposes it, not ahead of it. Don't stub these with fake client-side state that "approves" things locally; an unwired button that's visibly disabled/"coming soon" is better than one that lies about what happened.

---

## 2. Folder structure

```
web-app/app/
  layout.tsx                 # root layout — auth provider, global nav shell
  page.tsx                   # redirects to /proposals (no public landing page — internal tool)
  login/page.tsx             # Supabase Auth login (Phase 0)
  proposals/
    page.tsx                 # list view  (Server Component — fetches GET /proposals)
    [id]/page.tsx             # detail/review view (Server Component shell + Client feature components)

web-app/components/
  proposals/
    ProposalList.tsx          # table/cards, status badges, links to detail
    ProposalStatusBadge.tsx   # renders ProposalStatus enum as a labeled badge
  sections/
    SectionEditor.tsx         # one section's content, edit-in-place
    RegenerateSectionButton.tsx  # opens instruction input, calls regenerate, shows attempt count/cap
    SectionApprovalToggle.tsx # per-section pending/approved control
  approval/
    ApprovalPanel.tsx         # "approve all remaining" + per-section approve, surfaces ApprovalGuardError
  delivery/
    DeliveryStatus.tsx        # sent/bounced/failed, retry action (Phase 7)
  documents/
    DocumentPreview.tsx       # PDF link/download once DOCUMENT_READY (Phase 6)
  activity/
    ActivityTimeline.tsx      # append-only log view (Phase 8)
  layout/
    AppShell.tsx, NavBar.tsx, AuthGuard.tsx

web-app/lib/
  api/
    client.ts                 # the single typed API client (§4)
    types.ts                   # request/response types mirrored from backend Pydantic schemas
  auth/
    session.ts                 # Supabase Auth session helpers, server + client
  proposal-status.ts           # pure helpers: what actions are allowed to *display* for a given status/sections (§5)
```

One feature component per workflow action (per `CLAUDE.md` convention) — `SectionEditor`, `RegenerateSectionButton`, `ApprovalPanel`, `ActivityTimeline` are named directly in `architecture.md` §2.2 and CLAUDE.md; don't fold "edit" and "regenerate" into one generic `SectionActions` component even though they operate on the same entity.

---

## 3. Routing & auth

- Every route under `/proposals` requires an authenticated session — enforced by a server-side check in `layout.tsx` (or per-page), not just by hiding nav links. There is no role split to build (single `salesperson` role — `decisions.md` #21), so no per-route permission matrix, just authenticated-or-not.
- `AuthGuard` is a thin wrapper, not a security boundary — the real enforcement is the backend re-checking auth on every request (already true: `get_current_salesperson` dependency on the proposals router). The frontend gate is UX (redirect to `/login`), matching CLAUDE.md's "hiding a button is not access control."
- Auth provider: Supabase Auth, per `architecture.md` §5's default recommendation — needs to be confirmed before Phase 0 wraps; until then, the dev bearer-token stub (`dev-salesperson-token`) already accepted by `core/security.py` is what local dev auth targets.

---

## 4. API client

One typed client (`lib/api/client.ts`), matching CLAUDE.md's "no ad hoc `fetch` calls in components" rule:

- Thin wrapper functions per backend route (`listProposals()`, `getProposal(id)`, later `regenerateSection(id, sectionKey, instruction)`, `approveSection(...)`, `approveProposal(...)`), each typed against `lib/api/types.ts` (mirrors the backend's Pydantic response models — `ProposalSummaryResponse`, `ProposalDetailResponse`, `ProposalSectionResponse`).
- Central error handling: the backend's domain errors (`InvalidTransitionError`, `ApprovalGuardError`, `RegenerationCapExceededError`, `RegenerationInstructionRequiredError` — see `backend/app/domain/exceptions.py`) will surface as 4xx responses with structured detail once the service/API layer wraps them. The client should parse these into a typed `ApiError` (status + code + message) rather than a generic thrown `Error`, so components can render *why* an action was rejected (e.g. "3 of 6 sections still pending" from an `ApprovalGuardError`) instead of a generic failure toast.
- Auth token attachment happens once, here — not per call site.

---

## 5. State-driven UI (the state machine is the source of truth, not component state)

`system-flow.md` §3 defines the Proposal state machine and its guard rules; the UI's job is to *reflect* that, never to decide it independently:

- `lib/proposal-status.ts` holds pure display-logic helpers like `canSubmitForApproval(proposal)`, `canApproveProposal(proposal)`, `pendingSectionCount(proposal)` — mirroring (not reimplementing) the backend's `domain/proposal_transitions.py` guard logic, purely so the UI can *show* the right affordance (e.g. disable "Approve Proposal" and show "4 sections still pending" instead of letting the click hit the backend and fail). The backend call is still the real gate — a disabled button is a courtesy, the 422/409 response is the actual enforcement.
- Every status-gated action must handle the backend rejecting it anyway (race condition: another tab approved a section in between) — show the server's error, don't assume the client's cached view is authoritative.
- Transient/background-job statuses (`GENERATING`, `DOCUMENT_GENERATING`, `DELIVERING`, and the `*_FAILED` substates) need a visible "in progress" / "failed, retry available" state per CLAUDE.md's "no silent spinner with no resolution" requirement — see §7 polling strategy.

---

## 6. Data fetching & mutations

Given this is a small internal tool (not a huge dataset, no complex client cache needs yet), default to the simplest thing that works and revisit only if it becomes a real pain point:

- **Reads**: Next.js Server Components fetch directly (list page, detail page shell) — no client-side cache library needed for initial load.
- **Mutations**: Client Components (`SectionEditor`, `RegenerateSectionButton`, `ApprovalPanel`) call the API client, then `router.refresh()` to re-fetch the Server Component tree rather than hand-rolling optimistic client state. Simple, and it matches "state transitions enforced server-side" — the UI shouldn't get ahead of what the server confirmed happened.
- **Polling for transient states**: while a proposal is `GENERATING`/`DOCUMENT_GENERATING`/`DELIVERING`, poll `GET /proposals/{id}` on a short interval (e.g. 2–3s) client-side until it leaves that state, then stop. No SSE/websocket infrastructure exists — don't build it speculatively for a single-tenant internal tool unless polling turns out to be a real UX problem.
- If this genuinely gets complex (e.g. multiple people editing concurrently, needing real-time updates across tabs), reach for TanStack Query or SWR then — not before, since neither is installed today and CLAUDE.md doesn't call for it.

---

## 7. Styling & components

- Tailwind v4 is already scaffolded (`@theme inline`, CSS custom properties in `globals.css`) — keep using it, no new CSS-in-JS library.
- No component library is installed yet (no shadcn/ui, no Radix). Given this is an internal tool with a small, fixed set of screens, hand-rolled Tailwind components are enough — don't pull in a full design system for ~6 screens. Revisit only if the component count grows a lot.
- Keep `ProposalStatusBadge` and similar "enum → visual" components centralized, since the same status vocabulary (`ProposalStatus`, `SectionApprovalStatus`, `ContentOrigin`) is rendered in multiple places (list, detail, activity log).

---

## 8. Testing

Framework choice isn't decided yet (per CLAUDE.md — "Test framework choice for both services is not yet decided"). For the frontend specifically: React Testing Library for component-level tests (SectionEditor validation, ApprovalPanel disabled-state logic) and Playwright for the couple of true end-to-end flows that matter most (submit → generate → review → approve → deliver) once enough of the backend exists to run that flow against. Don't build out a large frontend test suite before there's UI worth testing — Phase 0/1 is mostly auth + a list view.

---

## 9. Phased build plan (mirrors `architecture.md` §7, frontend side only)

| Phase | Backend prerequisite | UI work |
|---|---|---|
| 0 | Auth provider decided | Login page, `AuthGuard`, app shell/nav — a trivial protected route proving auth end-to-end |
| 1 | `POST /intake`, `GET /proposals[/id]` (done) | Proposal list + detail view, read-only, rendering real intake data and the 6 template sections |
| 2 | Claude full-generation service | Detail view shows `GENERATING` status + polling; sections populate once complete |
| 3 | Section edit persistence, content-origin tracking | `SectionEditor` — edit-in-place, save, origin badge (`ai_generated`/`human_edited`) |
| 4 | Regeneration endpoint | `RegenerateSectionButton` — mandatory instruction input, attempt-count/cap display (3 max), confirmation when overwriting a `human_edited` section |
| 5 | Approval endpoints + guards | `ApprovalPanel` — per-section approve, "approve all remaining," surfaces `ApprovalGuardError` clearly (which sections are still pending) |
| 6 | Document generation | `DocumentPreview` — PDF link once `DOCUMENT_READY`; `DOCUMENT_GENERATING`/`DOCUMENT_GENERATION_FAILED` states visible |
| 7 | Delivery endpoints | `DeliveryStatus` — sent/bounced/failed, retry action |
| 8 | Activity log endpoints | `ActivityTimeline` — per-proposal log, dashboard-viewable, exportable (matches `decisions.md` #19) |

Each row only starts once its backend prerequisite exists — no speculative UI against endpoints that don't exist yet, per the "no half-finished implementations" rule.
