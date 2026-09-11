# Edge Cases Log

Working log of edge cases discovered while building this project — the "gotchas" that aren't obvious from `CLAUDE.md`/`docs/architecture.md`/`docs/system-flow.md`/`docs/decisions.md` alone, but shaped an implementation choice. Newest first. When an edge case changes a documented decision, update the source doc (`decisions.md`, `intake-schema.md`, etc.) too — this file explains *why*, the source docs state *what's current*.

---

## 2026-09-11 — "Closest match" assignment: scoped to manual self-claim, not fuzzy auto-matching

**The gap (business view):** the feature request for self-service Team management asked for a salesperson's display name to be "used for assigning proposals to them (closest match)." Read literally, that could mean fuzzy-matching a proposal's free-text `salesperson_name` (whatever a client or admin typed at intake) against registered display names and auto-suggesting or auto-assigning the best match. CLAUDE.md and decisions #20 explicitly forbid exactly that: "never auto-assign proposal ownership by string-matching this field" — a client typing "Bob" shouldn't silently bind a proposal to whichever salesperson named "Bob S." happens to exist, since a near-miss match assigning the wrong person's name to real client PII is a worse failure than leaving it unassigned for a human to sort out.

**The fix (implemented 2026-09-11, scoped deliberately narrower):** `display_name` is a self-service field a salesperson sets once (`PATCH /auth/me`, unique across the team) and is only ever *written* into a proposal's `salesperson_name` by an explicit, human-clicked self-claim (`POST /proposals/{id}/claim`) — and only when that proposal is genuinely unassigned (`salesperson_name IS NULL`). No fuzzy matching, no auto-suggestion, no code path that reads an existing free-text `salesperson_name` and tries to resolve it to an account. This is a narrower interpretation of "closest match" than the request's literal wording — worth confirming this is what was actually wanted, versus a real fuzzy-match/suggestion feature layered on top later (which would need its own explicit trade-off discussion given the CLAUDE.md constraint above).

**Where it lives:** `backend/app/models/salesperson_account.py` (`display_name`), `backend/app/services/proposal_service.py::claim_proposal`, `backend/app/api/v1/endpoints/{auth,proposals}.py`, `web-app/components/team/TeamList.tsx`, `web-app/components/proposals/ClaimProposalButton.tsx`. `docs/decisions.md` #20.

**Open follow-up:** ownership is now assignable, but not yet *enforced* — any approved salesperson can still edit/approve/reassign-adjacent-actions on any proposal regardless of who claimed it (decisions #21's follow-up, still open). Claiming currently only sets the display label, not an access restriction.

---

## 2026-09-11 — Production proposal list showed "Invalid or expired token: Not enough segments" while local dev worked fine

**Severity: High** (production-only — the proposals list was completely unusable for a real signed-in user in prod, while looking correctly signed-in in the sidebar the whole time, which makes it a confusing bug to self-diagnose)

**The gap (business view):** after signing in with a real Supabase account in production, the sidebar correctly showed the real email and "Signed in" — but the Proposals page itself showed a "Backend Connection Notice: Invalid or expired token: Not enough segments" and an empty list, every time, while the exact same code path worked perfectly in local dev. "Not enough segments" is PyJWT's error for a string that isn't shaped like a JWT at all (a real JWT always has 3 dot-separated segments) — so the backend wasn't rejecting an expired or wrong token, it was being sent something that was never a JWT in the first place.

**Root cause:** `app/proposals/page.tsx` and `app/proposals/[id]/page.tsx` are Next.js **Server Components** — they fetch data on the server at request time, not in the browser. The shared API client's `request()` function (`web-app/lib/api/client.ts`) decided which auth token to send with: `token || (typeof window !== 'undefined' ? getClientAuthToken() : DEV_TOKEN)`. On the server, `window` is always undefined, so this unconditionally fell back to the literal string `"dev-salesperson-token"` — a real JWT is never checked at all for a server-rendered page load. Locally, the backend's `ENVIRONMENT` is `development`, so `verify_token`'s dev-token special case matches and everything works. In production, `ENVIRONMENT` is not `development`, so that special case never fires, the code falls through to real JWT verification, and `jwt.get_unverified_header("dev-salesperson-token")` immediately fails with "not enough segments" — because that string was never a JWT to begin with. This is exactly the same *shape* of bug as the earlier cookie-name mismatch (a fallback silently substituting a fake value instead of surfacing "there's no real token here"), just triggered by a different code path (SSR vs. client-side cookie reads) — see the pattern noted in `docs/submission/reflections.md`.

**Not the approval gate** (`salesperson_accounts`, decisions #22) — that check happens after JWT verification succeeds and returns a 403 with a distinctly different message ("Your account is pending approval..."). This failure never even reached that code, since the token itself was rejected as malformed before any approval status could be checked.

**The fix (implemented 2026-09-11):** Server Components can't read browser cookies via `document.cookie` (no `window`), but Next.js's `next/headers` `cookies()` API works server-side — added `web-app/lib/auth/serverSession.ts::getServerAuthToken()` using it, and updated both Server Component pages to fetch the real cookie value and pass it explicitly as the `token` argument to `listProposals`/`getProposal`, rather than relying on the API client's own guess. The API client's fallback for "no token, no window" now sends no Authorization header at all instead of a fake one — an unauthenticated server-rendered request now fails with a clear "Authentication required" 401 instead of a confusing malformed-token error. Also removed `getClientAuthToken()`'s own client-side "no cookie found → return DEV_TOKEN" fallback, now that there's no dev-login UI button — an unauthenticated browser session should redirect to `/login` (which `AuthGuard` already does when the token is genuinely absent), not silently authenticate as a fake dev user.

**Where it lives:** `web-app/lib/auth/session.ts`, `web-app/lib/auth/serverSession.ts` (new), `web-app/lib/api/client.ts`, `web-app/app/proposals/page.tsx`, `web-app/app/proposals/[id]/page.tsx`.

**Open follow-up:** any *other* Server Component that fetches from the backend in the future must remember to call `getServerAuthToken()` and pass it explicitly — nothing enforces this at a type level, so a new server-rendered page that forgets this will silently get the "no token" (clear 401) behavior rather than a wrong-but-passing one, which is a safe failure mode but still worth a lint rule or a shared data-fetching wrapper if more server-rendered pages get added.

---

## 2026-09-11 — Real logins started failing with "The specified alg value is not allowed"

**Severity: High** (production-blocking for real login, not cosmetic — every real-account request failed with a 401 on whichever Supabase signing mode we didn't anticipate)

**The gap (business view):** after real per-salesperson login shipped, sign-ins started intermittently throwing `Invalid or expired token: The specified alg value is not allowed`. This is a PyJWT error, not an expired-token message despite the wording — it means the token's own `alg` header wasn't in the list `jwt.decode(...)` was told to accept, i.e. a verification-method mismatch, not a bad secret or a stale session. Root cause: `verify_token` (`app/core/security.py`) hardcoded `algorithms=["HS256"]` and always verified against `SUPABASE_JWT_SECRET` — the *legacy* shared-secret Supabase signing mode. Supabase has since introduced **asymmetric JWT Signing Keys (ES256/RS256)**, verified via a published JWKS endpoint instead of a shared secret, and this project's Supabase instance is issuing tokens in that newer mode. Every real login was structurally broken the moment that was true — the shared secret doesn't even apply to ES256-signed tokens, so no amount of double-checking `SUPABASE_JWT_SECRET`'s value would have fixed it.

**The fix (implemented 2026-09-11):** `verify_token` now reads the token's own (unverified) header to see its actual `alg` before deciding how to verify it: `HS*` algorithms still verify against `SUPABASE_JWT_SECRET` as before (unchanged path, zero risk to whichever mode was already working); anything else (`ES256`/`RS256`) verifies against Supabase's JWKS (`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`) via `jwt.PyJWKClient`, which fetches and caches the actual public signing key by `kid` — never a shared secret for that mode, since asymmetric signing doesn't have one to share. This makes the backend correct regardless of which signing mode a given Supabase project is configured for, rather than needing to know it in advance.

**Where it lives:** `backend/app/core/security.py::verify_token`, `_get_jwks_client`. Tests: `backend/tests/test_jwt_verification.py` (HS256 still works, ES256 now works via a fake JWKS client, and a regression test proving the old HS256-only call really does reproduce the exact reported error against a real ES256 token — not just asserting the new code path in isolation).

**Open follow-up:** `PyJWKClient`'s default cache means a Supabase **key rotation** (if they ever rotate the signing key, e.g. for a security incident) could leave this backend verifying against a stale cached key for a window before the cache refreshes — not yet tuned or tested against an actual rotation event. Also worth confirming which signing mode is intended for this deployment long-term (Supabase's dashboard lets you choose) rather than silently supporting both indefinitely.

---

## 2026-09-11 — A proposal can be fully generated from near-empty intake and read as confidently "finished"

**The gap (business view):** nothing in the pipeline distinguishes a discovery call that actually happened from one where the notes never got filled in — a real example seen while testing had `client_needs_summary: "The client needs"`, `goals_and_objectives: "Goals"`, `project_scope: "deliverables"`, `recommended_services: "Services"`. Claude doesn't know that's placeholder-shaped input — it dutifully writes a grammatically clean, confident Introduction/Proposed Solution/Deliverables around it, and the result *looks* like a finished proposal at a glance (right template, right sections, right tone). The actual cost: a salesperson skims a generic-reading proposal, doesn't immediately recognize *why* it reads generic (the sections are well-formed, just empty of anything specific to this client), approves and sends it, and the client receives something that visibly wasn't tailored to them — the exact opposite of what a discovery-call-to-proposal pipeline is supposed to deliver, and a worse first impression than no automation at all.

**The fix (implemented 2026-09-11):** rather than trying to block generation on "bad" input (a real discovery call can legitimately have a short answer for one field, and Claude quality isn't something to gate mechanically), the system detects the pattern and puts a human decision back in the loop before it goes further: an amber "Intake looks thin" banner on the proposal detail page whenever 2+ of the narrative intake fields are under 4 words, with a one-click **"Email client for more detail"** action — a pre-filled `mailto:` link naming the specific thin fields, so the salesperson can close the gap with the client in one click instead of writing that email from scratch or not sending it at all. Chose flag-and-prompt over block-generation as the alternative not taken: blocking would stop a salesperson from even seeing a rough draft when they might have the missing context themselves (e.g. it's in their own call notes, just not transcribed into the form), and mechanically refusing to generate is a worse failure mode than a visible warning a human can act on or dismiss.

**Where it lives:** `web-app/lib/proposal-status.ts` (`hasThinIntake`, `thinIntakeFields`, `buildRequestMoreInfoMailto`), `web-app/app/proposals/[id]/page.tsx` (the banner). `docs/decisions.md` #23.

**Open follow-up:** the 4-word threshold and "2+ fields" combination were picked by judgment, not measured against real proposal data — worth revisiting once there's a real corpus of genuine vs. thin intakes to check the threshold against (a false positive costs a salesperson one glance at an unnecessary banner; a false negative costs exactly the "generic proposal shipped" failure this was built to catch, so the threshold should probably err toward over-flagging, not under-flagging, until there's real data to tune it). Also unaddressed: this only checks length, not content — a field that's long but still generic ("we would like your standard services please") would slip through undetected.

---

## 2026-09-11 — Real per-salesperson login: security/production-readiness review of the auth flow

**The gap (business view):** "the login page still uses only the dev salesperson option" was a real blocker — different salespeople couldn't sign in as themselves, so every action in the audit trail (`ActivityLogEntry.actor`) was meaningless for a real deployment. But adding real login the naive way (self-serve `supabase.auth.signUp()`, nothing else) trades one gap for a worse one: a working Supabase account is instantly JWT-issuing, so "add real login" alone would mean anyone who finds the deployed URL can create an account and read every client's PII (name, email, pricing, project scope) with zero review. For a sales tool whose entire dataset is client-confidential, that's not an acceptable default just because it's the quick way to ship login.

**The fix (implemented 2026-09-11):**
- **Auth mechanism**: Supabase Auth (email/password) via `@supabase/supabase-js`, client-side only — the frontend calls Supabase's own hosted Auth API directly (`app/login/page.tsx`), never touches the database, and gets back a JWT it sends as a Bearer token to this backend. FastAPI verifies that JWT's signature locally against `SUPABASE_JWT_SECRET` (`app/core/security.py::verify_token`) — it never calls Supabase again per request. Both sign-in and self-serve sign-up are supported (no dashboard step needed to add a salesperson).
- **Approval gate** (`salesperson_accounts` table): a signed-up account is `pending`, not usable, until an already-approved salesperson approves it. `get_current_salesperson` self-registers the row on the account's first authenticated request and returns 403 until approved — consistent with this project's "no separate approver role" model (decisions #21/#22): approving a new colleague costs no more privilege than approving a proposal. Bootstrap (nobody can approve the first account via the API, since nobody's approved yet) is solved by `scripts/approve_salesperson.py`, run once directly against the DB — deliberately not an endpoint, since exposing "approve the first account" as an API just moves the same bootstrap problem down one level.
- **A real, pre-existing bug found and fixed along the way**: `getClientAuthToken()`/`setClientAuthToken()`/`clearClientAuthToken()` disagreed on the cookie name (`proposal_auth_token` vs. `auth_token`) — a real login's token was written to one cookie and never read back, so every session silently fell through to the dev token regardless of who actually signed in. This means real login was *structurally* broken before this pass, not just "not built yet." Fixed to one shared constant.
- **Removed the dev-login button from the UI entirely** (per direct request) — dev token still works for local/test environments (gated on `ENVIRONMENT` in `app/core/security.py`), but there's no UI affordance for it in the deployed app anymore.

**Still open, flagged for a deliberate decision rather than silently left as-is:**
1. **Self-serve sign-up has no invite gate or email-domain restriction.** Anyone with the login URL can create a `pending` account — low severity today (they still can't *do* anything until approved, and there's only one role to escalate to regardless), but it does mean the pending-approval queue itself is an open surface: someone could spam-create accounts. No rate limiting on sign-up exists (that's Supabase Auth's own responsibility, not verified configured here).
2. **Account approval isn't written to any audit trail.** `ActivityLogEntry` is scoped per-`proposal_id` — there's no equivalent log for "who approved which salesperson account, and when" outside the `approved_by`/`approved_at` columns on the row itself. For a compliance export (decisions #19) that's supposed to cover every state-relevant action, account approval is arguably one and currently isn't captured anywhere queryable/exportable the way proposal actions are.
3. **The bootstrap script is a manual, undocumented-to-ops step** — nothing prevents a fresh deployment from having zero approved accounts and no one realizing why every real user is stuck at 403 until someone remembers to run it.

**Where it lives:** `backend/app/models/salesperson_account.py`, `backend/app/services/salesperson_account_service.py`, `backend/app/core/security.py`, `backend/app/api/v1/endpoints/auth.py`, `backend/scripts/approve_salesperson.py`, `backend/migrations/versions/d3e4f5a6b7c8_add_salesperson_accounts_table.py`, `web-app/app/login/page.tsx`, `web-app/lib/auth/session.ts`, `web-app/lib/auth/supabaseClient.ts`, tests in `backend/tests/test_salesperson_approval.py`. `docs/decisions.md` #22.

---

## 2026-09-11 — Once a delivered proposal's PDF can be silently replaced, the business loses proof of what a client actually received

**The gap (business view):** decisions #9's fix (2026-09-11, see below) makes document regeneration legitimate after a post-approval edit — which is the right call for keeping content current, but it means the PDF at a given Storage path is now a mutable, overwritten-in-place object, not an immutable record. Concretely: a proposal is delivered, the client starts a conversation referencing specific pricing/scope language from what they received, then the salesperson edits a section and re-approves — the old PDF is gone (same storage path, upserted) and no section-content version history exists either (see the same entry below). If a pricing or scope dispute ever comes up ("that's not what you sent me"), the business has no way to reconstruct exactly what document a client actually opened, only what the system currently says. That's a real legal/trust exposure for a sales tool whose entire output is a client-facing commitment document, not just a UX nitpick.

**The fix (proposed):** before overwriting, copy the outgoing PDF to a dated/versioned Storage path (e.g. `proposals/{id}/history/{delivered_at}.pdf`) whenever a `DeliveryRecord` is created for it — i.e., snapshot on *delivery*, not on every regeneration, since a PDF that's approved-but-never-sent has no client-facing stakes yet. Alternative not picked: version every `DocumentArtifact` row instead of overwriting (append-only artifacts table) — rejected here as the default because it's a bigger schema change than the business problem strictly requires; the risk is specifically about what a client *received*, not every intermediate regeneration.

**Where it lives:** `backend/app/services/document_service.py::generate_document`, `backend/app/services/delivery_service.py::deliver_proposal` (the natural point to snapshot), `docs/decisions.md` #9.

**Open follow-up:** this compounds with the missing section-version-history gap (same day's entry below) — solving both together (snapshot the PDF + keep prior section content at time of delivery) turns "we don't remember what we sent" into a genuine audit capability, which is also exactly what a compliance-minded client or a future dispute would ask for first.

---

## 2026-09-11 — n8n workflow reviewed for production readiness; one real regression found (inline secret)

**Context:** the user's updated n8n workflow (Code node now string-coerces every Sheet value before sending, and — closing the exact gap flagged in the 2026-09-10 entry below — both the Code node's own validation throw and the HTTP node's failure now route via `continueErrorOutput` to a new "Append row in sheet" node that dead-letters the failed row into an "Invalid Responses" Sheet tab). Reviewed against error handling, edge cases, idempotency, and security.

**What's solid:**
- **Error handling**: both failure points (Code-node validation, HTTP 4xx/5xx) now converge on one dead-letter path instead of failing silently — exactly the fix this doc previously called for.
- **Edge case**: coercing every value to a trimmed string before sending closes a real type-mismatch risk — Google Sheets can return `estimated_pricing` as a number if the cell is formatted as currency, which would otherwise 422 against `IntakePayload`'s `str` field.

**Regression found — the shared secret is inline in the workflow JSON, not a credential.** The HTTP node's previous version (2026-09-10) referenced a proper n8n credential (`genericAuthType: httpHeaderAuth`, `credentials.httpHeaderAuth`). The version reviewed here replaced that with a literal header parameter: `{"name": "x-webhook-secret", "value": "dev-webhook-secret"}` typed directly into `headerParameters`. This is precisely what decisions #3 says not to do ("store as env var on both sides — never inline it in the n8n workflow JSON export"). Anyone who receives this workflow JSON (a backup, a shared export, a support request) now has the live webhook secret in plaintext.

**Fix (accepted, not yet applied — first item on the go-live checklist):** move the secret into n8n's own secret manager / external-secrets integration (n8n supports resolving credential values from an external vault rather than storing them in the workflow itself) instead of the current literal header value or even a plain Header Auth credential typed into n8n's UI. Currently the correct approach is used only for local/dev convenience — the user has confirmed this is the deliberate first step to take before going live, not an oversight to fix silently mid-build. Recorded here specifically so it's citable in a personal reflection on environment/secrets handling.

**Verified 2026-09-11 (not a bug after all):** checked directly against a real failed execution — the "Append row in sheet" node's canonical-named columns (`timestamp`, `respondent_email`, `client_name`, `client_email`, `company_name`, `date_of_call`, `salesperson_name`, `client_needs_summary`, `project_scope`, `goals_and_objectives`, `recommended_services`, `proposed_timeline`, `estimated_pricing`) all populate correctly from the Code node's error output, alongside `error`/`details`. The earlier concern in this entry (that n8n might surface only the raw pre-Code-node item shape on a thrown error, leaving canonical columns blank) does not hold for this node/version — the previous draft of this entry is superseded by this confirmed result.

**Also worth knowing (expected, not a bug):** the Google Sheets Trigger's `rowAdded` event only fires for genuinely new rows — if a row dead-letters into "Invalid Responses" and someone later fixes the *original* row in the source sheet, nothing re-triggers automatically. Recovery is manual: fix the mapping/data, then manually re-run that execution (or re-add a corrected row) in n8n. This matches the "a form/mapping fix always needs a human either way" reasoning in the 2026-09-10 entry, just naming it explicitly so it isn't assumed to be automatic.

**Where it lives:** the n8n workflow itself (not version-controlled in this repo — reviewed from the exported JSON the user shared). `docs/decisions.md` #3, #5.

---

## 2026-09-11 — Post-approval document regeneration resolved; old section content is never retained

**The gap (business view):** `document_service.start_document_generation` unconditionally raised `DocumentAlreadyGeneratedError` if any `DocumentArtifact` already existed for the proposal — including after a legitimate edit-then-re-approve cycle (decisions #9's `regeneration_invalidates_approval` already forces a post-approval edit back to `IN_REVIEW`). That made re-approval a dead end: a salesperson could fix a section after `DOCUMENT_READY`, get the proposal all the way back to `APPROVED` again, and then be permanently unable to generate a PDF reflecting the fix.

**The fix (implemented 2026-09-11, resolves decisions #9):** `start_document_generation` now deletes an existing `DocumentArtifact` before transitioning to `DOCUMENT_GENERATING`, rather than rejecting. This is safe specifically because `transition_proposal` already rules out reaching `APPROVED` a second time without a genuine intervening edit/regeneration — so a `DocumentArtifact` found at this point is always stale content from a prior approval cycle, never a duplicate request for the same one. The regenerated PDF reuses the same deterministic Storage path (`build_document_filename` depends only on client/company name, not a version number) and `upload_pdf`'s `upsert` overwrites the old object in place — no orphaned file left in Storage, no Storage-delete call needed. `DocumentAlreadyGeneratedError` removed as dead code (nothing raises it anymore); the only remaining guard is `InvalidTransitionError` when the proposal isn't `APPROVED`.

**Answering "are old section versions ever kept?" — no.** `ProposalSection.version` is an incrementing integer, but the prior `content` is overwritten in place on every manual edit and every regeneration — nothing snapshots what an *approved* version of a section actually said before it was changed. `regeneration_log` records the instruction/outcome/resulting-version metadata per attempt, but not the text itself, and `ClaudeCallLog` only captures what Claude *generated*, not what a human then approved. Net effect: once a section is edited or regenerated post-approval and the document is regenerated, there is no way to reconstruct exactly what the previously-approved, previously-delivered PDF said at the content level (the old PDF file itself, if not yet overwritten, is the only surviving record, and it's about to be overwritten by this same fix).

**The fix (not implemented, deliberately flagged):** a real section-version-history table (one row per historical `content`+`content_origin`+`approved_at`, not just the current row) would be needed if this ever matters for a dispute or compliance question ("what did we actually promise them in the version we sent"). Not built here — this pass only fixed the dead-end bug, it didn't add version history, since that's a materially bigger feature (a new table, migration, and a UI to browse it) than the regeneration fix itself.

**Where it lives:** `backend/app/services/document_service.py::start_document_generation`, `backend/app/domain/exceptions.py` (`DocumentAlreadyGeneratedError` removed), `backend/app/api/v1/endpoints/proposals.py`, tests in `backend/tests/test_document.py`. `docs/decisions.md` #9.

---

## 2026-09-11 — PII/retention policy defined; activity log audited and fixed against it

**The gap:** decisions #18 (PII/retention policy) was still open, and Phase 8's freshly-built `ActivityLogEntry` (2026-09-10) hadn't been checked against any concrete policy — it turned out to violate the "avoid storing PII in operational logs" principle architecture.md §1 already warned about: the `CREATED` event's description/metadata included `company_name`, and `DELIVERED`/`DELIVERY_FAILED` included `client_email`/`recipient_email` and (for the failure case) a raw provider error string that could itself echo the recipient's address back.

**The fix (implemented 2026-09-11):** a concrete policy now exists at `docs/reference/data-retention-policy.md` — PII vs. sensitive-business-data vs. operational-metadata field classification, and retention windows (proposals 24mo, activity logs 12mo, app logs 30 days), defined directly by the project owner. The activity-log call sites in `intake_service.py` and `delivery_service.py` were fixed to stop carrying PII — `proposal_id` (already the foreign key) is the entity reference; the PII itself already lives correctly on `Proposal`/`DeliveryRecord` and doesn't need a second copy in the audit trail. Tests updated (`test_activity_log.py`).

**Not implemented — policy defined, not yet enforced:** no scheduled job deletes anything when a retention window expires (no proposal-expiry job, no activity-log-pruning job, no log-rotation config on `logs/server.logs`); pre-existing `logger.*` calls elsewhere (`generation_service.py`, `regeneration_service.py`, etc.) weren't re-audited against the policy's "must not contain" list in this pass; and Postgres RLS as defense-in-depth is deliberately deferred — see the reference doc's own "Authorization boundary & defense-in-depth RLS" section for why it isn't a safe quick add given the app's current direct (non-PostgREST) Postgres connection, which owns the tables and would bypass RLS by default regardless of policies written against it.

**Where it lives:** `docs/reference/data-retention-policy.md`, `backend/app/services/intake_service.py`, `backend/app/services/delivery_service.py`, `docs/decisions.md` #18.

---

## 2026-09-10 — Phase 8 (activity log) + Phase 9 (job-failure monitoring) built; three items still open

**The gap (business view):** Two things were missing going into this pass: (1) there was no audit trail at all — CLAUDE.md requires one for every state-relevant action, viewable in the dashboard and exportable for compliance, and nothing in the codebase wrote to anything but the app logger; (2) background-job failures (a failed generation, regeneration, document render, or delivery) only ever surfaced as a `logger.warning`/`logger.error` line with no consistent tag, so nothing external could alert on them the way `INTAKE_SCHEMA_DRIFT` now does for intake.

**The fix (implemented 2026-09-10):**
- **Phase 8**: `ActivityLogEntry` + `record_activity()` (`backend/app/models/activity_log.py`, `backend/app/services/activity_log_service.py`) — every service call site that already mutated proposal/section state (intake creation, manual edit, regeneration success/failure, section/proposal approval, changes-requested, reject, document generation success/failure, delivery success/failure, generation success/failure) now also writes an entry in the *same* commit. `actor` is threaded end-to-end, including through every background job (`run_generation_job(proposal_id, actor)`, etc.), so an async outcome still records who triggered it. `GET /proposals/{id}/activity` (dashboard, newest-first) and `GET /activity/export` (CSV, optionally filtered by proposal, oldest-first, for compliance) are both salesperson-authenticated. Frontend: `ActivityTimeline.tsx`, a collapsible per-proposal panel matching `ClaudeCallLogPanel`'s existing pattern.
- **Phase 9 (partial)**: every background-job failure site now logs a consistent `BACKGROUND_JOB_FAILED job=<name> proposal=<id> ...` tag, extending the intake-monitoring pattern (`INTAKE_SCHEMA_DRIFT`/`INTAKE_AUTH_FAILED`, see the entry below) to generation, regeneration, document generation, and delivery — a log-based monitor can now alert on any failed async job in the system, not just intake.

**Three things deliberately left open, not silently dropped:**
1. **Audit log integrity (architecture.md §1)**: `activity_log_entries` is a normal table with normal CRUD permissions at the DB level. The application layer never exposes an update/delete path (only `record_activity`'s insert and the list/export reads), but that's a convention, not a guarantee — anyone with direct DB access (or a future endpoint added carelessly) could edit or delete a row with nothing to stop them. Real tamper-resistance (DB-level REVOKE on UPDATE/DELETE for the app's role, a trigger, or a genuinely separate WORM store) is unbuilt. Worth a real decision before this table is relied on for actual compliance, not just internal dashboarding.
2. **Retention/access-control policy (decisions #18)** still isn't defined, and this table makes the gap bigger, not smaller, in the same way the Claude-call-log table did (see that entry below) — it now holds a second copy of state-relevant facts (who did what, when) for every proposal indefinitely, with `ON DELETE CASCADE` as the only lifecycle rule (dies with the Proposal, no independent retention window).
3. **RLS was never audited.** The backend connects to Postgres with what functions as a service-role key and does all authorization in the FastAPI dependency layer (`get_current_salesperson`), not via Postgres Row-Level Security. Given this is single-tenant/single-role (decisions #1, #21), RLS may genuinely not be needed — but that's an assumption nobody has explicitly confirmed, only inherited from how Phase 0 happened to wire auth. Worth a deliberate yes/no, not a default.

**Where it lives:** `backend/app/models/activity_log.py`, `backend/app/services/activity_log_service.py`, hooks in `intake_service.py`/`proposal_service.py`/`generation_service.py`/`regeneration_service.py`/`approval_service.py`/`document_service.py`/`delivery_service.py`, `backend/app/api/v1/endpoints/proposals.py` (`/activity`) and `activity.py` (`/activity/export`), `web-app/components/proposals/ActivityTimeline.tsx`, tests in `backend/tests/test_activity_log.py`.

**Open follow-up:** the three items above, plus: no test exists yet that specifically exercises the `BACKGROUND_JOB_FAILED` log line itself (the underlying job-failure *behavior* is well-tested — this only adds a tag to an already-tested code path), so a monitoring rule built against that tag should be smoke-tested against a real failure before being trusted in production.

---

## 2026-09-10 — n8n error branch + backend alert-logging built for schema drift; one real gap remains

**The gap (business view):** The canonical schema lives in three places that have to agree — the Google Form question, the Sheet column header it produces, and n8n's Code node mapping that header to a canonical key for FastAPI (`docs/intake-schema.md`). Nobody but n8n's maintainer can keep those in sync. Three distinct failure shapes, each with a different blast radius:

1. **A required field is renamed or removed on the form.** The Sheet column n8n's Code node looks for no longer exists. FastAPI's Pydantic model correctly rejects this with a 422 (CLAUDE.md: "rejects rather than accepting nulls").
2. **A new field is added to the form.** n8n's Code node doesn't know the new column exists.
3. **A question's wording changes but the column header/canonical key doesn't** (e.g. "Estimated Pricing" reworded to ask something subtly different). Semantic drift, not structural — no schema check anywhere can ever catch this one.

**The fix (implemented 2026-09-10):**
- **n8n workflow** (`Google Sheets Trigger` → `Normalize Sheet Headers to Canonical Keys` Code node → `POST Intake to FastAPI`, retry x3 → `Alert: Intake POST Failed` NoOp on the error output): the Code node validates required fields itself before ever calling FastAPI (fails loud in n8n's own execution log rather than an opaque downstream 422), and — the key design choice — **passes any unmapped Sheet column through under its raw header instead of dropping it.** Combined with `IntakePayload`'s `extra="forbid"` (`backend/app/schemas/intake.py`), that turns case 2 (new field silently dropped) into a real, catchable 422 instead of an invisible data loss. This is stronger than the plan originally written here, which assumed case 2 was undetectable — it isn't, given this mapping choice.
- **Backend logging** (`backend/app/main.py::intake_schema_drift_handler`, a `RequestValidationError` handler scoped by checking `request.url.path == INTAKE_PATH`): every 422 on `/intake` is logged at `ERROR` with a greppable `INTAKE_SCHEMA_DRIFT` tag, the validation errors, and the raw request body — independent of whether n8n's own `Alert` node is wired to a real channel yet or even reachable for a given failure shape. `verify_webhook_secret` (`backend/app/api/v1/endpoints/intake.py`) similarly logs `INTAKE_AUTH_FAILED` on a bad/missing shared secret. The intent: a log-based monitor (CloudWatch/Datadog/Sentry alert rule, whatever this deploys with) can page an admin off these tags without depending on the n8n side at all — two independent alert paths instead of one.
- **Case 3 (semantic drift) still has no technical fix** — undetectable by any check, since well-formed data arrives either way. Mitigation is process only: `docs/intake-schema.md`'s opening line already states the rule (update that file first whenever a form question changes, then the n8n mapping, then let Pydantic be the backstop) — the gap isn't a missing plan, it's that nothing *enforces* the form owner (who may not be the n8n maintainer) actually follows it.

**Where it lives:** `backend/app/main.py` (exception handler), `backend/app/api/v1/endpoints/intake.py` (`verify_webhook_secret` logging), n8n workflow (not version-controlled in this repo — exported JSON reviewed 2026-09-10, live in n8n's own UI).

**The real gap — flagging explicitly to talk through later, not fixed yet:** the n8n Code node's own thrown `Error` (missing required field, case 1's earliest catch point) has no `onError`/`continueErrorOutput` configured on that node. It fails the whole n8n execution before the request ever reaches FastAPI — which means it never reaches n8n's `Alert` node, *and* it never reaches the backend's new `INTAKE_SCHEMA_DRIFT` logging either, since FastAPI never sees the request at all. Right now that specific failure shape is only visible in n8n's own execution-failure list, which nobody is watching. Two ways to close it, worth a real discussion rather than a unilateral pick: (a) wire `continueErrorOutput` on the Code node into the same `Alert` node n8n already has, or (b) have the Code node's validation intentionally *not* throw — instead forward the row to FastAPI anyway with the missing field(s) present as empty/null, letting Pydantic's 422 (and this repo's new backend logging) be the single source of truth for every drift shape instead of splitting detection across two systems. Also still open from the n8n side: the `Alert` NoOp node is a placeholder, not wired to a real channel yet, and `retryOnFail` on the HTTP node retries a 422 the same as a 5xx (harmless, just ~9s of wasted retry before the alert fires).

**Open follow-up:** once `docs/decisions.md` #5 locks the canonical field list, revisit whether the Sheet's raw row (pre-Code-node) is worth logging on *every* intake regardless of success/failure — cheap insurance for reconstructing a lost submission from case 1, and the only way to notice case 2 after the fact if someone later asks "wait, didn't the form used to ask X?"

---

## 2026-09-10 — Brand colors/fonts pulled from koyatalent.com's live CSS, not invented

**The gap (business view):** The PDF and delivery email were originally styled with placeholder colors (an arbitrary indigo) since no brand asset existed in this repo. Shipping a "branded" client-facing document in the wrong colors is worse than shipping it visibly generic — a client who's seen koyatalent.com would notice the mismatch immediately, undermining exactly the professionalism the branding is meant to convey.

**The fix (implemented 2026-09-10):** fetched the live site's compiled CSS (`https://koyatalent.com/_astro/*.css`) and pulled real design tokens rather than guessing from the rendered page: ink `#1f2429`, muted text `#5c646c`, section background `#eef0ee`, border `#d8dbd9`, and the site's own CTA accent blue `#2563eb` (confirmed via its `.solcta__link{color:#2563eb}` class — literally their "solution CTA" link color, not a guess). Font stack matches their `--font` custom property exactly: `"Geist Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`. These constants live once in `backend/app/domain/document.py` and are re-exported into `backend/app/domain/delivery.py` so the PDF and the email that links to it read as one brand, not two.

**Where it lives:** `backend/app/domain/document.py` (`INK`, `MUTED`, `ACCENT`, `BG_LIGHT`, `BORDER`, `FONT_STACK`), `backend/app/domain/delivery.py` (HTML email, same tokens).

**Open follow-up:** WeasyPrint has no network access during PDF rendering, so "Geist Sans" silently falls back to system sans-serif if it isn't installed on whatever machine renders the PDF — never a render failure, but the font may not exactly match the site's until Geist is either installed system-wide or self-hosted and passed to WeasyPrint via `@font-face` with a local file path. No actual logo asset exists either (site uses a text wordmark, matching what this project already did) — if a real logo file ever gets added to the repo, embed it as a `data:` URI in the HTML template rather than a network-fetched image, for the same reason.

---

## 2026-09-10 — Delivery links must not expire before a client opens them

**The gap (business view):** The document link embedded in the delivery email has to work whenever the client eventually clicks it — could be minutes after sending, could be two weeks later if the email sits unread. A naive implementation (email the signed Storage URL directly) would use `get_signed_url`'s default 1-hour expiry (`adapters/storage_client.py`), so any client who doesn't open the email same-day gets a dead link with no way to recover — no client portal, no login, no way for them to ask the system for a fresh one (CLAUDE.md: "clients never authenticate into this system"). A client hitting a broken link on a proposal they were about to say yes to is exactly the kind of silent failure that costs a deal without anyone on the sales side ever finding out why.

**The fix (implemented 2026-09-10):** the email links to this backend's own `GET /public/proposals/{id}/document` — an unauthenticated redirect endpoint that generates a *fresh* signed URL server-side on every hit and 302s to it, rather than emailing the raw signed URL. The emailed link itself (pointing at our own domain, keyed only by the proposal's UUID) never expires; only the short-lived signed URL behind it does, and that's regenerated transparently every time. A client can click a link from a proposal sent months ago and it still works, as long as the underlying document still exists in Storage.

**Where it lives:** `backend/app/api/v1/endpoints/public.py`, `backend/app/services/delivery_service.py::build_document_link`.

**Open follow-up:** the redirect endpoint has no rate limiting or expiry of its own — anyone with a proposal's UUID can hit it indefinitely to regenerate a fresh signed URL for that PDF. UUIDs aren't guessable, and there's no other client-facing surface exposing them beyond the one email sent to the actual client, so the practical risk is low for this single-tenant internal tool — but worth revisiting if proposal IDs ever end up referenced anywhere more exposed (e.g. a future client-visible portal).

---

## 2026-09-10 — Nothing can ever mark a delivery "bounced" yet

**The gap (business view):** `DeliveryRecord.status` includes `bounced` alongside `sent`/`failed` (matching CLAUDE.md's "sent/bounced/failed" requirement), but nothing in the current send path can ever produce that status — `deliver_proposal` only ever writes `sent` (the SMTP call returned without raising) or `failed` (it raised). A bounce is fundamentally different: the SMTP call succeeds (the receiving mail server accepted the message), and the failure — invalid address, full mailbox, spam rejection — arrives later, asynchronously, usually via a bounce notification email or a provider webhook. Today a bounced proposal shows as `DELIVERED`/`sent` in the UI forever, giving the salesperson false confidence that the client received it when they never did — a client who never got a proposal they were expecting, and a salesperson who has no idea why they went quiet.

**The fix:** not implemented — this requires either parsing bounce notification emails or a provider-specific webhook (most transactional email providers offer one), neither of which exists yet since no real SMTP/provider account is configured in this environment (see the entry below). Flagged explicitly rather than left as a silent gap, since "sent" currently means "the SMTP handshake succeeded," not "the client received it."

**Where it lives:** `backend/app/models/delivery.py` (`DeliveryStatus.BOUNCED` — defined, never set), `backend/app/services/delivery_service.py`.

**Open follow-up:** once a real provider is chosen, wire its bounce webhook (or IMAP-based bounce parsing, if using raw SMTP) to a new endpoint that finds the matching `DeliveryRecord` (by provider message ID — worth adding a `provider_message_id` column when this is built) and updates its status to `bounced`, surfaced in the UI so the salesperson can follow up through another channel.

---

## 2026-09-10 — Resend configured and verified with a real send (was: no provider configured)

**The gap (business view):** Originally, no real email provider was configured — the SMTP adapter's failure path was verified but nothing about actual deliverability was. The user provisioned a Resend account and supplied `RESEND_API_KEY` + `EMAIL_FROM_ADDRESS` in `backend/.env`.

**The fix (implemented + verified live 2026-09-10):** switched the email adapter from generic SMTP to Resend's REST API (`backend/app/adapters/email_client.py`, plain `httpx` POST — no vendor SDK dependency). Confirmed end-to-end against the real account: a synthetic proposal driven to `DOCUMENT_READY`, delivered via `deliver_proposal()`, landed as `DeliveryStatus.SENT` with no error, proposal transitioned to `DELIVERED`, and the branded HTML email (with the "View Your Proposal" CTA button) was received. The earlier "SMTP not configured" failure-path verification still stands as the negative-path test — both are covered now.

**Where it lives:** `backend/app/adapters/email_client.py`, `backend/app/core/config.py` (`RESEND_API_KEY`, `EMAIL_FROM_ADDRESS`, `EMAIL_FROM_NAME`).

**Not actually an open follow-up:** the test send used `EMAIL_FROM_ADDRESS=notifications@notify.olaniyigeorge.com` (the verified domain on the dev Resend account) rather than a real `koyatalent.com` address — but on reflection this isn't a gap this project needs to solve. It's a per-deployment env var, not a code decision: whichever company runs this sets `EMAIL_FROM_ADDRESS`/`EMAIL_FROM_NAME` to their own verified sending domain (their sales inbox, `proposals@theirdomain.com`, whatever they already use), the same way they'd set their own Supabase project or Resend account. No code change is needed to support that, so it doesn't belong in this log as a gap — just a reminder that the *dev* value in `backend/.env` is a placeholder, same as the Supabase one below.

---

## 2026-09-10 — Supabase Storage has never been exercised against a real bucket in this environment

**The gap (business view):** `SUPABASE_URL`/`SUPABASE_KEY` in `backend/.env` are placeholder values (`example.supabase.co`), not a real project — distinct from `DATABASE_URL`, which is a genuinely working Postgres connection. Phase 6 (document generation) depends on Supabase Storage for the one thing it does: upload the branded PDF. Every live end-to-end test of `POST /generate-document` in this dev environment ends in `DOCUMENT_GENERATION_FAILED` at the upload step — not because the code is wrong, but because there is no real bucket to reach. If this placeholder is still in place when someone actually tries to generate a document against a real deployment, every proposal will get stuck failing at the same step with the same "can't reach Storage" error, and nobody will have seen it fail against a *real* bucket (wrong bucket name, wrong permissions, CORS, a bucket that doesn't exist yet) until then.

**The fix (verified, not solved):** the failure path itself is solid — confirmed live that a failed upload leaves the Proposal in `DOCUMENT_GENERATION_FAILED` with no `DocumentArtifact` row created (checked directly against the DB), and that retrying from that state correctly re-enters `DOCUMENT_GENERATING` rather than getting stuck. Rendering itself (WeasyPrint, no network dependency) was verified thoroughly via the fidelity test suite. What's unverified is everything Storage-specific: whether `DOCUMENT_STORAGE_BUCKET` ("proposal-documents") needs to be created manually in the Supabase dashboard first (Storage buckets aren't auto-created by an upload call), whether the configured key has Storage write permission, and whether `create_signed_url` behaves as the code assumes.

**Where it lives:** `backend/app/adapters/storage_client.py`, `backend/.env` (`SUPABASE_URL`/`SUPABASE_KEY`), `backend/app/core/config.py` (`DOCUMENT_STORAGE_BUCKET`).

**Open follow-up:** before Phase 6 is considered production-ready, someone with real Supabase project credentials needs to: (1) create the `proposal-documents` bucket (or set `DOCUMENT_STORAGE_BUCKET` to an existing one), (2) confirm the configured key can write to it, (3) run `generate-document` once against it end-to-end and confirm the signed URL from `GET /proposals/{id}/document` actually downloads the PDF.

---

## 2026-09-10 — Client's raw intake wording reached the client verbatim via the pinned Introduction

**The gap (business view):** Introduction was assembled at intake by wrapping `client_needs_summary` and `goals_and_objectives` verbatim in a fixed boilerplate frame (see the superseded 2026-09-09 entry below). Those two fields are free-text answers the client or salesperson typed into a form — if the wording was ungrammatical, a run-on sentence, or genuinely unclear, that exact text went straight into a client-facing proposal with no cleanup step, because nothing in the pipeline ever touched it after intake. A proposal opening with the client's own typo or awkward phrasing reflects worse on the sender than on the client who wrote it, and undermines exactly the "confident, professional" tone the rest of the document (and `HOUSE_TONE` in `generation.py`) is built around. Reported by the user after reviewing a real proposal in the running app.

**The fix (implemented 2026-09-10):** Introduction moved back into `GENERATED_SECTION_KEYS` — it's now a Claude call like Proposed Solution/Deliverables, with an explicit task instruction to paraphrase `client_needs_summary`/`goals_and_objectives` into clean, professional prose and correct grammar/phrasing, while being told just as explicitly not to add any need, goal, or commitment beyond what those two facts state — paraphrasing wording is in scope, inventing content is not. This reintroduces the small hallucination-surface-area cost the 2026-09-09 entry removed (one more Claude call, one more section that could technically drift), which is why that entry's "zero hallucination risk" framing doesn't fully hold anymore — traded deliberately for not shipping the client's own unedited wording back to them. Word target 60-100 words, matching the other generated sections' brevity.

**Where it lives:** `backend/app/domain/generation.py` (`GENERATED_SECTION_KEYS`, `WORD_TARGETS`, `_section_task_description` INTRODUCTION case, `pinned_prefix_for_section` INTRODUCTION case — the pre-generation placeholder only, never the final content), `backend/app/services/intake_service.py` (Introduction now seeded with that placeholder instead of assembled boilerplate), `web-app/lib/proposal-status.ts` (`GENERATED_SECTION_KEYS` — Introduction can now be regenerated with an instruction like any other generated section), tests in `backend/tests/test_generation.py` and `backend/tests/test_regeneration.py`.

**Open follow-up:** the same paraphrase-not-invent risk applies narratively to any future expansion of what gets generated from free-text fields — the mitigation here (an explicit "paraphrasing is in scope, inventing is not" instruction, tested by asserting the prompt contains it) is a prompt-level control, not a verified one; nothing currently checks that a *specific* generated Introduction didn't quietly add a claim. Revisit with a real consistency-check pass (architecture.md §4 point 8) if this turns out to happen in practice. Timeline/Pricing remain deliberately pinned verbatim and out of scope for this kind of "AI cleanup" — see the discussion when this was first proposed: normalizing a date/price via LLM risks the exact numeric drift this project's canonical-facts-layer rule exists to prevent, which is a different risk profile than paraphrasing free-text narrative.

---

## 2026-09-10 — A proposal from n8n intake had no way to leave DRAFT

**The gap (business view):** Every proposal created by the intake webhook lands in `DRAFT` with empty/template-only sections. Phase 2 built the `POST /generate` endpoint and the background Claude job, but no frontend control ever called it — the detail page rendered a fully read-only view with no "Generate" action anywhere. A real inbound request from n8n would sit in `DRAFT` forever from the salesperson's point of view: they'd open the proposal, see boilerplate/empty sections, and have no button to press. That's not a rough edge, it's a dead end in the one flow every proposal must pass through — every single proposal created via the real intake path would have been stuck. Caught by the user reviewing the running app rather than by any test, since the backend endpoint genuinely worked and every backend test that exercised it called it directly by URL.

**The fix (implemented 2026-09-10):** `GenerateProposalButton` — a client component shown in the Proposal Actions panel whenever `proposal.status` is `DRAFT` or `GENERATION_FAILED` (relabeled "Retry Generation" in the latter case). Fires `POST /generate`, then polls `GET /proposals/{id}` every 2.5s (60s timeout) until status leaves `GENERATING`, then refreshes the page — same polling pattern as `RegenerateSectionButton`.

**Where it lives:** `web-app/components/proposals/GenerateProposalButton.tsx`, wired into `web-app/app/proposals/[id]/page.tsx` via `canTriggerGeneration()` in `lib/proposal-status.ts`.

**Open follow-up:** none of Phase 2's "Detail view shows GENERATING status + polling" UI spec (`docs/ui-plan.md` §9) was actually built until now — worth double-checking the equivalent trigger exists for every other phase's primary action before considering that phase done, not just the backend endpoint. (Regeneration and section-editing didn't have this gap because their buttons were built alongside their endpoints in the same phase; full-proposal generation was the one action whose UI trigger got skipped.)

---

## 2026-09-10 — "Approve entire proposal" can rubber-stamp sections nobody actually read

**The gap (business view):** The bulk "Approve Proposal" action (system-flow.md §3: "a single action that approves all remaining sections at once") force-approves every still-pending section in the same call that finalizes the proposal. Combined with self-approval being frictionless by design (decisions #14) and there being no separate approver role (decisions #21), a salesperson can open a freshly-generated proposal and click "Approve Proposal" immediately — no section ever individually reviewed, no read confirmation, nothing stopping a factually-off or badly-toned AI section from reaching `APPROVED` (and eventually the client) with zero human eyes actually on it. The per-section approve flow exists specifically to make review deliberate section-by-section; the bulk action is a designed escape hatch from that deliberateness, and nothing currently signals to the salesperson that clicking it might be skipping review entirely versus just finishing up the last section or two.

**The fix (partial):** the UI is honest about what the bulk action will do rather than hiding it — `ApprovalPanel` shows "will approve N remaining" next to the button whenever `pendingSectionCount > 0`, so a salesperson approving 5 unread sections at least sees that number before clicking, rather than a button that looks identical whether 0 or 6 sections are still pending. This is a visibility nudge, not a guardrail — it doesn't require acknowledgment or block the action.

**Where it lives:** `web-app/components/proposals/ApprovalPanel.tsx`, `backend/app/services/approval_service.py::approve_entire_proposal`.

**Open follow-up:** if this turns out to be a real behavior in practice (not just a theoretical risk), the cheapest next step is requiring a confirmation dialog when `remainingPending > 0` specifically (mirroring `RegenerateSectionButton`'s human-edit confirmation), rather than restricting the bulk action itself — the system-flow.md diagram treats "approve all at once" as an intentional, documented feature, so removing it isn't the fix; making the skip-ahead cost more visible in the moment is.

---

## 2026-09-10 — Claude call logs are a second place client PII lives, with no retention policy of their own

**The gap (business view):** The new `claude_call_logs` table stores the full system/user prompt and Claude's response for every generation and regeneration call — which means client name, company, needs summary, pricing, and timeline (everything in the canonical facts block) now exists verbatim in a second table, not just on `Proposal`. Decisions #18 already flags that Proposal-level PII retention/access-control isn't finalized; this table makes that gap bigger before it's resolved, not smaller — it's an unbounded, ever-growing, unredacted log of exactly the sensitive fields the still-open policy question is about, and every regeneration attempt adds another full copy of that same data.

**The fix (accepted for now, not solved):** `ON DELETE CASCADE` on `proposal_id` means the log rows die when a Proposal does, so there's no leak *beyond* a proposal's own lifetime — but there's no independent retention window shorter than the proposal's, no redaction of PII within stored prompts/responses, and no access control narrower than "any authenticated salesperson can call `GET /proposals/{id}/claude-calls`" (consistent with the rest of the single-role model, per decisions #21, but worth naming explicitly for a table whose entire purpose is holding raw prompt/response text).

**Where it lives:** `backend/app/models/claude_call_log.py`, migration `b637bee3715a`.

**Open follow-up:** fold this into decisions #18 when that retention/access-control policy actually gets defined — don't solve it in isolation for just this table. In the meantime, this table exists purely for internal prompt-improvement observability (per the user's request), not as a system of record anything else reads, so the practical exposure is currently bounded to "whoever can already see the proposal in this single-tenant internal tool."
## 2026-09-10 — A flaky Claude call must not burn one of the salesperson's 3 regeneration attempts

**The gap (business view):** The 3-attempt cap (decisions #13) exists to force a directed, converging regeneration rather than aimless retries — but if a transient failure (rate limit, timeout, a momentary API outage) eats one of only 3 attempts, the salesperson is punished for infrastructure flakiness, not their own instruction quality. Losing a third of their budget to something entirely outside their control is exactly the kind of "the tool wasted my time" moment that kills trust in an AI feature, especially right when they're trying to get a proposal out the door.

**The fix (implemented 2026-09-10, Phase 4):** `ProposalSection.regeneration_count` — the value the 3-attempt cap actually checks — is only incremented in `regeneration_service.regenerate_section()` *after* `generate_text()` succeeds. A `ClaudeGenerationError` (rate limit, timeout, refusal, empty response) is caught, recorded in `regeneration_log` with `outcome: "failed"` and the error message (so the salesperson can still see it happened and roughly why), and the function returns without touching `regeneration_count`, `content`, `version`, or `approval_status` — the section is left exactly as it was, per CLAUDE.md's "a failed call must leave the prior state intact."

**Where it lives:** `backend/app/services/regeneration_service.py` (`regenerate_section`), test `test_regeneration_job_failure_does_not_burn_cap_attempt`.

**Open follow-up:** a salesperson who mistypes an instruction (e.g. a typo that produces a *technically successful* but useless Claude response) still burns a real attempt — there's no distinction between "Claude failed to respond" and "Claude responded but the salesperson didn't like it," nor should there be; only genuine call failures are free retries by design. The escape hatch for a cap-exhausted section is unchanged and unlimited: manual editing (Phase 3) has no attempt cap.

---

## 2026-09-10 — Concurrent writers can silently clobber each other's section edits or regenerations

**The gap (business view):** Nothing in Phase 3 or Phase 4 detects two people (or one person in two tabs) changing the same section at nearly the same time. If salesperson A edits a section by hand while salesperson B's regeneration job for that same section is still in flight, whichever write commits last simply overwrites the other with no warning — the loser's work vanishes without any error, undo, or record that a conflict even happened. This is exactly the "optimistic concurrency" risk architecture.md §6 already named as a general requirement ("use a version/updated-at check... surface a conflict rather than losing data"), now concrete: Phase 4 introduced a second, *asynchronous* writer (the regeneration background job) racing against Phase 3's synchronous edit endpoint on the same row, which is a materially higher-probability collision than two synchronous edits ever were, since the regeneration job can be in flight for several seconds while its target section stays fully editable in the UI the whole time.

**The fix:** not implemented — both `update_section_content()` and `regenerate_section()` read-modify-write a `ProposalSection` with no version check, so this remains a real, live gap, not a theoretical one. Flagged here explicitly rather than silently deferred, per architecture.md §6.

**Where it lives:** `backend/app/services/proposal_service.py::update_section_content`, `backend/app/services/regeneration_service.py::regenerate_section` — both would need to compare an expected `version` (or `updated_at`) against the current row inside the same transaction and raise a conflict (409) instead of writing, if a caller's read is stale.

**Open follow-up:** given the single-tenant, single-role, no-ownership-restriction design (decisions #21), the realistic collision is "two tabs of the same salesperson" or "salesperson edits while their own earlier regeneration for that section is still running" more often than two different salespeople — worth confirming whether that narrower risk still justifies the extra complexity of version-checked writes before building it. Note `RegenerateSectionButton`'s `isRegenerating` state only disables *its own* trigger while a job is in flight — it does not currently disable the sibling `SectionEditor`'s "Edit Content" button for the same section (the two components don't share state), so a salesperson can still start a manual edit on a section while that section's own regeneration job is still running. A shared "this section is busy" flag between the two components would close that specific window cheaply, without needing full version-checked writes.

---

## 2026-09-10 — Truncated sibling summaries could still let a regenerated section drift narratively

**The gap (business view):** Per architecture.md §4 point 3, a regeneration call includes short summaries of every other section (not full text) so the new text doesn't contradict the rest of the proposal. Those summaries are a blunt character-count truncation (`content[:160]`) of each sibling section's actual content, not a real summary — if a sibling's most relevant detail happens to fall after character 160, the regenerated section never sees it and could still narratively drift (e.g. Deliverables lists something Proposed Solution's cut-off tail actually promised). The canonical facts layer (client name, dates, pricing) is unaffected — those are passed verbatim regardless — so this is a narrative-consistency risk only, not a numeric/factual one.

**The fix (accepted, not eliminated):** architecture.md §4 point 8 explicitly marks a real consistency pass (a secondary check that flags contradictions) as optional/deferred, and this project has only two sections that are ever AI-generated (Proposed Solution, Deliverables — see `docs/edge-cases.md` "Generated sections run long"), which narrows the realistic collision surface considerably versus the general N-section case the architecture doc was written for. Truncation was chosen over a real summarization call to avoid doubling Claude spend (one summarization call per sibling, per regeneration) for a low-probability, low-severity failure mode.

**Where it lives:** `backend/app/domain/generation.py::_sibling_summary_block`.

**Open follow-up:** if this turns out to cause visible contradictions in practice, the cheapest fix is raising the truncation length before reaching for a real summarization call or a consistency-check pass — no evidence yet that 160 characters is actually too short for either of the two generated sections' summaries.

---

## 2026-09-09 — Duplicate intake beyond webhook retries

**The gap:** The original idempotency key (`hash(timestamp + email_address)`, `docs/decisions.md` #4) only protects against *n8n retrying a failed delivery of the same Sheet row* — the `Timestamp` column is identical on a retry because it's the same row. It does **not** protect against a human genuinely submitting the same request twice (e.g. a salesperson re-filling the Google Form for the same client because they weren't sure the first one went through, or the client verbally re-requesting the same thing). That second submission gets a *new* `Timestamp` from Google Forms, so the old key treats it as a brand-new proposal — duplicate `Proposal` rows for what is substantively one request.

**The fix:** Idempotency key is now `hash(company_name + normalize(project_scope) + respondent_email)` — no `timestamp` in the key at all. Rationale: a true duplicate (whether a retry or a re-submission) shares these three fields; a genuinely different request from the same person on the same day will describe a different `project_scope`. `normalize()` = lowercase, trim, collapse internal whitespace, strip trailing punctuation, so a re-typed submission with cosmetic differences (extra space, re-cased text, trailing period) still dedupes.

**Where it lives:**
- Computed in FastAPI: `compute_intake_key()` / `normalize_text()` in `backend/app/services/intake_service.py`.
- n8n's Code node does **not** compute the hash — it only does Sheet-column → canonical-key translation (per the existing n8n/FastAPI boundary in `CLAUDE.md`). Keeping the hash algorithm in one place (Python) avoids a second implementation drifting from the first.
- Tests: `test_intake_idempotency_survives_resubmission_with_new_timestamp`, `test_intake_idempotency_ignores_cosmetic_differences` in `backend/tests/test_intake.py`.
- Doc updates: `docs/decisions.md` #4 (marked revised), `docs/intake-schema.md` "Idempotency key" section.

**Open follow-up:** `project_scope` is free text from a Google Form long-answer field — two submissions describing the *same* project in genuinely different wording (not just whitespace/casing) will still fork into two proposals. Current normalization only catches cosmetic differences, not semantic ones. Revisit if this turns out to happen in practice (e.g. fuzzy-match or a Claude-based dedupe check before create) — no evidence yet that it's a real problem, so not building it preemptively.

---

## 2026-09-09 — Generated sections run long; client skim reading suffers

**The gap (business view):** A proposal that reads like a white paper gets skimmed and set aside. Long AI sections look thorough but bury the client's actual problem and your answer in padding. The salesperson then spends edit time cutting, not improving — negating the time save Phase 2 was supposed to deliver. Original prompts had no length target at all (asked for "2-3 paragraphs" per section with no word ceiling), and `CLAUDE_MAX_TOKENS` was set to 2048 — enough headroom for Claude to write several times longer than the reference template ever does.

**The fix (implemented 2026-09-09):** `docs/reference/proposal-template.md` (the actual PRD reference, now on disk) shows every section as one to two short sentences of boilerplate around a pinned fact — there was never a "few paragraphs per section" target to begin with. Reset to match: `WORD_TARGETS` in `backend/app/domain/generation.py` sets 120-200 words for Proposed Solution's generated narrative and 60-120 words for Deliverables, stated explicitly in the prompt ("going over it is treated as a failure to follow instructions, not thoroughness"), and `CLAUDE_MAX_TOKENS` dropped from 2048 to 500. Also found while re-reading the template: **Introduction has no generated placeholder in it at all** — it's fixed boilerplate wrapping `client_needs_summary` and `goals_and_objectives` verbatim — so it's been moved out of the Claude-call path entirely and assembled at intake like Timeline/Pricing. Net effect: one fewer Claude call per proposal (lower cost, faster generation, zero hallucination risk on that section) plus tighter output on the two sections that do need a model call.

**Where it lives:** `backend/app/domain/generation.py` (`WORD_TARGETS`), `backend/app/core/config.py` (`CLAUDE_MAX_TOKENS = 500`), tests in `backend/tests/test_generation.py`. Word-count badge in the UI (Phase 3/4 SectionEditor) is still the open UI-side follow-up below.

**Superseded in part (2026-09-10):** Introduction being pinned-only turned out to trade the hallucination risk this entry solved for a different, equally real problem — a client's ungrammatical/unclear raw form answers reaching the client verbatim, unedited. Introduction is generated again as of 2026-09-10, now with a length target and an explicit paraphrase-don't-invent instruction — see "Client's raw intake wording reached the client verbatim via the pinned Introduction" below. The word-target/`CLAUDE_MAX_TOKENS` fix in this entry still stands for all three generated sections.

**Open follow-up:** the visible word-count badge next to each section (so the salesperson sees at a glance which sections still need trimming after an edit) is still Phase 3/4 UI work, not yet built. If Claude consistently exceeds the new targets in practice, tune the prompt per section — treat as prompt-iteration work, not a code bug. Cap regeneration at 3 (already decided #13) so a "shorten this" instruction can't infinite-loop.

---

## 2026-09-09 — Email sent without a human reviewing the draft

**The gap (business view):** If "send" fires automatically from DOCUMENT_READY or APPROVED, a wrong recipient, a stale link, a generic email body, or a pricing error in the body goes out before anyone sees it. For a proposal that's a sales document, a bad send is a lost opportunity or a damaged first impression — higher cost than a delayed send.

**The fix (proposed):** Email draft is composed (storage link embedded) but not sent until the salesperson reviews and confirms it in the UI. The send button is disabled until the draft is reviewed. Delivery status (sent/bounced/failed) tracked in DeliveryRecord as already planned (decisions #17). This is a Phase 7 change: the "review email draft" step sits between DOCUMENT_READY and DELIVERING. See `decisions.md` #16 follow-up.

**Where it lives:** Phase 7 delivery service + UI (email draft review component). Storage: Supabase Storage default; link embedded in email body, not attachment.

**Open follow-up:** confirm whether the email body is templated (house tone, project-specific merge fields) or fully free-form per send. Templated + editable is the sweet spot — a starting draft the salesperson tweaks, not a blank box and not a locked text.

---

## 2026-09-09 — Human edits lost when a section is regenerated without warning

**The gap (business view):** A salesperson spends 10 minutes tightening a section's wording, then hits regenerate (or a background job does), and the edit vanishes — the section goes back to the AI version. The time spent editing is wasted and the salesperson loses trust in the edit feature. This is the highest-friction failure mode in the review flow because it punishes the exact action (editing) that's supposed to be the value add.

**The fix (implemented 2026-09-10, Phase 4):** `RegenerateSectionButton` (`web-app/components/proposals/RegenerateSectionButton.tsx`) shows a `window.confirm` warning before submitting a regenerate call against any section whose `content_origin` is `human_edited` or `human_edited_after_generation` — "this section has manual edits — regenerating will replace them, this cannot be undone." The 3-attempt cap (decisions #13) limits how often this can happen per section. Sibling sections are never touched by a single-section regenerate (CLAUDE.md constraint; covered by `test_regeneration_job_success_updates_only_targeted_section`).

**Where it lives:** `web-app/components/proposals/RegenerateSectionButton.tsx` (confirm dialog), `backend/app/domain/content_origin.py` (the origin-flip rules this confirmation is warning about).

**Open follow-up — this guard is UI-only, not backend-enforced.** The FastAPI endpoint (`POST /proposals/{id}/sections/{key}/regenerate`) does not itself require any confirmation or check prior content_origin before overwriting — "hiding a button isn't access control" (CLAUDE.md) technically doesn't apply here since this isn't a security boundary, but it does mean a second frontend, a script, or a direct API call bypasses the warning entirely and silently destroys the human edit. If a second client ever calls this API, revisit whether the backend should require an explicit `confirm_overwrite: true` flag when `content_origin` is already human-touched, rather than relying on any one frontend to ask.

---

## 2026-09-09 — Salesperson attribution breaks when the client fills the form

**The gap (business view):** The Google Form can be filled by the salesperson OR the client. `salesperson_name` is free text — if the client types their own name, a different spelling, or leaves it blank, string-matching it to a `User` account misassigns the proposal or leaves it unassigned. The wrong salesperson (or nobody) ends up reviewing a proposal that's sitting in the queue, delaying revenue. Worse, requiring the field at all forces a discovery call to happen before intake — the exact friction step self-serve clients don't need.

**The fix (implemented 2026-09-09):** `salesperson_name` is now optional end-to-end — `IntakePayload.salesperson_name: Optional[str]`, the `proposals.salesperson_name` DB column is nullable (migration `209e98a651b7`), and a blank/whitespace Sheet cell is normalized to `NULL` ("unassigned") by a Pydantic validator rather than stored as a literal empty string. This is a deliberate tradeoff: it removes attribution-at-intake in exchange for removing the discovery-call requirement entirely — a client with an existing form can self-serve straight into the pipeline, shortening the sales cycle. The alternative (exact-match against `User.name`) was rejected — it still misassigns on any spelling difference and does nothing for the "client filled it, no salesperson exists yet" case, which is now the common path this unblocks. Assignment happens after intake via a manual claim/assign step in the review queue — not attempted automatically. See `decisions.md` #20 (now ✅).

**Where it lives:** `backend/app/schemas/intake.py` (`Optional[str]` + `blank_salesperson_name_is_unassigned` validator), `backend/app/models/proposal.py` (nullable column), `backend/migrations/versions/209e98a651b7_make_salesperson_name_nullable.py`, `backend/app/schemas/proposal.py` (response models), tests in `backend/tests/test_intake.py`.

**Open follow-up:** the claim/assign UI + service itself doesn't exist yet — needed before/alongside Phase 5 approval (approval needs an actor). Auto-assignment criteria (round-robin, territory, current load) are explicitly deferred — manual claim is the only mechanism for now, and that's a real ongoing labor cost worth revisiting once proposal volume makes manual triage slow. Confirm whether Supabase Auth users are the actor model before adding a separate `User` table.

---

## 2026-09-09 — Regeneration loses the salesperson's instruction context across attempts

**The gap (business view):** A salesperson regenerates a section 2–3 times to get it right, each time typing a fresh instruction from memory ("more formal", "shorter", "focus on ROI"). There's no record of what they asked on previous attempts, so they repeat themselves, refine by guesswork, or give up after the cap. The 3-attempt cap (#13) becomes frustrating rather than a useful constraint — and the salesperson can't tell whether the last regeneration actually addressed what they meant. For a creative-writing task that's meant to converge, losing the instruction trail per section wastes attempts and degrades the output.

**The fix (implemented 2026-09-10, Phase 4):** `ProposalSection.regeneration_log` (JSON column, migration `8277db7b3a4f`) — an append-only list, one entry per regeneration attempt: `{instruction, attempted_at, outcome, resulting_version | error}`. `RegenerateSectionButton` renders the full history above the instruction textarea whenever a section already has attempts, each one tagged succeeded/failed. The cap (3) counts against the section's `regeneration_count`, not the log length, so a failed attempt still shows in the trail (see the "failed regeneration must not burn a cap attempt" entry below) without spending one of the 3 real tries.

**Where it lives:** `backend/app/models/proposal.py` (`regeneration_log` column), `backend/app/services/regeneration_service.py` (appends an entry on both success and failure), `backend/app/schemas/proposal.py` (`RegenerationLogEntry`), `web-app/components/proposals/RegenerateSectionButton.tsx` (renders it). Tests: `test_regeneration_job_success_updates_only_targeted_section`, `test_regeneration_job_failure_does_not_burn_cap_attempt`.

**Resolved follow-up (decisions #13b):** append-only, no edit/delete — matches "cleaner audit" over "salesperson's editable notes," since the log records what was actually *sent* to Claude, not a scratchpad. If a salesperson wants to revise their intent, that's simply their next attempt's instruction.

---

## YYYY-MM-DD — Short title

```
## YYYY-MM-DD — Short title

**The gap:** What broke / what wasn't handled, concretely (an input, a sequence of actions).

**The fix:** What was changed and why this approach over alternatives.

**Where it lives:** Code, tests, and doc locations touched.

**Open follow-up:** Anything still not handled, so it doesn't get silently forgotten.
```
