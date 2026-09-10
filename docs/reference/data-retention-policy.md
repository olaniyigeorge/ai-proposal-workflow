# Data Retention & PII Policy

Resolves `docs/decisions.md` #18. This is the canonical policy document — cross-referenced from `decisions.md` and `docs/edge-cases.md`, not duplicated there.

## PII and Sensitive Data Policy

Proposal intake data is considered sensitive application data.

### PII fields

The following fields contain or may contain PII:

- `respondent_email`
- `client_name`
- `client_email`
- `company_name`
- `salesperson_name`

### Potentially sensitive business data

The following fields may contain confidential client/business information:

- `client_needs_summary`
- `project_scope`
- `goals_and_objectives`
- `recommended_services`
- `proposed_timeline`
- `estimated_pricing`

### Operational metadata

The following are considered operational metadata:

- proposal ID
- event type
- timestamps
- actor/user ID
- status
- event outcome

Operational logs should avoid storing the actual PII/business payload whenever possible.

## Retention Policy

### Proposals

Proposal records are retained for 24 months after their last meaningful activity.

After the retention period expires, the proposal and associated PII are deleted unless a documented business/legal retention requirement requires longer retention.

### Activity logs

Activity logs are retained for 12 months.

Activity logs should contain operational metadata only and should not contain complete proposal payloads or unnecessary PII.

### Application logs

Application logs are retained for 30 days.

Application logs must not contain:

- client email addresses
- webhook secrets
- authentication tokens
- complete request bodies
- complete proposal payloads

## Implementation status (as of 2026-09-11)

**Done:**
- `ActivityLogEntry` (Phase 8) was audited against this policy and fixed: the `CREATED` event no longer carries `company_name`, and `DELIVERED`/`DELIVERY_FAILED` no longer carry `client_email`/`recipient_email` in description or metadata. Both entity types were already stored properly on `Proposal`/`DeliveryRecord` — the activity log only needs `proposal_id` as the reference, per "operational logs should avoid storing the actual PII/business payload whenever possible." See `backend/app/services/intake_service.py`, `backend/app/services/delivery_service.py`.
- The backend (FastAPI's `get_current_salesperson` dependency) is the sole authorization boundary today — every protected route requires it, confirmed in `backend/app/api/v1/endpoints/proposals.py`.

**Not done — no automated enforcement of any retention window yet.** This document defines the *policy*; nothing currently deletes a `Proposal`, `ActivityLogEntry`, or application log line when its window expires. That needs a scheduled job (e.g. a daily cron/Celery beat task) that:
1. Deletes `activity_log_entries` older than 12 months (independent of their parent `Proposal`'s own lifecycle).
2. Deletes `Proposal` rows (cascading to sections, intake submission, document artifacts, delivery records, Claude call logs, and activity log entries via `ON DELETE CASCADE`) 24 months after `updated_at`, unless flagged for longer retention (no such flag exists yet — would need a `retention_hold` column if this becomes a real requirement).
3. Confirms `logs/server.logs` (`backend/app/utils/logger.py`) is rotated/truncated at 30 days — currently an unbounded, ever-growing file with no rotation configured at all.

**Also not done:** an audit of every existing `logger.*` call site against the "must not contain" list above (client emails, webhook secrets, auth tokens, full request bodies/payloads) — this pass fixed the newly-added `ActivityLogEntry` call sites but did not re-audit the pre-existing `logger.info`/`logger.warning` calls across `generation_service.py`, `regeneration_service.py`, `document_service.py`, `delivery_service.py` for policy compliance. Worth a dedicated pass before this policy is considered enforced rather than just documented. Note also `ClaudeCallLog` (`backend/app/models/claude_call_log.py`) stores full prompts/responses verbatim by design (prompt-improvement observability) — that table is a deliberate, larger exception to "avoid storing the actual payload," already flagged in `docs/edge-cases.md`, and isn't addressed by this policy pass.

## Authorization boundary & defense-in-depth RLS

The backend is the authorization boundary: every protected route requires `get_current_salesperson` (Supabase Auth JWT or the dev token), and business rules (state machine, approval guards, regeneration cap) are enforced in `services/`, never in the frontend. This part is solid and unchanged by this policy.

**Postgres Row-Level Security as defense-in-depth is not implemented, and isn't a quick add given the current connection model** — flagged here rather than silently skipped:

- The backend connects to Supabase Postgres directly via `DATABASE_URL` (`backend/app/core/database.py`), not through Supabase's PostgREST layer — so there is no `request.jwt.claims` / `auth.uid()` context available to RLS policies the way Supabase's own client libraries provide it. A policy written against `auth.uid()` would simply never match anything over this connection.
- The connecting role also owns the tables (it ran every migration in this project), and Postgres table owners bypass RLS by default unless `FORCE ROW LEVEL SECURITY` is set — so naively running `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` would change nothing for this app's own queries while giving a false sense of protection.
- Given this is single-tenant/single-role (decisions #1, #21 — any authenticated salesperson may act on any proposal), the realistic threat RLS would defend against here is narrow: a leaked `DATABASE_URL` used directly, bypassing the FastAPI layer entirely. That's a real risk worth closing, but doing it safely means: (a) a second, lower-privileged Postgres role for the app's own connection (not the migration-owning role), with `FORCE ROW LEVEL SECURITY` on, and (b) policies that check for a session-local flag the app sets after its own auth check succeeds (e.g. `SET LOCAL app.authenticated = true`) rather than anything Supabase-Auth-specific — since there's only one role, the policy would just be "reject all access unless that flag is set for this transaction," which is a real (if blunt) defense-in-depth layer against a bypassed app layer.
- **Deliberately not implemented in this pass**: this changes the app's DB connection/role setup on a live, real Supabase project already used for testing, and doing it wrong (e.g. `FORCE ROW LEVEL SECURITY` without the app setting its session flag correctly) would lock the app out of its own data. That's a bigger, riskier change than fits alongside a documentation-and-log-scrubbing pass — worth its own dedicated piece of work with a rollback plan, not a rushed addition here.

## Future: ownership-based access once real login lands

Real per-salesperson login (decisions #21's still-open follow-up) hasn't landed yet — today every request authenticates as the same dev-token identity or a single undifferentiated Supabase Auth user. Once it does, the intended model (per direct guidance from the project owner, 2026-09-11):

- A `Proposal` with a `salesperson_name`/owner already assigned is editable only by that salesperson.
- A proposal that's genuinely unassigned (`salesperson_name` is `NULL`, decisions #20) can be self-claimed — any salesperson may edit `salesperson_name` to themselves, at which point they own it and can manage it (edit, approve) going forward.

Not implemented yet — blocked on login actually landing, per the project owner. Recorded here so it isn't lost, and so `approval_service`/`proposal_service`'s current "any salesperson may act on any proposal" behavior is understood as the deliberate interim default (decisions #21), not the final model.
