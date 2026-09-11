# AI Proposal Workflow — What It Is & How To Use It

## Header

**AI Proposal Workflow.** An internal tool that takes what comes in from a discovery call (client name, what they need, scope, price, timeline) and turns it into a real, branded proposal document — drafted by AI, reviewed and approved by you, then emailed to the client. You're always the last check before anything goes out.

- App: https://ai-proposal-workflow.vercel.app/
- Backend docs (if you ever need to check something's actually running): https://ai-proposal-workflow.onrender.com/api/v1/docs

## Why this exists

Writing a proposal by hand after every call is repetitive — same structure, same sections, different client. That's time you could spend actually selling. This tool takes the notes from the call and gets you a first draft in minutes instead of an hour, without taking you out of the loop. Nothing reaches a client unless you say it's ready.

**What "working" looks like:** you fill out the intake form (or a client fills it themselves), a proposal shows up on your dashboard, you generate it, tweak whatever needs tweaking, approve it, and send it — all without ever having to write a section from scratch.

## How it actually works, step by step

1. **Something comes in.** A Google Form submission (from you or the client) flows through a Sheet and lands in the system as a new proposal in "Draft."
2. **You hit Generate.** The AI writes the sections that actually need writing (the intro, the recommended approach, the deliverables list). Pricing, dates, and the client's name are never left to the AI to guess or rephrase — those come straight from what was entered and stay exact.
3. **You review.** Read each section. If something's off, either edit it yourself or hit Regenerate and tell it what to change ("make this more formal," "shorten this"). You get 3 tries per section before you have to just edit it by hand — this stops anyone (including future-you) from endlessly re-rolling instead of just fixing it.
4. **You approve.** Section by section, or all at once if you're happy with everything. The proposal can't move forward until every section is approved — the system won't let you skip that, even accidentally.
5. **PDF gets made.** Once approved, a branded PDF is generated — exactly once, so what gets approved is what gets sent, not some later draft.
6. **You review the email, then you send it.** The email has a link to the PDF (not an attachment) and nothing goes out until you personally click send. No auto-send, ever.
7. **Everything's logged.** Every action — created, edited, regenerated, approved, sent, or failed — is on an activity log per proposal, so if anyone ever asks "what happened to this one," the answer's right there.

## How to actually use it

1. Open the app and sign in.
2. Find your proposal in the list (or open a new one that just came in from intake).
3. Click **Generate Proposal**.
4. Read through the sections. Edit directly, or click **Regenerate** with an instruction if you want the AI to try again.
5. Approve each section (or click **Approve Proposal** to approve everything left at once).
6. Click **Generate PDF Document**.
7. Review the email draft, then click **Send**.
8. Check the **Activity Log** on the proposal page any time you want the full history.

## A few things worth knowing

- **There's no "manager" role.** Anyone signed in can approve their own proposal — that's expected, not a bug. If you built it, you can approve it and send it.
- **The AI never touches numbers or dates.** Pricing, timelines, and client details are always exactly what was entered — the AI only writes the surrounding narrative, never the facts.
- **If a submission looks too thin to write a real proposal from** (one-word answers, obviously incomplete), the system flags it and gives you a one-click way to email the client asking for more detail — instead of quietly generating something generic.
- **Once a proposal is sent, it's locked.** No more silent edits to something a client's already seen. If it needs to change after delivery, that's a deliberate new step, not an accident waiting to happen.
