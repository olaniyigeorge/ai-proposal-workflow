"""
The only module allowed to call the Resend API directly (per CLAUDE.md:
"adapters are the only place that import a third-party SDK"). Uses Resend's
plain REST API over `httpx` (already a dependency via the Supabase SDK)
rather than adding the `resend` PyPI package — one JSON POST is all this
needs, and it keeps the adapter's only external dependency the same HTTP
client already used elsewhere in this codebase.
"""

import httpx

from app.core.config import settings

_RESEND_API_URL = "https://api.resend.com/emails"


class EmailSendError(Exception):
    """Raised on any failure sending the delivery email — missing API key,
    a rejected recipient, a Resend API error, etc. Callers
    (services/delivery_service.py) treat this the same way every other
    external-call failure is treated: leave the Proposal's prior state
    intact and transition to DELIVERY_FAILED rather than silently
    swallowing it (CLAUDE.md: "not fired-and-forgotten").
    """


async def send_email(
    to_email: str, subject: str, text_body: str, html_body: str | None = None
) -> None:
    if not settings.RESEND_API_KEY:
        raise EmailSendError(
            "RESEND_API_KEY is not configured — cannot send delivery email"
        )

    payload: dict = {
        "from": f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_ADDRESS}>",
        "to": [to_email],
        "subject": subject,
        "text": text_body,
    }
    if html_body:
        payload["html"] = html_body

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                _RESEND_API_URL,
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise EmailSendError(f"Failed to reach Resend: {exc}") from exc

    if response.status_code >= 400:
        raise EmailSendError(
            f"Resend rejected the email (HTTP {response.status_code}): {response.text}"
        )
