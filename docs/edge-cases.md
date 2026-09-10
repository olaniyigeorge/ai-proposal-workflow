# Edge Cases Log

Working log of edge cases discovered while building this project — the "gotchas" that aren't obvious from `CLAUDE.md`/`docs/architecture.md`/`docs/system-flow.md`/`docs/decisions.md` alone, but shaped an implementation choice. Newest first. When an edge case changes a documented decision, update the source doc (`decisions.md`, `intake-schema.md`, etc.) too — this file explains *why*, the source docs state *what's current*.

---

## 2026-09-10 — No error path when the Google Form drifts out of sync with the canonical intake schema

**The gap (business view):** The canonical schema lives in three places that have to agree — the Google Form question, the Sheet column header it produces, and n8n's Code node mapping that header to a canonical key for FastAPI (`docs/intake-schema.md`). Nobody but n8n's maintainer can keep those in sync, and nothing today tells them when they've drifted. Three distinct failure shapes, each with a different blast radius:

1. **A required field is renamed or removed on the form.** The Sheet column n8n's Code node looks for no longer exists, so it sends `null`/omits the key. FastAPI's Pydantic model correctly rejects this with a 422 (CLAUDE.md: "rejects rather than accepting nulls") — but today n8n's HTTP Request node has no configured error branch on a non-2xx response. A submission that fails validation this way currently just fails the n8n execution with no alert to anyone and no record that a real client request was lost — worse than a visible bug, because the client thinks they submitted a request and nobody on the sales side knows one exists to follow up on.
2. **A new field is added to the form.** No technical failure at all — n8n's Code node simply doesn't know the new column exists, so that answer is silently dropped before it ever reaches FastAPI. The submission looks completely successful; the new information the client typed just never arrives anywhere.
3. **A question's wording changes but the column header/canonical key doesn't** (e.g. "Estimated Pricing" gets reworded to ask something subtly different). Nothing in the pipeline can detect this — it's a semantic drift, not a structural one, and no schema check will ever catch it.

**The fix (planned, not yet implemented — n8n workflow lives outside this repo):**
- **Case 1 (structural drift on a required field) gets an automated safety net:** add an error branch after the intake HTTP Request node in n8n — an IF node (or the node's own "continue on fail" + a downstream check) on non-2xx — that routes the failed row + FastAPI's error body to a dead-letter destination (append to a second "Intake Failures" Sheet tab, or a Slack/email alert to whoever owns the n8n workflow — not the salesperson, since this is a technical config issue, not a business one). The goal is only "someone finds out a submission was lost," not auto-repair — a form/column rename needs a human to fix the n8n mapping either way.
- **Case 2 (new field silently dropped) and case 3 (semantic drift) have no technical fix** — they're undetectable by any check FastAPI or n8n can run, since the data that arrives is well-formed either way. The only mitigation is process: `docs/intake-schema.md`'s opening line already states the rule ("update this file first whenever a form question changes, then the n8n mapping, then let Pydantic be the backstop") — the actual gap today isn't a missing plan, it's that nothing enforces anyone follows that line when the form owner (who may not be the n8n maintainer) edits a question. Cheapest real-world guardrail: whoever owns the Google Form treats editing a question as a change request routed through the n8n maintainer, not a self-serve edit — worth a one-line note in whatever runbook/handoff doc governs form ownership, not code.

**Where it lives:** `docs/intake-schema.md` (schema of record), `docs/decisions.md` #5 (still 🟠 — the field list isn't locked, which is exactly what makes drift likely right now rather than a one-time historical risk). n8n workflow itself is not version-controlled in this repo, so the error-branch fix above needs to be applied directly in n8n's UI and re-exported/documented, not shipped as a code change here.

**Open follow-up:** once decisions #5 locks the canonical field list, revisit whether the Sheet's raw row (pre-Code-node) is worth logging on *every* intake regardless of success/failure — cheap insurance for reconstructing a lost submission from case 1, and the only way to notice case 2 after the fact if someone later asks "wait, didn't the form used to ask X?"

---

## 2026-09-10 — Brand colors/fonts pulled from koyatalent.com's live CSS, not invented

**The gap (business view):** The PDF and delivery email were originally styled with placeholder colors (an arbitrary indigo) since no brand asset existed in this repo. Shipping a "branded" client-facing document in the wrong colors is worse than shipping it visibly generic — a client who's seen koyatalent.com would notice the mismatch immediately, undermining exactly the professionalism the branding is meant to convey.

**The fix (implemented 2026-09-10):** fetched the live site's compiled CSS (`https://koyatalent.com/_astro/*.css`) and pulled real design tokens rather than guessing from the rendered page: ink `#1f2429`, muted text `#5c646c`, section background `#eef0ee`, border `#d8dbd9`, and the site's own CTA accent blue `#2563eb` (confirmed via its `.solcta__link{color:#2563eb}` class — literally their "solution CTA" link color, not a guess). Font stack matches their `--font` custom property exactly: `"Geist Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`. These constants live once in `backend/app/domain/document.py` and are re-exported into `backend/app/domain/delivery.py` so the PDF and the email that links to it read as one brand, not two.

**Where it lives:** `backend/app/domain/document.py` (`INK`, `MUTED`, `ACCENT`, `BG_LIGHT`, `BORDER`, `FONT_STACK`), `backend/app/domain/delivery.py` (HTML email, same tokens).

**Open follow-up:** WeasyPrint has no network access during PDF rendering, so "Geist Sans" silently falls back to system sans-serif if it isn't installed on whatever machine renders the PDF — never a render failure, but the font may not exactly match the site's until Geist is either installed system-wide or self-hosted and passed to WeasyPrint via `@font-face` with a local file path. No actual logo asset exists either (site uses a text wordmark, matching what this project already did) — if a real logo file ever gets added to the repo, embed it as a `data:` URI in the HTML template rather than a network-fetched image, for the same reason.

---

## 2026-09-10 — Delivery links must not expire before a client opens them

**The gap (business view):** The document link embedded in the delivery email has to work whenever the client eventually clicks it — could be minutes after sending, could be two weeks later if the email sits unread. A naive implementation (email the signed Storage URL directly) would use `get_signed_url`'s default 1-hour expiry (`adapters/storage_client.py`), so any client who doesn't open the email same-day gets a dead link with no way to recover — no client portal, no login, no way for them to ask the system for a fresh one (CLAUDE.md: "clients never authenticate into this system"). A client hitting a broken link on a proposal they were about to say yes to is exactly the kind of silent failure that costs a deal without anyone on the sales side ever finding out why.

**The fix (implemented 2026-09-10):** the email links to this backend's own `GET /public/proposals/{id}/document` — an unauthenticated redirect endpoint that generates a *fresh* signed URL server-side on every hit and 302s to it, rather than emailing the raw signed URL. The emailed link itself (pointing at our own domain, keyed only by the proposal's UUID) never expires; only the short-lived signed URL behind it does, and that's regenerated transparently every time. A client can click a link from a proposal sent months ago and it still works, as long as the underlying document still exists in Storage.

**Where it lives:** `backend/app/api/v1/endpoints/public.py`, `backend/app/services/delivery_service.py::build_document_link`.

**Open follow-up:** the redirect endpoint has no rate limiting or expiry of its own — anyone with a proposal's UUID can hit it indefinitely to regenerate a fresh signed URL for that PDF. UUIDs aren't guessable, and there's no other client-facing surface exposing them beyond the one email sent to the actual client, so the practical risk is low for this single-tenant internal tool — but worth revisiting if proposal IDs ever end up referenced anywhere more exposed (e.g. a future client-visible portal).

---

## 2026-09-10 — Nothing can ever mark a delivery "bounced" yet

**The gap (business view):** `DeliveryRecord.status` includes `bounced` alongside `sent`/`failed` (matching CLAUDE.md's "sent/bounced/failed" requirement), but nothing in the current send path can ever produce that status — `deliver_proposal` only ever writes `sent` (the SMTP call returned without raising) or `failed` (it raised). A bounce is fundamentally different: the SMTP call succeeds (the receiving mail server accepted the message), and the failure — invalid address, full mailbox, spam rejection — arrives later, asynchronously, usually via a bounce notification email or a provider webhook. Today a bounced proposal shows as `DELIVERED`/`sent` in the UI forever, giving the salesperson false confidence that the client received it when they never did — a client who never got a proposal they were expecting, and a salesperson who has no idea why they went quiet.

**The fix:** not implemented — this requires either parsing bounce notification emails or a provider-specific webhook (most transactional email providers offer one), neither of which exists yet since no real SMTP/provider account is configured in this environment (see the entry below). Flagged explicitly rather than left as a silent gap, since "sent" currently means "the SMTP handshake succeeded," not "the client received it."

**Where it lives:** `backend/app/models/delivery.py` (`DeliveryStatus.BOUNCED` — defined, never set), `backend/app/services/delivery_service.py`.

**Open follow-up:** once a real provider is chosen, wire its bounce webhook (or IMAP-based bounce parsing, if using raw SMTP) to a new endpoint that finds the matching `DeliveryRecord` (by provider message ID — worth adding a `provider_message_id` column when this is built) and updates its status to `bounced`, surfaced in the UI so the salesperson can follow up through another channel.

---

## 2026-09-10 — Resend configured and verified with a real send (was: no provider configured)

**The gap (business view):** Originally, no real email provider was configured — the SMTP adapter's failure path was verified but nothing about actual deliverability was. The user provisioned a Resend account and supplied `RESEND_API_KEY` + `EMAIL_FROM_ADDRESS` in `backend/.env`.

**The fix (implemented + verified live 2026-09-10):** switched the email adapter from generic SMTP to Resend's REST API (`backend/app/adapters/email_client.py`, plain `httpx` POST — no vendor SDK dependency). Confirmed end-to-end against the real account: a synthetic proposal driven to `DOCUMENT_READY`, delivered via `deliver_proposal()`, landed as `DeliveryStatus.SENT` with no error, proposal transitioned to `DELIVERED`, and the branded HTML email (with the "View Your Proposal" CTA button) was received. The earlier "SMTP not configured" failure-path verification still stands as the negative-path test — both are covered now.

**Where it lives:** `backend/app/adapters/email_client.py`, `backend/app/core/config.py` (`RESEND_API_KEY`, `EMAIL_FROM_ADDRESS`, `EMAIL_FROM_NAME`).

**Not actually an open follow-up:** the test send used `EMAIL_FROM_ADDRESS=notifications@notify.olaniyigeorge.com` (the verified domain on the dev Resend account) rather than a real `koyatalent.com` address — but on reflection this isn't a gap this project needs to solve. It's a per-deployment env var, not a code decision: whichever company runs this sets `EMAIL_FROM_ADDRESS`/`EMAIL_FROM_NAME` to their own verified sending domain (their sales inbox, `proposals@theirdomain.com`, whatever they already use), the same way they'd set their own Supabase project or Resend account. No code change is needed to support that, so it doesn't belong in this log as a gap — just a reminder that the *dev* value in `backend/.env` is a placeholder, same as the Supabase one below.

---

## 2026-09-10 — Supabase Storage has never been exercised against a real bucket in this environment

**The gap (business view):** `SUPABASE_URL`/`SUPABASE_KEY` in `backend/.env` are placeholder values (`example.supabase.co`), not a real project — distinct from `DATABASE_URL`, which is a genuinely working Postgres connection. Phase 6 (document generation) depends on Supabase Storage for the one thing it does: upload the branded PDF. Every live end-to-end test of `POST /generate-document` in this dev environment ends in `DOCUMENT_GENERATION_FAILED` at the upload step — not because the code is wrong, but because there is no real bucket to reach. If this placeholder is still in place when someone actually tries to generate a document against a real deployment, every proposal will get stuck failing at the same step with the same "can't reach Storage" error, and nobody will have seen it fail against a *real* bucket (wrong bucket name, wrong permissions, CORS, a bucket that doesn't exist yet) until then.

**The fix (verified, not solved):** the failure path itself is solid — confirmed live that a failed upload leaves the Proposal in `DOCUMENT_GENERATION_FAILED` with no `DocumentArtifact` row created (checked directly against the DB), and that retrying from that state correctly re-enters `DOCUMENT_GENERATING` rather than getting stuck. Rendering itself (WeasyPrint, no network dependency) was verified thoroughly via the fidelity test suite. What's unverified is everything Storage-specific: whether `DOCUMENT_STORAGE_BUCKET` ("proposal-documents") needs to be created manually in the Supabase dashboard first (Storage buckets aren't auto-created by an upload call), whether the configured key has Storage write permission, and whether `create_signed_url` behaves as the code assumes.

**Where it lives:** `backend/app/adapters/storage_client.py`, `backend/.env` (`SUPABASE_URL`/`SUPABASE_KEY`), `backend/app/core/config.py` (`DOCUMENT_STORAGE_BUCKET`).

**Open follow-up:** before Phase 6 is considered production-ready, someone with real Supabase project credentials needs to: (1) create the `proposal-documents` bucket (or set `DOCUMENT_STORAGE_BUCKET` to an existing one), (2) confirm the configured key can write to it, (3) run `generate-document` once against it end-to-end and confirm the signed URL from `GET /proposals/{id}/document` actually downloads the PDF.

---

## 2026-09-10 — Client's raw intake wording reached the client verbatim via the pinned Introduction

**The gap (business view):** Introduction was assembled at intake by wrapping `client_needs_summary` and `goals_and_objectives` verbatim in a fixed boilerplate frame (see the superseded 2026-09-09 entry below). Those two fields are free-text answers the client or salesperson typed into a form — if the wording was ungrammatical, a run-on sentence, or genuinely unclear, that exact text went straight into a client-facing proposal with no cleanup step, because nothing in the pipeline ever touched it after intake. A proposal opening with the client's own typo or awkward phrasing reflects worse on the sender than on the client who wrote it, and undermines exactly the "confident, professional" tone the rest of the document (and `HOUSE_TONE` in `generation.py`) is built around. Reported by the user after reviewing a real proposal in the running app.

**The fix (implemented 2026-09-10):** Introduction moved back into `GENERATED_SECTION_KEYS` — it's now a Claude call like Proposed Solution/Deliverables, with an explicit task instruction to paraphrase `client_needs_summary`/`goals_and_objectives` into clean, professional prose and correct grammar/phrasing, while being told just as explicitly not to add any need, goal, or commitment beyond what those two facts state — paraphrasing wording is in scope, inventing content is not. This reintroduces the small hallucination-surface-area cost the 2026-09-09 entry removed (one more Claude call, one more section that could technically drift), which is why that entry's "zero hallucination risk" framing doesn't fully hold anymore — traded deliberately for not shipping the client's own unedited wording back to them. Word target 60-100 words, matching the other generated sections' brevity.

**Where it lives:** `backend/app/domain/generation.py` (`GENERATED_SECTION_KEYS`, `WORD_TARGETS`, `_section_task_description` INTRODUCTION case, `pinned_prefix_for_section` INTRODUCTION case — the pre-generation placeholder only, never the final content), `backend/app/services/intake_service.py` (Introduction now seeded with that placeholder instead of assembled boilerplate), `web-app/lib/proposal-status.ts` (`GENERATED_SECTION_KEYS` — Introduction can now be regenerated with an instruction like any other generated section), tests in `backend/tests/test_generation.py` and `backend/tests/test_regeneration.py`.

**Open follow-up:** the same paraphrase-not-invent risk applies narratively to any future expansion of what gets generated from free-text fields — the mitigation here (an explicit "paraphrasing is in scope, inventing is not" instruction, tested by asserting the prompt contains it) is a prompt-level control, not a verified one; nothing currently checks that a *specific* generated Introduction didn't quietly add a claim. Revisit with a real consistency-check pass (architecture.md §4 point 8) if this turns out to happen in practice. Timeline/Pricing remain deliberately pinned verbatim and out of scope for this kind of "AI cleanup" — see the discussion when this was first proposed: normalizing a date/price via LLM risks the exact numeric drift this project's canonical-facts-layer rule exists to prevent, which is a different risk profile than paraphrasing free-text narrative.

---

## 2026-09-10 — A proposal from n8n intake had no way to leave DRAFT

**The gap (business view):** Every proposal created by the intake webhook lands in `DRAFT` with empty/template-only sections. Phase 2 built the `POST /generate` endpoint and the background Claude job, but no frontend control ever called it — the detail page rendered a fully read-only view with no "Generate" action anywhere. A real inbound request from n8n would sit in `DRAFT` forever from the salesperson's point of view: they'd open the proposal, see boilerplate/empty sections, and have no button to press. That's not a rough edge, it's a dead end in the one flow every proposal must pass through — every single proposal created via the real intake path would have been stuck. Caught by the user reviewing the running app rather than by any test, since the backend endpoint genuinely worked and every backend test that exercised it called it directly by URL.

**The fix (implemented 2026-09-10):** `GenerateProposalButton` — a client component shown in the Proposal Actions panel whenever `proposal.status` is `DRAFT` or `GENERATION_FAILED` (relabeled "Retry Generation" in the latter case). Fires `POST /generate`, then polls `GET /proposals/{id}` every 2.5s (60s timeout) until status leaves `GENERATING`, then refreshes the page — same polling pattern as `RegenerateSectionButton`.

**Where it lives:** `web-app/components/proposals/GenerateProposalButton.tsx`, wired into `web-app/app/proposals/[id]/page.tsx` via `canTriggerGeneration()` in `lib/proposal-status.ts`.

**Open follow-up:** none of Phase 2's "Detail view shows GENERATING status + polling" UI spec (`docs/ui-plan.md` §9) was actually built until now — worth double-checking the equivalent trigger exists for every other phase's primary action before considering that phase done, not just the backend endpoint. (Regeneration and section-editing didn't have this gap because their buttons were built alongside their endpoints in the same phase; full-proposal generation was the one action whose UI trigger got skipped.)

---

## 2026-09-10 — "Approve entire proposal" can rubber-stamp sections nobody actually read

**The gap (business view):** The bulk "Approve Proposal" action (system-flow.md §3: "a single action that approves all remaining sections at once") force-approves every still-pending section in the same call that finalizes the proposal. Combined with self-approval being frictionless by design (decisions #14) and there being no separate approver role (decisions #21), a salesperson can open a freshly-generated proposal and click "Approve Proposal" immediately — no section ever individually reviewed, no read confirmation, nothing stopping a factually-off or badly-toned AI section from reaching `APPROVED` (and eventually the client) with zero human eyes actually on it. The per-section approve flow exists specifically to make review deliberate section-by-section; the bulk action is a designed escape hatch from that deliberateness, and nothing currently signals to the salesperson that clicking it might be skipping review entirely versus just finishing up the last section or two.

**The fix (partial):** the UI is honest about what the bulk action will do rather than hiding it — `ApprovalPanel` shows "will approve N remaining" next to the button whenever `pendingSectionCount > 0`, so a salesperson approving 5 unread sections at least sees that number before clicking, rather than a button that looks identical whether 0 or 6 sections are still pending. This is a visibility nudge, not a guardrail — it doesn't require acknowledgment or block the action.

**Where it lives:** `web-app/components/proposals/ApprovalPanel.tsx`, `backend/app/services/approval_service.py::approve_entire_proposal`.

**Open follow-up:** if this turns out to be a real behavior in practice (not just a theoretical risk), the cheapest next step is requiring a confirmation dialog when `remainingPending > 0` specifically (mirroring `RegenerateSectionButton`'s human-edit confirmation), rather than restricting the bulk action itself — the system-flow.md diagram treats "approve all at once" as an intentional, documented feature, so removing it isn't the fix; making the skip-ahead cost more visible in the moment is.

---

## 2026-09-10 — Claude call logs are a second place client PII lives, with no retention policy of their own

**The gap (business view):** The new `claude_call_logs` table stores the full system/user prompt and Claude's response for every generation and regeneration call — which means client name, company, needs summary, pricing, and timeline (everything in the canonical facts block) now exists verbatim in a second table, not just on `Proposal`. Decisions #18 already flags that Proposal-level PII retention/access-control isn't finalized; this table makes that gap bigger before it's resolved, not smaller — it's an unbounded, ever-growing, unredacted log of exactly the sensitive fields the still-open policy question is about, and every regeneration attempt adds another full copy of that same data.

**The fix (accepted for now, not solved):** `ON DELETE CASCADE` on `proposal_id` means the log rows die when a Proposal does, so there's no leak *beyond* a proposal's own lifetime — but there's no independent retention window shorter than the proposal's, no redaction of PII within stored prompts/responses, and no access control narrower than "any authenticated salesperson can call `GET /proposals/{id}/claude-calls`" (consistent with the rest of the single-role model, per decisions #21, but worth naming explicitly for a table whose entire purpose is holding raw prompt/response text).

**Where it lives:** `backend/app/models/claude_call_log.py`, migration `b637bee3715a`.

**Open follow-up:** fold this into decisions #18 when that retention/access-control policy actually gets defined — don't solve it in isolation for just this table. In the meantime, this table exists purely for internal prompt-improvement observability (per the user's request), not as a system of record anything else reads, so the practical exposure is currently bounded to "whoever can already see the proposal in this single-tenant internal tool."
## 2026-09-10 — A flaky Claude call must not burn one of the salesperson's 3 regeneration attempts

**The gap (business view):** The 3-attempt cap (decisions #13) exists to force a directed, converging regeneration rather than aimless retries — but if a transient failure (rate limit, timeout, a momentary API outage) eats one of only 3 attempts, the salesperson is punished for infrastructure flakiness, not their own instruction quality. Losing a third of their budget to something entirely outside their control is exactly the kind of "the tool wasted my time" moment that kills trust in an AI feature, especially right when they're trying to get a proposal out the door.

**The fix (implemented 2026-09-10, Phase 4):** `ProposalSection.regeneration_count` — the value the 3-attempt cap actually checks — is only incremented in `regeneration_service.regenerate_section()` *after* `generate_text()` succeeds. A `ClaudeGenerationError` (rate limit, timeout, refusal, empty response) is caught, recorded in `regeneration_log` with `outcome: "failed"` and the error message (so the salesperson can still see it happened and roughly why), and the function returns without touching `regeneration_count`, `content`, `version`, or `approval_status` — the section is left exactly as it was, per CLAUDE.md's "a failed call must leave the prior state intact."

**Where it lives:** `backend/app/services/regeneration_service.py` (`regenerate_section`), test `test_regeneration_job_failure_does_not_burn_cap_attempt`.

**Open follow-up:** a salesperson who mistypes an instruction (e.g. a typo that produces a *technically successful* but useless Claude response) still burns a real attempt — there's no distinction between "Claude failed to respond" and "Claude responded but the salesperson didn't like it," nor should there be; only genuine call failures are free retries by design. The escape hatch for a cap-exhausted section is unchanged and unlimited: manual editing (Phase 3) has no attempt cap.

---

## 2026-09-10 — Concurrent writers can silently clobber each other's section edits or regenerations

**The gap (business view):** Nothing in Phase 3 or Phase 4 detects two people (or one person in two tabs) changing the same section at nearly the same time. If salesperson A edits a section by hand while salesperson B's regeneration job for that same section is still in flight, whichever write commits last simply overwrites the other with no warning — the loser's work vanishes without any error, undo, or record that a conflict even happened. This is exactly the "optimistic concurrency" risk architecture.md §6 already named as a general requirement ("use a version/updated-at check... surface a conflict rather than losing data"), now concrete: Phase 4 introduced a second, *asynchronous* writer (the regeneration background job) racing against Phase 3's synchronous edit endpoint on the same row, which is a materially higher-probability collision than two synchronous edits ever were, since the regeneration job can be in flight for several seconds while its target section stays fully editable in the UI the whole time.

**The fix:** not implemented — both `update_section_content()` and `regenerate_section()` read-modify-write a `ProposalSection` with no version check, so this remains a real, live gap, not a theoretical one. Flagged here explicitly rather than silently deferred, per architecture.md §6.

**Where it lives:** `backend/app/services/proposal_service.py::update_section_content`, `backend/app/services/regeneration_service.py::regenerate_section` — both would need to compare an expected `version` (or `updated_at`) against the current row inside the same transaction and raise a conflict (409) instead of writing, if a caller's read is stale.

**Open follow-up:** given the single-tenant, single-role, no-ownership-restriction design (decisions #21), the realistic collision is "two tabs of the same salesperson" or "salesperson edits while their own earlier regeneration for that section is still running" more often than two different salespeople — worth confirming whether that narrower risk still justifies the extra complexity of version-checked writes before building it. Note `RegenerateSectionButton`'s `isRegenerating` state only disables *its own* trigger while a job is in flight — it does not currently disable the sibling `SectionEditor`'s "Edit Content" button for the same section (the two components don't share state), so a salesperson can still start a manual edit on a section while that section's own regeneration job is still running. A shared "this section is busy" flag between the two components would close that specific window cheaply, without needing full version-checked writes.

---

## 2026-09-10 — Truncated sibling summaries could still let a regenerated section drift narratively

**The gap (business view):** Per architecture.md §4 point 3, a regeneration call includes short summaries of every other section (not full text) so the new text doesn't contradict the rest of the proposal. Those summaries are a blunt character-count truncation (`content[:160]`) of each sibling section's actual content, not a real summary — if a sibling's most relevant detail happens to fall after character 160, the regenerated section never sees it and could still narratively drift (e.g. Deliverables lists something Proposed Solution's cut-off tail actually promised). The canonical facts layer (client name, dates, pricing) is unaffected — those are passed verbatim regardless — so this is a narrative-consistency risk only, not a numeric/factual one.

**The fix (accepted, not eliminated):** architecture.md §4 point 8 explicitly marks a real consistency pass (a secondary check that flags contradictions) as optional/deferred, and this project has only two sections that are ever AI-generated (Proposed Solution, Deliverables — see `docs/edge-cases.md` "Generated sections run long"), which narrows the realistic collision surface considerably versus the general N-section case the architecture doc was written for. Truncation was chosen over a real summarization call to avoid doubling Claude spend (one summarization call per sibling, per regeneration) for a low-probability, low-severity failure mode.

**Where it lives:** `backend/app/domain/generation.py::_sibling_summary_block`.

**Open follow-up:** if this turns out to cause visible contradictions in practice, the cheapest fix is raising the truncation length before reaching for a real summarization call or a consistency-check pass — no evidence yet that 160 characters is actually too short for either of the two generated sections' summaries.

---

## 2026-09-09 — Duplicate intake beyond webhook retries

**The gap:** The original idempotency key (`hash(timestamp + email_address)`, `docs/decisions.md` #4) only protects against *n8n retrying a failed delivery of the same Sheet row* — the `Timestamp` column is identical on a retry because it's the same row. It does **not** protect against a human genuinely submitting the same request twice (e.g. a salesperson re-filling the Google Form for the same client because they weren't sure the first one went through, or the client verbally re-requesting the same thing). That second submission gets a *new* `Timestamp` from Google Forms, so the old key treats it as a brand-new proposal — duplicate `Proposal` rows for what is substantively one request.

**The fix:** Idempotency key is now `hash(company_name + normalize(project_scope) + respondent_email)` — no `timestamp` in the key at all. Rationale: a true duplicate (whether a retry or a re-submission) shares these three fields; a genuinely different request from the same person on the same day will describe a different `project_scope`. `normalize()` = lowercase, trim, collapse internal whitespace, strip trailing punctuation, so a re-typed submission with cosmetic differences (extra space, re-cased text, trailing period) still dedupes.

**Where it lives:**
- Computed in FastAPI: `compute_intake_key()` / `normalize_text()` in `backend/app/services/intake_service.py`.
- n8n's Code node does **not** compute the hash — it only does Sheet-column → canonical-key translation (per the existing n8n/FastAPI boundary in `CLAUDE.md`). Keeping the hash algorithm in one place (Python) avoids a second implementation drifting from the first.
- Tests: `test_intake_idempotency_survives_resubmission_with_new_timestamp`, `test_intake_idempotency_ignores_cosmetic_differences` in `backend/tests/test_intake.py`.
- Doc updates: `docs/decisions.md` #4 (marked revised), `docs/intake-schema.md` "Idempotency key" section.

**Open follow-up:** `project_scope` is free text from a Google Form long-answer field — two submissions describing the *same* project in genuinely different wording (not just whitespace/casing) will still fork into two proposals. Current normalization only catches cosmetic differences, not semantic ones. Revisit if this turns out to happen in practice (e.g. fuzzy-match or a Claude-based dedupe check before create) — no evidence yet that it's a real problem, so not building it preemptively.

---

## 2026-09-09 — Generated sections run long; client skim reading suffers

**The gap (business view):** A proposal that reads like a white paper gets skimmed and set aside. Long AI sections look thorough but bury the client's actual problem and your answer in padding. The salesperson then spends edit time cutting, not improving — negating the time save Phase 2 was supposed to deliver. Original prompts had no length target at all (asked for "2-3 paragraphs" per section with no word ceiling), and `CLAUDE_MAX_TOKENS` was set to 2048 — enough headroom for Claude to write several times longer than the reference template ever does.

**The fix (implemented 2026-09-09):** `docs/reference/proposal-template.md` (the actual PRD reference, now on disk) shows every section as one to two short sentences of boilerplate around a pinned fact — there was never a "few paragraphs per section" target to begin with. Reset to match: `WORD_TARGETS` in `backend/app/domain/generation.py` sets 120-200 words for Proposed Solution's generated narrative and 60-120 words for Deliverables, stated explicitly in the prompt ("going over it is treated as a failure to follow instructions, not thoroughness"), and `CLAUDE_MAX_TOKENS` dropped from 2048 to 500. Also found while re-reading the template: **Introduction has no generated placeholder in it at all** — it's fixed boilerplate wrapping `client_needs_summary` and `goals_and_objectives` verbatim — so it's been moved out of the Claude-call path entirely and assembled at intake like Timeline/Pricing. Net effect: one fewer Claude call per proposal (lower cost, faster generation, zero hallucination risk on that section) plus tighter output on the two sections that do need a model call.

**Where it lives:** `backend/app/domain/generation.py` (`WORD_TARGETS`), `backend/app/core/config.py` (`CLAUDE_MAX_TOKENS = 500`), tests in `backend/tests/test_generation.py`. Word-count badge in the UI (Phase 3/4 SectionEditor) is still the open UI-side follow-up below.

**Superseded in part (2026-09-10):** Introduction being pinned-only turned out to trade the hallucination risk this entry solved for a different, equally real problem — a client's ungrammatical/unclear raw form answers reaching the client verbatim, unedited. Introduction is generated again as of 2026-09-10, now with a length target and an explicit paraphrase-don't-invent instruction — see "Client's raw intake wording reached the client verbatim via the pinned Introduction" below. The word-target/`CLAUDE_MAX_TOKENS` fix in this entry still stands for all three generated sections.

**Open follow-up:** the visible word-count badge next to each section (so the salesperson sees at a glance which sections still need trimming after an edit) is still Phase 3/4 UI work, not yet built. If Claude consistently exceeds the new targets in practice, tune the prompt per section — treat as prompt-iteration work, not a code bug. Cap regeneration at 3 (already decided #13) so a "shorten this" instruction can't infinite-loop.

---

## 2026-09-09 — Email sent without a human reviewing the draft

**The gap (business view):** If "send" fires automatically from DOCUMENT_READY or APPROVED, a wrong recipient, a stale link, a generic email body, or a pricing error in the body goes out before anyone sees it. For a proposal that's a sales document, a bad send is a lost opportunity or a damaged first impression — higher cost than a delayed send.

**The fix (proposed):** Email draft is composed (storage link embedded) but not sent until the salesperson reviews and confirms it in the UI. The send button is disabled until the draft is reviewed. Delivery status (sent/bounced/failed) tracked in DeliveryRecord as already planned (decisions #17). This is a Phase 7 change: the "review email draft" step sits between DOCUMENT_READY and DELIVERING. See `decisions.md` #16 follow-up.

**Where it lives:** Phase 7 delivery service + UI (email draft review component). Storage: Supabase Storage default; link embedded in email body, not attachment.

**Open follow-up:** confirm whether the email body is templated (house tone, project-specific merge fields) or fully free-form per send. Templated + editable is the sweet spot — a starting draft the salesperson tweaks, not a blank box and not a locked text.

---

## 2026-09-09 — Human edits lost when a section is regenerated without warning

**The gap (business view):** A salesperson spends 10 minutes tightening a section's wording, then hits regenerate (or a background job does), and the edit vanishes — the section goes back to the AI version. The time spent editing is wasted and the salesperson loses trust in the edit feature. This is the highest-friction failure mode in the review flow because it punishes the exact action (editing) that's supposed to be the value add.

**The fix (implemented 2026-09-10, Phase 4):** `RegenerateSectionButton` (`web-app/components/proposals/RegenerateSectionButton.tsx`) shows a `window.confirm` warning before submitting a regenerate call against any section whose `content_origin` is `human_edited` or `human_edited_after_generation` — "this section has manual edits — regenerating will replace them, this cannot be undone." The 3-attempt cap (decisions #13) limits how often this can happen per section. Sibling sections are never touched by a single-section regenerate (CLAUDE.md constraint; covered by `test_regeneration_job_success_updates_only_targeted_section`).

**Where it lives:** `web-app/components/proposals/RegenerateSectionButton.tsx` (confirm dialog), `backend/app/domain/content_origin.py` (the origin-flip rules this confirmation is warning about).

**Open follow-up — this guard is UI-only, not backend-enforced.** The FastAPI endpoint (`POST /proposals/{id}/sections/{key}/regenerate`) does not itself require any confirmation or check prior content_origin before overwriting — "hiding a button isn't access control" (CLAUDE.md) technically doesn't apply here since this isn't a security boundary, but it does mean a second frontend, a script, or a direct API call bypasses the warning entirely and silently destroys the human edit. If a second client ever calls this API, revisit whether the backend should require an explicit `confirm_overwrite: true` flag when `content_origin` is already human-touched, rather than relying on any one frontend to ask.

---

## 2026-09-09 — Salesperson attribution breaks when the client fills the form

**The gap (business view):** The Google Form can be filled by the salesperson OR the client. `salesperson_name` is free text — if the client types their own name, a different spelling, or leaves it blank, string-matching it to a `User` account misassigns the proposal or leaves it unassigned. The wrong salesperson (or nobody) ends up reviewing a proposal that's sitting in the queue, delaying revenue. Worse, requiring the field at all forces a discovery call to happen before intake — the exact friction step self-serve clients don't need.

**The fix (implemented 2026-09-09):** `salesperson_name` is now optional end-to-end — `IntakePayload.salesperson_name: Optional[str]`, the `proposals.salesperson_name` DB column is nullable (migration `209e98a651b7`), and a blank/whitespace Sheet cell is normalized to `NULL` ("unassigned") by a Pydantic validator rather than stored as a literal empty string. This is a deliberate tradeoff: it removes attribution-at-intake in exchange for removing the discovery-call requirement entirely — a client with an existing form can self-serve straight into the pipeline, shortening the sales cycle. The alternative (exact-match against `User.name`) was rejected — it still misassigns on any spelling difference and does nothing for the "client filled it, no salesperson exists yet" case, which is now the common path this unblocks. Assignment happens after intake via a manual claim/assign step in the review queue — not attempted automatically. See `decisions.md` #20 (now ✅).

**Where it lives:** `backend/app/schemas/intake.py` (`Optional[str]` + `blank_salesperson_name_is_unassigned` validator), `backend/app/models/proposal.py` (nullable column), `backend/migrations/versions/209e98a651b7_make_salesperson_name_nullable.py`, `backend/app/schemas/proposal.py` (response models), tests in `backend/tests/test_intake.py`.

**Open follow-up:** the claim/assign UI + service itself doesn't exist yet — needed before/alongside Phase 5 approval (approval needs an actor). Auto-assignment criteria (round-robin, territory, current load) are explicitly deferred — manual claim is the only mechanism for now, and that's a real ongoing labor cost worth revisiting once proposal volume makes manual triage slow. Confirm whether Supabase Auth users are the actor model before adding a separate `User` table.

---

## 2026-09-09 — Regeneration loses the salesperson's instruction context across attempts

**The gap (business view):** A salesperson regenerates a section 2–3 times to get it right, each time typing a fresh instruction from memory ("more formal", "shorter", "focus on ROI"). There's no record of what they asked on previous attempts, so they repeat themselves, refine by guesswork, or give up after the cap. The 3-attempt cap (#13) becomes frustrating rather than a useful constraint — and the salesperson can't tell whether the last regeneration actually addressed what they meant. For a creative-writing task that's meant to converge, losing the instruction trail per section wastes attempts and degrades the output.

**The fix (implemented 2026-09-10, Phase 4):** `ProposalSection.regeneration_log` (JSON column, migration `8277db7b3a4f`) — an append-only list, one entry per regeneration attempt: `{instruction, attempted_at, outcome, resulting_version | error}`. `RegenerateSectionButton` renders the full history above the instruction textarea whenever a section already has attempts, each one tagged succeeded/failed. The cap (3) counts against the section's `regeneration_count`, not the log length, so a failed attempt still shows in the trail (see the "failed regeneration must not burn a cap attempt" entry below) without spending one of the 3 real tries.

**Where it lives:** `backend/app/models/proposal.py` (`regeneration_log` column), `backend/app/services/regeneration_service.py` (appends an entry on both success and failure), `backend/app/schemas/proposal.py` (`RegenerationLogEntry`), `web-app/components/proposals/RegenerateSectionButton.tsx` (renders it). Tests: `test_regeneration_job_success_updates_only_targeted_section`, `test_regeneration_job_failure_does_not_burn_cap_attempt`.

**Resolved follow-up (decisions #13b):** append-only, no edit/delete — matches "cleaner audit" over "salesperson's editable notes," since the log records what was actually *sent* to Claude, not a scratchpad. If a salesperson wants to revise their intent, that's simply their next attempt's instruction.

---

## YYYY-MM-DD — Short title

```
## YYYY-MM-DD — Short title

**The gap:** What broke / what wasn't handled, concretely (an input, a sequence of actions).

**The fix:** What was changed and why this approach over alternatives.

**Where it lives:** Code, tests, and doc locations touched.

**Open follow-up:** Anything still not handled, so it doesn't get silently forgotten.
```
