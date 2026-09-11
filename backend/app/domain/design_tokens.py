"""Single source of truth for this backend's brand tokens — colors, font
stack, and card-radius/border language shared by the PDF (domain/document.py)
and the client email (domain/delivery.py). Resolved 2026-09-11 (see
docs/design-system-redesign-and-ownership-concerns.md §6-§8): before this
module existed, both files duplicated the same koyatalent.com-derived values
independently; now both import from here, so a brand-token change happens in
exactly one place for the backend's two client-facing outputs.

CLAUDE.md deliberately keeps `backend/` and `web-app/` as two independently
deployable services with no shared code — so this is NOT the same file the
dashboard imports. The dashboard's parallel source of truth is
`web-app/app/globals.css`'s `:root` block. The values below are kept
numerically identical to that file by hand (same koyatalent.com source); if
you change one, change the other and note it in docs/edge-cases.md.
"""

BRAND_NAME = "Koya Talent"

# Flat color tokens — mirror web-app/app/globals.css :root exactly.
INK = "#1f2429"  # --foreground
MUTED = "#5c646c"  # --muted-text
ACCENT = "#2563eb"  # --primary-accent
SURFACE_BASE = "#f5f6f5"  # --surface-base
SURFACE_CARD = "#ffffff"  # --surface-card
BORDER = "#d8dbd9"  # --surface-border

# Retained for any caller still expecting the pre-2026-09-11 name — the
# dashboard doesn't have a literal "light section wash" token, so this alias
# just makes the meaning explicit at call sites during the transition to
# card-based section rendering.
BG_LIGHT = SURFACE_BASE

FONT_STACK = '"Geist Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'

# Card-language constants (docs/design-system-redesign-and-ownership-concerns.md
# §6: "card surfaces, rounded corners... a clear visual hierarchy" is what
# "matches the dashboard" means here, adapted for print/email). The dashboard
# itself uses Tailwind's rounded-lg/rounded-xl utilities (8px/12px) — these
# mirror that rather than introducing a third radius scale.
CARD_RADIUS = "8px"
CARD_RADIUS_LG = "12px"
