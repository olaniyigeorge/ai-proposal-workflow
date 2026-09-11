"""
Salesperson feedback collection (week-3 feature).

POST /api/v1/feedback — auth required, adds a FeedbackEntry (category +
text + actor email from the JWT). GET /api/v1/feedback — read-backed list so
the team can spot patterns; in this phase there is no in-app 'mark as
addressed' state, that is a follow-up.
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client_feedback import FeedbackCategory, FeedbackEntry
from app.schemas.extended import FeedbackEntryRequest, FeedbackEntryResponse


async def submit_feedback(
    db: AsyncSession,
    request: FeedbackEntryRequest,
    actor_email: str,
) -> FeedbackEntry:
    """Create a feedback entry. Minimal validation is done by the schema;
    the service enforces non-empty text (schema already does) and attaches the
    actor's email from the authenticated request context."""
    entry = FeedbackEntry(
        category=request.category,
        text=request.text,
        actor_email=actor_email,
    )
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return entry


async def list_feedback(
    db: AsyncSession,
    *,
    category: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[FeedbackEntry]:
    """Read feedback entries, newest first, optionally filtered by category.

    `category` is the raw query-param string (BUG / FEATURE_REQUEST / GENERAL).
    Conversion to FeedbackCategory happens at the SQL level by comparing against
    the enum's `.value`, so invalid string values simply return zero rows rather
    than raising."""
    stmt = select(FeedbackEntry).order_by(FeedbackEntry.created_at.desc())
    if category is not None:
        stmt = stmt.where(FeedbackEntry.category == category)
    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())
