# Reflections

## Clarifying questions I'd actually ask if this landed on my desk

Ownership, first. When a proposal's "assigned" to a salesperson, does that mean only they can touch it, or can anyone help out? I picked "only they can act on it" as a default and moved on — that's a guess, not something the PRD told me.

Data source, second. Should intake be a real structured form, or should it just take raw notes/transcripts from the call and figure it out? Those two paths need completely different validation and UX, so I'd want that answered before building either one, not after.

Then there's a pile of smaller stuff the PRD just didn't say: what currency prices are in, whether there's a separate approver role or the salesperson just approves their own work, how people log in, how we handle the fact that every proposal has real client PII in it, what "delivered" actually needs to mean (email accepted by the provider? opened? something else?), how long we keep retrying a failed send. I made calls on all of this and wrote them down as I went (`docs/decisions.md`, `docs/edge-cases.md`) — the ones I couldn't confidently guess are exactly the questions above.

## The hardest part, and why

Honestly wasn't the AI integration. It was making real product calls off a thin spec. Small example: nothing said what currency to quote prices in — I just had to pick something and keep moving. Same story with auth and proposal ownership — the PRD didn't say who's allowed to act on what, so I had to decide, then make the rest of the system consistent with that decision. The pattern underneath both: a thin spec pushes product decisions into implementation, where they're more expensive to get wrong.

## What I'd do differently next time

Lock down the open questions *before* writing code, not while writing it. I ended up making a string of judgment calls mid-build — approval role vs. self-approval, auth model, PII handling, what "delivered" means, retry cutoffs, whether to generate straight off intake or write a fuller brief first, which sections are even AI-written. All of that would've been cheaper to settle in a 30-minute conversation up front than to half-decide and revisit later. One call I'm glad I made either way: post-approval regeneration invalidates the existing approval rather than quietly patching approved content — an approved proposal should never silently drift.

## Edge cases I actually built for

- **Post-approval regen doesn't sneak past approval.** Regenerate a section after approval, and the approval resets — no stale "Approved" sitting on top of changed content.
- **PII is treated as a real constraint, not an afterthought.** Every proposal has client name/email/company in it. Activity logging exists specifically so there's an audit trail, even before the retention policy was fully nailed down.
- **A failed background job doesn't corrupt anything.** Claude call fails, PDF render fails, email fails — the prior state stays intact, nothing half-written. And a failed regeneration attempt doesn't burn one of the salesperson's 3 tries — you shouldn't get punished for the API having a bad moment.
- **Form/schema drift.** If a form question gets renamed, a naive column-mapping breaks silently. I mapped on keyword matching against canonical keys instead of exact column names, and anything that still fails to map gets written to an error sheet with the actual failure visible — not swallowed.
- **Empty-looking-but-not-empty input.** Someone types a space or an empty-looking string into a required field — that's not "missing," technically, but it's not usable either. I flag whitespace-only/empty values as insufficient rather than trusting "field wasn't null."
- **Pinned facts stay pinned.** Pricing, dates, and timeline are locked verbatim in a facts layer and reinforced in every prompt so regenerating the narrative around them never lets the model quietly rephrase a number or date.

## Model choice: Claude Sonnet 5, and the actual reasoning

I didn't just take the default — I checked what each tier's actually good at and ran the cost math (see `model-cost-analysis.md`).

The three alternatives, and why they're wrong for this: Fable 5.1 and Opus 5 are built for long-horizon agentic work and complex coding — this app does neither, it's short, single-turn section drafting with a hard 500-token cap. Paying 2.5-5x more for reasoning capability this task can't use would've been the wrong call. Haiku 4.5 would save real money at scale, but I hadn't actually tested whether it holds up on tone and quality for this specific job, so I didn't just guess my way into a downgrade.

The number that actually settled it: at a realistic 2,000 proposals/month, the *entire spread* across every model — cheapest to most expensive — comes out to about $120/month. At that scale this isn't a cost decision at all, it's a quality decision. So I kept Sonnet 5 deliberately: it's positioned as the best speed/intelligence balance, which is exactly what short, non-agentic, client-facing copy needs, and a single bad section reaching a client costs a lot more than the entire monthly model bill regardless of which of the four I'd picked.

## A trade-off that bit me, and the actual lesson

I built the activity-log audit trail before the PII/retention policy existed. That was backwards — the first version logged `company_name` on creation and `client_email` on delivery, which directly violated a policy that didn't even exist yet. Once the retention policy landed, I had to go back and strip PII out of already-shipped code and already-written tests. Lesson: for anything that's explicitly a compliance/audit feature, write the data policy *first*, even a rough one, before building the thing that logs against it.

## Self-critique — things I'd rather flag myself than have someone else find

- The n8n webhook secret is still typed in plaintext in the exported workflow JSON, not pulled from a real credential store. Caught it in review, flagged it as the first go-live task — but it shipped that way, and it should've been caught before it was ever exported like that.
- I talk about "retry with backoff" for Claude calls in the architecture doc, but the actual code doesn't retry at all — a failed call is handled safely (nothing corrupts), it's just not retried. Worth being upfront about rather than letting someone assume the docs and the code agree.
- The Render free-tier backend cold-starts after ~15 min idle. I added a client-side keep-alive ping, but that only helps while someone actually has the app open — it's not a real fix, just a partial one, and I'm saying so rather than claiming it's solved.
- I only caught a real bug (two functions disagreeing on a cookie name, which silently broke real login) because I actually tried logging in and watched it fail. A code review that just checks "does this function work in isolation" would've missed it — the lesson is that a get/set/clear trio needs to be checked together, not one function at a time.
