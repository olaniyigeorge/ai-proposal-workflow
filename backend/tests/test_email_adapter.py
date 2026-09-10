"""Tests for the Resend email adapter (Phase 7). The success path against
the real Resend API isn't exercised here — no live credentials in this test
env — but the config guard and payload shape are.
"""

import pytest

from app.adapters.email_client import EmailSendError, send_email
from app.core.config import settings


@pytest.mark.asyncio
async def test_send_email_without_api_key_raises_clear_error(monkeypatch) -> None:
    monkeypatch.setattr(settings, "RESEND_API_KEY", "")
    with pytest.raises(EmailSendError, match="RESEND_API_KEY"):
        await send_email("client@example.com", "Subject", "Body text")
