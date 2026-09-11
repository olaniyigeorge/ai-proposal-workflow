# Model Cost Analysis — Claude Model Choice at 2,000 Proposals/Month

## Pricing (per Anthropic's model comparison table)

| Model | Input ($/MTok) | Output ($/MTok) | Positioning |
|---|---|---|---|
| Claude Fable 5.1 | $10 | $50 | Demanding reasoning / long-horizon agentic work |
| Claude Opus 5 | $5 | $25 | Complex agentic coding / enterprise work |
| Claude Sonnet 5 (current default, `CLAUDE_MODEL`) | $2 | $10 | Best combination of speed and intelligence |
| Claude Haiku 4.5 | $1 | $5 | Fastest, near-frontier intelligence |

## What this app actually calls Claude for

Per `backend/app/domain/generation.py`: 3 of 6 template sections are generated (Introduction, Proposed Solution, Deliverables), each a **single, short, non-agentic completion** — no tool use, no multi-turn reasoning, no chained calls. `CLAUDE_MAX_TOKENS = 500` caps every call; actual targets are 60–200 words (~80–270 tokens) per section. This is about as far from "demanding reasoning / long-horizon agentic work" as a Claude use case gets.

## Token estimate per call (from the actual prompt-building code)

- **System prompt** (`build_system_prompt()`): house tone + rules, ~150 words ≈ **200 tokens**.
- **Full-generation user prompt**: canonical facts block (client/company/dates/scope/goals/services/pricing, varies with real answers) + task description ≈ **300 tokens** average.
- **Regeneration user prompt**: same facts block + sibling-section summaries (`_sibling_summary_block`, ~3 sections × 160 chars) + instruction ≈ **500 tokens** average (larger than full-gen due to the sibling context).
- **Output**: word targets of 60–200 words ⇒ **~80–270 tokens**, averaging **~180 tokens** per call across the three generated sections.

## Monthly volume assumption (2,000 proposals/month)

- **Full generation**: every proposal generates 3 sections once ⇒ **6,000 calls/month**.
- **Regeneration**: assumed average **1.5 regeneration calls per proposal** (a rough estimate — no real usage data exists yet; some proposals need 0, some use the full 3-attempt cap per section). ⇒ **3,000 calls/month**.
- **Total: ~9,000 Claude calls/month.**
- Blended input tokens/call: (6,000×500 + 3,000×700) / 9,000 ≈ **567 tokens** (full-gen input ~500, regen input ~700 including sibling summaries).
- Blended output tokens/call: **~180 tokens**.
- **Monthly input tokens ≈ 5.1M. Monthly output tokens ≈ 1.6M.**

*(These are estimates from reading the actual prompt-assembly code, not measured production data — re-run this math once `ClaudeCallLog.input_tokens`/`output_tokens` has a real month of data, since that table already records exactly this per call.)*

## Monthly cost by model

| Model | Input cost (5.1M × rate) | Output cost (1.6M × rate) | **Total/month** |
|---|---|---|---|
| Fable 5.1 | $51.00 | $81.00 | **≈ $132** |
| Opus 5 | $25.50 | $40.50 | **≈ $66** |
| **Sonnet 5 (current)** | $10.20 | $16.20 | **≈ $26** |
| Haiku 4.5 | $5.10 | $8.10 | **≈ $13** |

## The actual finding: at this volume, model choice is not a meaningful cost lever

The entire spread across all four models — from the cheapest (Haiku) to the most expensive (Fable) — is **about $120/month** at 2,000 proposals. Even the full jump from Haiku to Fable 5.1 costs less than one salesperson's time for a few minutes each month. This changes the framing of "which model should we use": it is **not** a cost decision at this scale, it's a **quality** decision — a single bad/hallucinated section reaching a client costs far more in trust and rework than the entire monthly model bill, regardless of which of these four models is chosen.

## Recommendation

**Keep Claude Sonnet 5.** It already isn't a cost risk, the section content itself hasn't shown quality problems in testing (see `docs/edge-cases.md`'s generation entries), and it's explicitly positioned as "the best combination of speed and intelligence" — a good fit for short, non-agentic, client-facing copy where you want more than a bare-minimum-capability model but don't need Opus/Fable-level reasoning for a single-paragraph completion.

**Do not upgrade to Opus 5 or Fable 5.1** — those are positioned for "complex agentic coding" and "long-horizon agentic work" respectively; this app has neither (no tool use, no multi-step agent loops, single completions). Paying 2.5–5× more for that is buying capability this task can't use.

**Worth a real (not guessed) comparison against Haiku 4.5** — the $13/month saved is trivial, but if a side-by-side test on real proposals shows Haiku holds up on tone/quality for this specific short-form task, it's a legitimate downgrade with no real business cost either way. If quality noticeably drops (vaguer narrative, weaker paraphrasing of messy client answers — see the Introduction-section reasoning in `docs/edge-cases.md`), stay on Sonnet; the money difference doesn't justify the risk.

## What would actually change this analysis

- **Real regeneration rate**: if actual usage runs closer to 3 regenerations/section/proposal (the hard cap) instead of the 1.5-call average assumed here, monthly volume roughly doubles — cost still stays in the tens-to-low-hundreds of dollars range for any of these four models, so the conclusion doesn't change.
- **Scaling 10×** (20,000 proposals/month): the same math scales linearly to Sonnet ≈ $260/month, Opus ≈ $660/month, Fable ≈ $1,320/month — at that volume the Opus/Fable premium ($400–1,060/month) becomes a real line item worth re-justifying against measured quality gains, not assumed ones.
