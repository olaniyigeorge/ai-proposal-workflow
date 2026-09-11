# AI Proposal Workflow — One-Pager

## Header

**AI Proposal Workflow** — an internal tool that turns a sales team's discovery-call notes into a reviewed, branded, client-ready proposal PDF, with a human approving every step before anything reaches a client.

Live app: https://ai-proposal-workflow.vercel.app/ · API: https://ai-proposal-workflow.onrender.com/api/v1/docs

## Purpose & Success Criteria

**The problem:** after a discovery call, a salesperson has to turn rough notes (client needs, scope, pricing, timeline) into a polished proposal document — writing the narrative sections by hand, formatting it, and emailing it out. That's repetitive drafting work that takes time away from selling.

**What success looks like:** a salesperson submits (or a client self-submits) a short intake form, and within minutes has an AI-drafted proposal to review — not to rubber-stamp, but to edit, regenerate individual sections with feedback, and approve section-by-section or all at once. Nothing reaches a client without a human explicitly approving it and reviewing the actual email before it sends. The tool should save drafting time without ever taking the human out of the final decision.

## How It Works

1. **Intake** — a Google Form → Google Sheet → n8n automation normalizes the submission and posts it to the backend, which validates it, dedupes retries/resubmissions, and creates the proposal.
2. **Generation** — the salesperson triggers AI generation. Claude drafts the narrative sections (Introduction, Proposed Solution, Deliverables); pricing, timeline, and client facts are always inserted verbatim, never left to the model to paraphrase.
3. **Review** — the salesperson edits any section by hand, or asks Claude to regenerate one with a specific instruction ("make this more formal") — capped at 3 attempts per section so a stuck section doesn't become an unbounded cost.
4. **Approval** — sections can be approved individually or all at once. The proposal only reaches "Approved" once every section is approved — this is enforced by the backend, not just hidden in the UI.
5. **Document & delivery** — once approved, a branded PDF is generated exactly once and uploaded to storage. The salesperson reviews the composed client email (with a link to the PDF, never an attachment) before it sends — there's no auto-send. Once delivered, that proposal is locked: no further edits, no regenerated document. What the client received is what stays on record.
6. **Audit trail** — every meaningful action (created, edited, regenerated, approved, delivered, and every failure) is logged and exportable for compliance review.

## How to Use It

1. Go to the live app and sign in (a real Supabase account, or the "Dev Salesperson" option for a quick look without creating one).
2. Open a proposal from the list — a fresh one starts in **Draft** with template-only sections.
3. Click **Generate Proposal** to have Claude draft the two AI-written sections.
4. Edit any section directly, or click **Regenerate** and give it an instruction if you want the AI to try again.
5. Approve sections individually, or use **Approve Proposal** to approve everything remaining at once.
6. Once approved, click **Generate PDF Document**, then review and send the composed client email from the **Send PDF to Client** panel.
7. Check the **Activity Log** on the proposal page at any point to see the full history of what happened and when.

## Notes for a non-technical reviewer

- There is only one role in this system — every signed-in salesperson can act on any proposal (no manager/approver gate). Self-approval is expected, not a bug.
- The AI never invents pricing, dates, or client details — those are always the exact values from intake, inserted verbatim.
- If an intake looks too sparse to write a real proposal from (e.g. one-word answers), the tool now flags it and offers a one-click "email client for more detail" action before generating anything.
