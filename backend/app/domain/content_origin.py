"""Content-origin transition rules — shared by manual section edits
(services/proposal_service.py) and regeneration (services/regeneration_service.py).

docs/decisions.md #13b left one question explicitly open: what a section's
`content_origin` becomes after each action, given the enum carries both
`human_edited` and `human_edited_after_generation`. Resolved here:

- Manual edit: if the content being edited was already AI-touched
  (`ai_generated` or already `human_edited_after_generation`), the edit keeps
  that AI-touched marker (`human_edited_after_generation`) rather than
  collapsing to the plainer `human_edited` — worth keeping for audit ("a
  human customized AI output" vs. "a human wrote this from a blank
  template"). A manual edit on content that was never AI-generated
  (`template_default`, or `human_edited` with no AI history) is just
  `human_edited`.
- Regeneration: always produces fresh AI content that fully replaces
  whatever was there, human edits included, so the origin becomes
  `ai_generated` unconditionally. The per-section `regeneration_log` is what
  preserves the human's instruction trail across attempts — not the origin
  flag.
"""

from app.models.proposal import ContentOrigin

_AI_TOUCHED = frozenset({ContentOrigin.AI_GENERATED, ContentOrigin.HUMAN_EDITED_AFTER_GENERATION})


def content_origin_after_manual_edit(current: ContentOrigin) -> ContentOrigin:
    if current in _AI_TOUCHED:
        return ContentOrigin.HUMAN_EDITED_AFTER_GENERATION
    return ContentOrigin.HUMAN_EDITED


def content_origin_after_regeneration() -> ContentOrigin:
    return ContentOrigin.AI_GENERATED
