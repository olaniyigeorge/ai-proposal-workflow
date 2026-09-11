# Questions I should expect on the call

Grouped by theme, with a short note on how I'd actually answer each one — not a script, just so I'm not caught flat-footed.

## Model choice / cost

**"Why Sonnet 5 and not Haiku, Opus, or Fable?"**
Because the task is short, single-turn, non-agentic section drafting — the model tiers above Sonnet are built for long-horizon/agentic work this app doesn't do, and I didn't want to pay 2.5-5x more for capability the task can't use. I actually ran the cost math instead of guessing: at 2,000 proposals/month, the entire spread from Haiku to Fable is ~$120/month total — at that scale it's a quality decision, not a cost one. Haiku's a legitimate thing to test later, I just haven't validated it holds up on tone yet.

**"What would change your model choice?"**
Real usage data showing quality problems on Sonnet, or a 10x volume jump where the Opus/Fable premium becomes a real line item worth re-justifying against measured (not assumed) quality gains.

## Reliability / failure handling

**"What happens if the Claude API is down or rate-limited mid-generation?"**
The call fails cleanly — caught, logged, and the section is left in its last-known-good state, never blank or half-written. Honest gap: I don't currently retry with backoff, I just handle the failure safely. That's on my punch list, not something I'm going to pretend is done.

**"What happens if someone submits the same form twice?"**
It's a no-op, not a duplicate. Dedupe is a hash of company name + normalized project scope + respondent email — not timestamp — so it catches actual duplicate submissions, not just retries.

**"Does a failed regeneration burn one of the 3 attempts?"**
No, and that was a deliberate fix — the attempt counter only increments after a successful call. Otherwise a flaky API call would eat into a budget that's supposed to be about instruction quality, not infrastructure luck.

## The AI's boundaries

**"How do you stop the AI from making up pricing, dates, or client details?"**
Those never go through the model at all — they're pinned verbatim in a facts layer and inserted directly. The AI only ever writes the narrative around them, and the prompt explicitly forbids it from restating or paraphrasing the actual number/date itself.

**"What if the intake data is garbage or placeholder-shaped?"**
Caught this in testing — a real example had answers like "Goals: Goals." The AI will happily write a clean, confident-sounding proposal around nothing. Rather than blocking generation (which risks stopping someone who actually has the missing context), I built a "this looks thin" flag with a one-click "email client for more detail" action, so a human decides what to do with it.

## Approval / control

**"Can a salesperson approve their own proposal?"**
Yes, by design — there's one role in this system, no separate approver. That's the expected path, not something to reject.

**"What stops something from being sent without a human actually checking it?"**
Every state transition is enforced server-side, not just a hidden button. Approval requires every section individually approved before the proposal-level approval unlocks. Delivery requires the salesperson to review the actual composed email before clicking send — nothing auto-sends.

**"What happens if someone edits a section after it's already approved?"**
That invalidates the existing approval and forces the proposal back into review — it can't sit in "Approved" pointing at content nobody actually signed off on.

## Security

**"Any hardcoded secrets or exposed keys?"**
None in the codebase — checked directly, `.env` was never committed. The one real open item: the n8n workflow export currently has the webhook secret typed in as plaintext rather than pulled from a credential store. Flagged it, fixing it before that workflow gets shared anywhere.

**"What's in the frontend that could leak something?"**
Only the public Supabase anon key, which is meant to be public — no service-role key, no API keys, nothing sensitive reachable from browser JS.

## Scope / what's not done

**"What would you build next if you had another week?"**
Retry-with-backoff on the Claude calls (currently handled safely but not retried), frontend tests (backend's well-tested, web-app isn't yet), and finishing the section-version-history gap — right now there's no way to reconstruct exactly what a client received if content changes after delivery.

**"Why does the PDF only generate once, after approval?"**
Content needs to stay editable right up until approval, but once it's approved, what gets sent should match exactly what was signed off on — no "draft PDF" floating around that might not match the final approved text.

## The honest one I should be ready for

**"Is there anything you'd flag before I find it myself?"**
Yes — the n8n secret placement, the missing retry/backoff, and the fact that the Render free-tier backend cold-starts after ~15 minutes idle (I added a partial mitigation, not a full fix). I'd rather say all three out loud than have them come up as "gotcha" findings.
