---
name: business-edge-case-review
description: Review a feature, flow, or design decision for edge cases from a business-owner perspective (not just a correctness/QA perspective) — what breaks in practice, what it costs the business in time/money/trust, and how the fix could be pushed further to compound the win. Use when asked to "spot edge cases", "review from a business perspective", "what could go wrong here for the business", or before/after building a workflow step that touches money, client-facing content, human review, or attribution/ownership.
---

# Business Edge-Case Review

A correctness review asks "does this crash or produce wrong output." This
skill asks a different question: **"what happens to the business — the
sales team, the client relationship, the bottom line — when this behaves
unexpectedly?"** A flow can be 100% bug-free and still cost the business
real money or credibility if nobody thought through the operational edge
case.

Use this skill when reviewing: a new feature before it ships, an existing
flow that's shown a rough edge, or a design decision that changes who does
what (attribution, approval, delivery, automation replacing a human step).

## The four questions, every time

For each edge case you find, answer all four — this is what separates a
business review from a bug report:

1. **What breaks, concretely?** A specific input, sequence, or actor (not
   "invalid data" — "a client fills the form without a salesperson name
   because they don't have that field, so what does it default to?").
2. **What does it cost the business if unaddressed?** Name the actual cost:
   lost deal (client sees an error / stale info / wrong price), wasted labor
   (salesperson redoes work, or spends more time fixing than the automation
   saved), delayed revenue (proposal stuck unassigned in a queue), trust/brand
   damage (a bad email goes out, a client-facing typo, a broken link),
   compliance/legal exposure (PII mishandled). Vague costs ("bad UX") are not
   acceptable — tie it to time, money, or a concrete relationship risk.
3. **What's the fix, and why this one over the obvious alternative?** State
   the fix and name at least one alternative you're not picking and why. If
   the fix trades one risk for another (e.g. "make the field optional" trades
   attribution-accuracy for ingestion-ease), say so explicitly — the business
   owner needs the tradeoff, not just the answer.
4. **How could this be pushed further to compound the win?** A defensive fix
   stops the bleeding; a good business review also asks whether the same
   change unlocks something — e.g. "making salesperson_name optional doesn't
   just fix a data bug, it removes the requirement for a discovery call
   before intake, which shortens the sales cycle and lets clients self-serve."
   Not every edge case has a "compound the win" angle — say so if it
   genuinely doesn't, don't force one.

## Where the highest-value edge cases hide

Prioritize scanning these areas — they're where a technically-correct system
still fails the business:

- **Automation replacing a human step.** Every place a human used to be in
  the loop (a discovery call, a manual review, a sign-off) and now isn't —
  what judgment did that human apply that the system needs to replicate or
  explicitly punt on? (E.g. matching a submission to the right salesperson,
  or catching a client's implicit budget signal a form field doesn't capture.)
- **Anything client-facing that can go out wrong.** Emails, documents,
  links — once sent, it can't be unsent. Look for: what if the draft is
  reviewed but the underlying data changed after review and before send?
  What if a link expires, points to the wrong storage object, or the
  attachment/PDF generation silently produced a stale version?
  What if generated content name-drops a fact that was never true?
- **Free-text fields treated as identifiers.** A name, an email, a company —
  anywhere a string is used to *match* or *assign* rather than just *display*.
  These are exactly where automation quietly does the wrong thing without
  ever raising an error (the earlier salesperson-attribution case is the
  template for this pattern).
- **Anything with a hard cap or a cost per call.** Regeneration limits, API
  call budgets, retry limits — what's the business cost when a legitimate
  user hits the cap mid-task (a salesperson genuinely needs a 4th
  regeneration to land the tone) versus the cost of not having the cap at all
  (unbounded spend, or an abuse vector)?
- **Anything measured by a human afterward.** Word count / length, tone,
  formatting — things a machine can produce "correctly" per its instructions
  but that a human still has to fix by hand, silently costing back the time
  the automation was supposed to save. If nobody is checking whether the
  automation's output actually saves editing time versus creating it, that's
  itself an edge case worth naming.
- **State that can go stale between steps.** A proposal reviewed, then
  edited before send; a price quoted, then changed; an assignment made, then
  the assignee going on leave. Anywhere there's a gap between "decision made"
  and "action taken," ask what happens if the world changed in between.

## Output format

Append findings to `docs/edge-cases.md` (or wherever this project keeps its
edge-case log) using its existing entry format, **but require the business
framing inside `The gap` and add it explicitly if the existing template
doesn't ask for it**:

```
## YYYY-MM-DD — Short title

**The gap (business view):** What breaks, concretely — and what it costs the
business (time, money, a specific relationship/trust risk) if unaddressed.

**The fix (proposed):** What to change, and the alternative you're not
picking (state the tradeoff).

**Where it lives:** Code, tests, and doc locations touched or to touch.

**Open follow-up:** What's still unhandled — and, if there is one, how this
fix could be pushed further to compound the win for the business.
```

If the project has an existing decision log (e.g. `docs/decisions.md`) and
this edge case resolves or changes an open question there, update that
entry too — the edge-case log explains *why*, the decision log states
*what's current*. Don't let the two drift apart.

## What this skill is not

- Not a correctness/security review — use a code-review or security-review
  skill for that; this skill assumes the code works as written and asks
  whether *as written* is good for the business.
- Not a place to invent hypothetical edge cases with no plausible trigger.
  Every finding needs a concrete "what input/actor/sequence causes this" —
  if you can't name one, it's speculation, not an edge case.
- Not a substitute for asking the business owner when the tradeoff is
  genuinely a judgment call (e.g. "should we ever auto-send without human
  review to speed up the highest-trust clients") — flag those as open
  questions, don't silently pick a side.
