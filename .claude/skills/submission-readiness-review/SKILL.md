---
name: submission-readiness-review
description: Self-check the current project against the cohort's "Building Production-Ready Systems" grading rubric before submission — the five production skills (error handling, edge cases, cost awareness, idempotency, security), the three grading dimensions (Technical Execution, Communication, Critical Thinking), and the submission checklist (workflow, one-pager, video, reflections, shareable link). Use before submitting a weekly project, when asked "am I ready to submit", "grade my project", "check this against the rubric", or "what will I lose points on".
---

# Submission Readiness Review

This skill runs the project through the cohort's own grading lens before a
human grader does — so gaps get found and fixed before Friday 23:59, not
after. It is deliberately literal about the rubric: don't soften a finding
because the code is otherwise good, and don't invent a passing grade the
evidence doesn't support.

Read the project's own `CLAUDE.md` / README / PRD first so findings are
grounded in what this specific project claims to do — a generic checklist
run without that context produces generic, low-value findings.

## What "production-ready" means here (frame every finding through this)

A production-ready system assumes: inputs will be messy/incomplete, external
services may fail, automations may run more than once, and someone else
depends on the outcome. The job is not to prevent every failure — it's to
design for failure being visible and survivable. If the strongest thing you
can say about the code is "it works when everything goes right," that's a
finding, not a pass.

## The five production skills — check each one explicitly

For each, name the concrete evidence (file:line, or "not found") — don't
grade on vibes.

1. **Error handling & failure visibility.** For every external call (API,
   AI model, database, webhook, file/storage write): is failure caught? Does
   it surface somewhere a human can see it (log, status field, UI state,
   returned error), or does it fail silently / crash uncaught / get swallowed
   by a bare `except: pass`? A failure nobody can see is worse than a crash —
   at least a crash is visible. Grep for bare excepts, empty catch blocks,
   and any place a failure would leave state half-written.

2. **Edge cases.** Missing/incomplete input, unexpected formats/values,
   duplicate or out-of-order events, empty lists, null/optional fields
   actually being null. You don't need every edge case handled — you need
   evidence the important ones were *identified* and a deliberate choice was
   made (handle it, reject it clearly, or document it as a known gap). An
   edge-case log (this project's own `docs/edge-cases.md` if present) is
   exactly the kind of evidence a grader wants to see — check whether it
   exists, is current, and actually reflects gaps in the code, not just gaps
   that were talked about.

3. **Cost awareness & resource usage.** Does anything call an LLM/API when it
   doesn't need to (no dedupe, no early-exit, recomputing instead of
   reusing)? Is the chosen model appropriate for the task, and is that choice
   *justified* somewhere (reflections, docs, a comment) rather than left as
   "whatever the default was"? "It was the default" is explicitly called out
   in the rubric as not an answer — if the project uses the largest available
   model for a task a smaller one would handle, that is a finding to report,
   not a detail to skip. Check for caching/memoization of expensive calls and
   whether retries have backoff/caps (an uncapped retry loop is a cost bug,
   not just a reliability one).

4. **Unbreakable / idempotent workflows.** Can the exact same trigger/webhook/
   run happen twice without creating duplicate records or corrupting state?
   Look for an idempotency key, upsert-not-insert, unique constraints, or
   equivalent — and a test proving the duplicate case, not just the happy
   path. If a workflow can be safely re-run after a partial failure, say so
   and cite the mechanism; if it can't, say exactly what breaks on a second
   run.

5. **Security & data responsibility.** This one is pass/fail, not a spectrum
   — a single hardcoded secret is disqualifying regardless of how good the
   rest of the system is. Run all of these, don't sample:
   - `git ls-files | xargs grep -lE "(sk-ant-|sk-proj-|AKIA[0-9A-Z]{16}|api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"]{8,}"` (adjust per stack) across tracked files — and separately across **history**, since a since-deleted key is still in the repo: `git log --all -p | grep -E "same pattern"` (or `git log --all --source -- '*.env'` to check no `.env` variant was ever tracked, even if removed later).
   - Confirm `.env`/credentials files are gitignored *and* were never committed before the gitignore rule existed (`git log --all --oneline -- <path>` should be empty).
   - For an n8n workflow export specifically: credentials must be referenced by a credential/environment reference, never inlined as plaintext in the exported JSON.
   - For a shipped frontend: no API key or service-role credential reachable from browser-visible JS/network calls — anything the client can call directly must go through a backend that holds the real secret.
   - Scan any committed screenshots/video scripts for visible tokens, real customer PII, or internal URLs that shouldn't be public.

## The three grading dimensions — give an honest 1-5 per dimension

Use the rubric's own level descriptions, don't paraphrase them into
something softer:

- **Technical Execution**: 1 = only works in ideal conditions; 3 = fully
  functional, handles common edge cases; 5 = goes beyond the PRD to improve
  reliability/clarity/robustness, failure modes well handled. Base the score
  on what you actually found in the five checks above, not on effort or
  code volume.
- **Communication (video)**: this skill can't watch the video, but it CAN
  check whether the one-pager and reflections exist, are current, and would
  let someone unfamiliar understand purpose/behavior/how-to-use without
  being overly technical. Flag if the one-pager is missing a required
  section (Header, Purpose & Success Criteria, How it Works, How to Use It).
- **Critical Thinking (reflections)**: read the reflections file/doc if one
  exists. 1-2 = describes what was built; 3 = identifies challenges but
  doesn't go deeper; 4-5 = analyzes trade-offs (including *which model and
  why*, required from Week 2 on), extracts lessons, critiques its own work.
  If reflections don't mention the model choice and its trade-off, call that
  out explicitly — it's named in the rubric as commonly skipped.

Report all three even when you can't fully assess one (e.g., no video to
watch) — say what's assessable from the repo and what needs the human's own
judgment.

## Submission checklist (run literally, in this order)

1. **Workflow**: is it actually runnable, not broken? Does it match what the
   video/docs claim it does? Does it include the error handling / idempotency
   found (or not found) above?
2. **Shareable link (Week 3+)**: does it exist, and can this skill verify it
   loads (fetch it, check for a non-error response) from outside any
   authenticated/local-only context? Does the response leak a key in a
   script tag, network call, or config blob sent to the browser? A dead link
   is called out in the rubric as the single most common way a strong
   project loses points — treat "I'll check it later" as a finding now, not
   later.
3. **One-pager**: exists, has the required sections, reads as something a
   non-technical stakeholder could rely on (not a code dump).
4. **Demo video**: can't watch it, but confirm a video/script/storyboard
   exists and, if a script exists, that it covers: who/what, the business
   problem, happy path demo, at least one failure/edge-case demo, key
   artefacts, trade-off reflection — per the required flow. Flag missing
   beats.
5. **Reflections**: exists, current, addresses model choice/trade-off from
   Week 2 on.

## Output format

Produce, in this order:

1. **One-paragraph verdict**: ready to submit, or not — and the single
   biggest risk if not (usually security or the shareable link).
2. **Five production skills**, each with: evidence found (file:line or
   "none found"), and a verdict (solid / partial / missing).
3. **Grading estimate table**: `| Dimension | Est. score /5 | Why |` for
   Technical Execution, Communication, Critical Thinking — mark
   Communication/parts of Critical Thinking as "needs your judgment" where
   this skill can't see the video.
4. **Security scan results** — explicit pass/fail, not folded into the
   general list, since it's the one disqualifying category.
5. **Prioritized punch list**: ordered by (a) anything disqualifying
   (exposed secret, dead link) first, (b) anything that moves a dimension
   score, (c) polish. Each item: what to do, where, and why it matters for
   the grade — not just "fix this."

Keep the tone matter-of-fact and specific. The goal is a list the user can
work through before the deadline, not a lecture on production readiness.

## What this skill does not do

- Does not watch the demo video or judge its pacing/delivery — say so
  explicitly rather than guessing a Communication score from the repo alone.
- Does not submit anything or modify the workflow/one-pager/reflections
  unless asked — this is a review, apply fixes only when the user asks for
  them.
- Does not pad findings to look thorough. If a check passes cleanly, say so
  in one line and move on — don't manufacture minor nitpicks to fill space.
