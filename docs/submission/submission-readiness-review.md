# Submission Readiness Review

Run against the cohort's "Building Production-Ready Systems" rubric on 2026-09-11, and re-checked after that day's fixes (real per-salesperson login, sidebar layout, mojibake characters, thin-intake flagging, RLS groundwork, retention enforcement script). Deployed at:

- Frontend: https://ai-proposal-workflow.vercel.app/
- Backend: https://ai-proposal-workflow.onrender.com/ (Swagger docs at `/api/v1/docs`)

## Verdict

**Close, not yet ready to submit.** The engineering is genuinely strong — one of the most thoroughly self-documented codebases reviewed against this rubric (25+ dated edge-case entries, a live decision log, real tests for illegal-transition/idempotency/cap-enforcement/retention). The biggest remaining risks are **outside the code**: no one-pager or reflections doc existed until this pass (now added alongside this review), the n8n webhook secret is still inline plaintext rather than in a secret manager, and the Render backend is on a free tier that cold-starts (503 → works within ~15-20s) — a grader hitting the link cold could see a failure on first load.

## The five production skills

| Skill | Evidence | Verdict |
|---|---|---|
| **Error handling & failure visibility** | Every external call (Claude, Storage, email, PDF render, n8n intake) wrapped, logged with a greppable tag (`BACKGROUND_JOB_FAILED`, `INTAKE_SCHEMA_DRIFT`, `INTAKE_AUTH_FAILED` — `app/main.py`, `app/services/*_service.py`), and routed to a `*_FAILED` status. No bare `except:` anywhere in `app/`. | **Solid** |
| **Edge cases** | `docs/edge-cases.md` — 25+ entries, actively updated same-day as code changes. Newest entries specifically caught a real regression (inline n8n secret) and a real UX gap (thin/placeholder intake reaching Claude ungated). | **Solid** |
| **Cost awareness** | Regeneration hard-capped at 3/section, mandatory instruction, failed calls don't burn the cap (tested). Model choice (`claude-sonnet-5`) is now justified with real numbers — see `submission/model-cost-analysis.md`: at 2,000 proposals/month the cost spread across every available model is ~$120/month total, so Sonnet 5 is kept deliberately, not by default. | **Solid** (was Partial before the cost analysis existed) |
| **Idempotency** | `compute_intake_key` (hash of company+scope+email, not timestamp), DB unique constraint, upsert-not-insert, three dedicated tests. | **Solid** |
| **Security & data responsibility** | See scan below. | **Partial — one real, unresolved item** |

## Grading estimate

| Dimension | Est. score /5 | Why |
|---|---|---|
| Technical Execution | **4** | Handles common edge cases well beyond baseline; state machine guards, background jobs, activity audit trail, retention enforcement, RLS groundwork. Docked from 5 for the still-open items in the punch list (secret manager migration, RLS cutover not yet flipped, no automated retention *schedule* wired up yet — the script exists and is tested, but nothing calls it on a timer). |
| Communication (one-pager/video) | **One-pager now exists** (`submission/one-pager.md`) — video still needs your own judgment; this review can't watch it. |
| Critical Thinking (reflections) | **Reflections doc now exists** (`submission/reflections.md`), explicitly addresses model choice/trade-off (the rubric's most commonly-skipped item) and self-critiques the RLS/retention gaps. Read it and add anything only you know (what was hardest, what you'd redo). |

## Security scan — explicit results

- ✅ No secret-shaped literals in tracked files (checked again post-changes).
- ✅ No `.env` ever tracked in git history; only `.env.example` files with placeholders (backend and now web-app).
- ✅ Frontend never holds a service-role/API key — only the Supabase **anon** key (public by design) and the backend Bearer token.
- ✅ Real per-salesperson login now exists (Supabase Auth, both sign-in and self-serve sign-up) — the earlier gap ("still uses only the dev salesperson option") is closed. **Found and fixed in the same pass**: `getClientAuthToken()`/`setClientAuthToken()` disagreed on the cookie name, so a real login's token was written to one cookie and never actually read back — every session silently fell through to the dev token regardless of who signed in. Fixed to a single shared constant.
- ⚠️ **Still open, disqualifying per the rubric's pass/fail security rule**: the n8n workflow's webhook secret is inline plaintext in the exported JSON, not a credential/secret-manager reference (`docs/edge-cases.md`, 2026-09-11). Accepted as the first go-live task, not yet done.
- ⚠️ Self-serve sign-up has no invite gate or email-domain restriction — anyone with the login URL can create a real account and see client PII once signed in. Low severity given the single-role model (no privilege to escalate to), but worth a decision before wide distribution.

## Live deployment check (2026-09-11)

- Backend (`onrender.com`) returned `503` on first hit, then served Swagger docs correctly ~15-20s later — a Render free-tier cold start, not a broken deploy. A grader/demo-video viewer hitting it cold could see a failure; consider a paid tier or an uptime ping before the demo, or explicitly narrate "give it a moment to wake up" in the video.
- Frontend (`vercel.app`) showed a stuck "Checking authorization..." state when fetched by an automated (non-JS-executing) tool — traced to `AuthGuard.tsx`'s synchronous client check, which should resolve in under a second in a real browser after hydration. Not confirmed as a real user-facing bug; verify in an actual browser before assuming it's fine.
- Supabase project itself (`cxbigqlpqyiittzkyzki.supabase.co`) is live and reachable — a user-reported `ERR_NAME_NOT_RESOLVED` on login traced to something local to that browser/network (extension, stale DNS, or a malformed env var value with whitespace), not a dead project.

## Prioritized punch list

1. **[Disqualifying, security] Move the n8n webhook secret to a secret manager** — still plaintext in the workflow export.
2. **[Blocks a clean demo] Warm the Render backend before recording/demoing**, or accept and narrate the cold-start delay.
3. **[Decision needed] Gate or accept open self-serve signup** — restrict to a company email domain, or explicitly accept it given the single-role model, and say which in reflections.
4. **[Polish] Finish the RLS cutover** if time allows — the groundwork (role, policies, session-flag code) is in place and applied; the actual `DATABASE_URL` role swap is a manual, deliberately-not-automated step (see `docs/reference/data-retention-policy.md`).
5. **[Polish] Schedule `scripts/enforce_retention.py`** on an actual cron (e.g. Render Cron Job) — it's built and tested but nothing calls it yet.
6. **[Polish] Verify the AuthGuard "Checking authorization..." behavior in a real browser**, not just an automated fetch, to close out that finding definitively.
