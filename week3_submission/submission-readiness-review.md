# Am I actually ready to submit? (Week 3 self-check)

Ran this against the rubric on 2026-09-11. Short version: **the build itself is in good shape, but the submission package has a few real gaps that will cost points if I don't close them before hitting submit.**

## The one thing that will sink this if I forget it

The Week3 submission doc (`Week3_Submission_Filled.docx`) still has these as literal placeholders:

- Application link — blank
- Generated proposal sample — blank
- Video walkthrough link — blank
- One-page documentation link — blank
- Anyten/n8n workflow link — blank

The rubric literally calls a dead/missing link the #1 way a strong project loses points. Doesn't matter how good the code is if the grader can't get to it. **This is priority zero, not polish.**

Good news: the app is actually deployed (frontend on Vercel, backend on Render — see `docs/submission/one-pager.md` for the URLs), so this is a "paste the link in" job, not a "go build something" job. Just don't forget to do it.

## Five production skills — where I actually stand

**1. Error handling** — solid. Every external call (Claude, Storage, email, PDF render, the n8n webhook) is wrapped and fails into a visible state, not a silent one. No bare `except:` anywhere. Genuinely good here.

**2. Edge cases** — solid, honestly the strongest part of the submission. `docs/edge-cases.md` has 30+ dated, real entries — not "we thought about X," but "X actually broke, here's the fix, here's what's still open." That log is worth pointing to directly if asked to prove I thought about failure modes.

**3. Cost awareness — partial, and I should be upfront about the gap.** I did the actual model-choice math (see `model-cost-analysis.md` and reflections) — that part's solid and the reasoning holds up. But when I actually checked the code: **there's no retry/backoff on the Claude calls.** The architecture doc talks about "retry with exponential backoff for transient failures," but the real adapter just calls the API once and catches the exception — no retry loop, no backoff library. A failed call is handled *safely* (no corrupted state, no wasted regeneration attempt), it's just not *retried*. Worth naming this honestly on the call rather than getting caught claiming something that isn't there.

**4. Idempotency** — solid. Real hash-based dedupe (company + scope + email, not timestamp), DB unique constraint, upsert not insert, three dedicated tests proving the duplicate case.

**5. Security — mostly clean, one real open item.** No hardcoded secrets in the codebase, `.env` never committed, frontend only ever holds the public Supabase anon key. But: **the n8n workflow export still has the webhook secret typed in as plaintext, not pulled from a credential/vault.** If that workflow JSON gets shared as part of the "Anyten/n8n workflow link" deliverable, that's a live secret going out the door. Fix this before pasting that link in, not after.

## Grading estimate (my honest guess, not a grader's)

| Dimension | Est. /5 | Why |
|---|---|---|
| Technical Execution | 4 | Real state machine, real guards, real background jobs, real audit trail. Docked because of the missing retry/backoff and because there are zero frontend tests — backend's well-tested, web-app isn't. |
| Communication (video + one-pager) | Can't self-grade the video — that's on me to record well. One-pager now exists (see this folder) and should read fine to a non-technical person. |
| Critical Thinking (reflections) | Should land 4-5 if I use the reflections doc as written — it names the model trade-off explicitly (required from Week 2+) and self-critiques real gaps instead of just describing what got built. |

## Punch list, in order

1. **Fill in every blank in `Week3_Submission_Filled.docx`** — application link, proposal sample, video link, one-pager link, n8n link. Nothing else matters if these are empty.
2. **Move the n8n webhook secret out of the exported JSON before sharing that workflow link.** Use n8n's credential store, not a literal header value.
3. **Warm up the Render backend right before recording the demo** (free tier cold-starts, ~15-20s first hit) or narrate it on video so it doesn't look broken.
4. **Say the retry/backoff gap out loud in reflections or on the call** rather than hoping nobody checks — it's a small, honest gap, and naming it yourself reads a lot better than getting caught not knowing.
5. **Optional polish**: the top-level README's "Open items" list is stale against `docs/decisions.md` (a few items marked open there are actually resolved) — five-minute fix, not score-critical, but a grader who reads both will notice the mismatch.

## Bottom line

Not a "go rebuild things" situation. It's a "go paste four links and fix one secret" situation. The engineering underneath is genuinely in good shape — the risk here is entirely in the submission packaging, not the product.
