"""The only module allowed to import the `anthropic` SDK directly (per
CLAUDE.md: "adapters are the only place that import a third-party SDK").
"""

import anthropic

from app.core.config import settings


class ClaudeGenerationError(Exception):
    """Raised on any failure calling the Claude API — missing key, rate limit,
    timeout, refusal, etc. Callers (services/generation_service.py) treat this
    uniformly as "this section's generation failed", per CLAUDE.md's
    requirement that a failed external call never leaves a blank/half-written
    section.
    """


_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        if not settings.ANTHROPIC_API_KEY:
            raise ClaudeGenerationError(
                "ANTHROPIC_API_KEY is not configured — cannot call Claude"
            )
        _client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


async def generate_text(system_prompt: str, user_prompt: str) -> str:
    """One non-streaming Claude call. Returns the concatenated text content.

    Raises ClaudeGenerationError on any SDK error or an empty/blocked
    response — never returns a blank string.
    """
    client = _get_client()

    try:
        response = await client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=settings.CLAUDE_MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except anthropic.APIError as exc:
        raise ClaudeGenerationError(f"Claude API call failed: {exc}") from exc

    if response.stop_reason == "refusal":
        raise ClaudeGenerationError("Claude declined to generate this section")

    text = "".join(block.text for block in response.content if block.type == "text").strip()
    if not text:
        raise ClaudeGenerationError("Claude returned an empty response")

    return text
