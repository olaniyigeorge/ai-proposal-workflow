# Design System & Document Redesign — Open Concerns Log

**Status:** open — planning doc, not yet implemented. Captures two things the latest development pass surfaced but didn't address: (1) a set of ownership/security concerns that have no doc home yet, and (2) the fact that the client-facing proposal PDF and email still read like an older, more generic style than the dashboard's current design system — they should be redesigned together to match.

This is not a substitute for `docs/decisions.md` or `docs/edge-cases.md`. Those are the decision log and the gotchas log. This file is a planning surface for a concrete redesign + the ownership follow-ups that claiming opened up.

---

## 1. Ownership enforcement (not built)

Claiming a proposal today sets the display label (`salesperson_name`) — it does **not** restrict who can act on it. The implemented behavior is: any approved salesperson can still edit, regenerate, approve, and deliver any proposal regardless of who claimed it. This is consistent with the current working default from `docs/decisions.md` #21 ("any authenticated salesperson may act on any proposal until told otherwise"), but claiming is supposed to be *toward* a point where ownership matters, so leaving enforcement off forever is the wrong default to sit on.

**What exists today:**
- `POST /proposals/{id}/claim` — writes `salesperson_name` from your `display_name`, only when the proposal is genuinely unassigned (`salesperson_name IS NULL`). Logs `PROPOSAL_CLAIMED`. No reassignment of already-owned proposals.
- `display_name` — set once via `PATCH /auth/me`, unique across the team. This is what gets written into a proposal on claim.

**What is missing:**
- No endpoint or rule prevents a salesperson from editing/regening/approving a proposal they didn't claim. If ownership is meant to be real, the service layer needs a guard (e.g. `is_owned_by_current_salesperson(proposal)` checked on state-changing actions, with a clear error for cross-owner attempts).
- No UI distinguishes "your proposals" from "everyone's proposals." The proposals list shows all proposals to every salesperson.
- No rule restricts who can approve whom's proposal. The Team tab's approve/reject gates account access, not proposal access — those are two different permissions even though both currently collapse to "any approved salesperson."

**Why it matters:**
- Claiming without enforcement is just labeling. If the business intent is "a salesperson owns what they claim and others don't touch it," that intent is unenforced. If the intent is "claiming is just a convenience label and anyone can work any proposal," that should be said plainly instead of half-built.
- The earlier design explicitly decided against ownership restriction as the default (decisions #21 follow-up, still open). That decision was made *before* claiming existed. Claiming changes the landscape — it's worth re-confirming whether the default still holds, or whether claiming is meant to open the door to per-proposal ownership.

**Open question (needs a decision before enforcing):**
- Does claiming a proposal give that salesperson exclusive rights to edit/approve/deliver it, or is ownership purely cosmetic?
- If exclusive: what's the exception list? (e.g. can an admin override? can the original creator still act? can a proposal be transferred?)
- If cosmetic: rename the feature so it isn't read as "ownership" — it's "assigning a name to an unassigned proposal," nothing more.

---

## 2. Approver authority is undefined for proposal actions

The Team tab lets an approved salesperson approve/reject *accounts*. It does not define who is allowed to approve *proposals*, and the current code doesn't restrict it — any approved account can approve any proposal. That's consistent with the single-role model, but it collides with the new team-approval surface: "approving someone" (giving them access) and "approving a proposal" (signing off on a client document) are different acts and currently look identical to a user ("I clicked Approve and something got approved").

**Open questions:**
- Is the same role allowed to approve both accounts and proposals, or should proposal approval require a different signal (e.g. only the proposal's owner, only senior account owners, or still anyone)?
- If a salesperson can approve a colleague's proposal, is that intentional or an oversight? Today it works, and nothing warns the approver that they're signing off on someone else's work.

---

## 3. Cross-account proposal reassignment is unaddressed

Claiming writes a name into an unassigned proposal once. There is no transfer path — no "give this proposal to someone else," no "unclaim," no bulk reassignment. If a salesperson leaves, gets rejected, or simply shouldn't own a proposal anymore, the current state of the system has no clean move.

**Edge case already documented:** `docs/edge-cases.md` (2026-09-11) covers the "closest match vs. manual self-claim" decision and notes ownership is not yet enforced. It doesn't cover transfer/reassignment because that wasn't built.

**Open questions:**
- Should a claimed proposal be transferable? By whom? (owner, admin, anyone?)
- Does a transfer log anywhere as an activity event? (it should, if claim does)
- Does a rejected salesperson's claimed proposals need reassignment or do they just become unassigned again?

---

## 4. Activity log doesn't capture account approvals or claims uniformly

The activity log (`ActivityLogEntry`) is scoped per-`proposal_id` and is the audit trail for proposal actions. Account approval (`approved_by`/`approved_at` on `salesperson_accounts`) is **not** in that log. Claiming writes a `PROPOSAL_CLAIMED` entry (per the latest pass), which is good, but account approval is still outside the exportable audit trail.

**Why it matters:**
- `docs/decisions.md` #19 requires the activity log to be exportable for compliance. Account approval is a state-relevant action (someone gains full system access) and is currently not in the exportable trail, only on the account row itself.
- If a compliance question ever asks "who approved access for the person who sent client X's proposal," the answer today requires reading two different systems (activity log for the proposal actions, account row for the approval) that aren't joined in one export.

**Open question:** should account approval be logged as a first-class activity event, or is the account row's `approved_by`/`approved_at` sufficient? The practical gap is the export — if it matters for compliance, it needs to be in the same trail.

---

## 5. Dev/staging/prod environment confusion around who can do what

The system has a dev token path (`dev-salesperson-token`) that works when `ENVIRONMENT=development`, and real Supabase Auth for everything else. The Team tab's approve/reject flow, the claim flow, and the ownership model all behave differently depending on which auth path hits them — and the dev token path can't represent a real team of named salespeople.

**Concretely:**
- You cannot test Team approval end-to-end with the dev token, because the dev token isn't a real account with a `display_name` or a `salesperson_accounts` row.
- You cannot test ownership enforcement with the dev token for the same reason.
- The dev token path skips the approval gate entirely (it's a dev bypass), so any feature that depends on "is this account approved" silently passes in dev and may fail in prod in ways dev never showed.

**Open question:** is the dev token path still needed once real login + team approval exist, or should local dev use a real Supabase auth flow (with a seeded approved account) so dev matches prod behavior for anything team/ownership-related?

---

## 6. Proposal document and client email are not yet redesigned to match the dashboard design system

### Current state

**Dashboard design system** (`web-app/app/globals.css`): ink `#1f2429`, muted `#5c646c`, surface base `#f5f6f5`, card `#ffffff`, border `#d8dbd9`, accent `#2563eb`, font stack `"Geist Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`. The dashboard uses rounded cards, subtle borders, the accent as the action color, status badges, and the full token vocabulary.

**Proposal document** (`backend/app/domain/document.py`): also uses the koyatalent.com-derived tokens (same ink/muted/accent/border/background/font), rendered to PDF via WeasyPrint. It's branded — it matches the site's colors — but the *layout* is a plain document structure (header rule, section headings with underlines, content blocks on a light background, footer) that predates and doesn't reference the dashboard's current design language. It's branded, but it's not visually continuous with what a salesperson sees while reviewing the proposal in the app.

**Client email** (`backend/app/domain/delivery.py`): branded HTML email using the same tokens, inline-styled, with a "View Your Proposal" CTA button. Also matches the site colors, but visually unrelated to the dashboard.

### What "redesign to match the dashboard" means here

The dashboard has a specific look — card surfaces, rounded corners, the accent used consistently for actions and highlights, muted ink for secondary text, a clear visual hierarchy. The proposal PDF and the email should feel like they came from the same product, not like three separately-branded outputs that happen to share a color palette.

**Concrete direction to decide:**
- Should the PDF's section rendering borrow the dashboard's card/panel visual language (rounded content blocks, subtle borders, the accent used the same way), or is a document supposed to look more formal and distinct from the dashboard?
- Should the email's CTA and layout be a direct visual sibling of the dashboard's buttons and cards, or does an email need its own (still-branded) treatment because email clients are a different medium?
- Do the dashboard, PDF, and email share one source of truth for the brand tokens (they already share the color values), or should there be one explicit design-system file everything imports from so a brand change only happens in one place?

### Where it lives today

- Dashboard tokens: `web-app/app/globals.css` (`:root` + Tailwind `@theme inline`)
- PDF: `backend/app/domain/document.py` (tokens duplicated as module constants + inline CSS)
- Email: `backend/app/domain/delivery.py` (tokens imported from `document.py` + inline styles)

The color values already match across all three. The gap is visual language and shared source of truth, not color mismatch.

---

## 7. Questions to settle before redesigning the document/email

1. **One brand system or three aligned ones?** If the dashboard's design language should drive the PDF and email, that needs a shared token source. If the PDF/email are supposed to look like documents/emails first and dashboard-second, the current per-medium duplication is fine and the only change is freshening the visual treatment.
2. **PDF as a webpage aesthetic or a document aesthetic?** WeasyPrint renders static HTML to PDF. The dashboard's rounded cards, hover states, and interactive feel don't translate directly to a static document. Deciding what "matches the dashboard" means for a non-interactive PDF is the real question — same colors and font, or same component vocabulary adapted for print?
3. **Email client constraints.** Email HTML is its own constrained medium (inline styles, unpredictable client rendering). Matching the dashboard too literally can break in real inboxes. The redesign should account for that rather than assume the dashboard's layout survives email clients.
4. **Should the client email preview in the dashboard look like the real email?** If the salesperson reviews the composed email draft before sending (per decisions #16), the preview should be honest about what the client will see — which means the preview and the real email share the same rendering, not two different templates.

---

## 8. Suggested next step

Before any code changes: decide (1) whether claiming is meant to be cosmetic or enforceable, and (2) whether the PDF/email should be redesigned to look like the dashboard or just freshened within their own mediums. Those two decisions shape everything else on this page. Once they're settled, the follow-ups become concrete tasks with clear scope rather than open concerns.
