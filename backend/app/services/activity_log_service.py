"""Phase 8: append-only audit trail of every state-relevant action across a
proposal's lifecycle (CLAUDE.md; architecture.md's `ActivityLogEntry`).

`record_activity` only calls `db.add()` — it never commits. Every call site
adds its entry to the same session as the state change it documents, then
lets that caller's existing `db.commit()` persist both atomically. This is
deliberately different from `claude_log_service.record_claude_call`, which
commits independently as pure observability that must survive regardless of
whether the section mutation itself succeeds.
"""

import csv
import io
import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_log import ActivityEventType, ActivityLogEntry


def record_activity(
    db: AsyncSession,
    *,
    proposal_id: uuid.UUID,
    event_type: ActivityEventType,
    description: str,
    actor: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> None:
    db.add(
        ActivityLogEntry(
            proposal_id=proposal_id,
            event_type=event_type,
            description=description,
            actor=actor,
            event_metadata=metadata or {},
        )
    )


async def list_activity_for_proposal(
    db: AsyncSession, proposal_id: uuid.UUID
) -> List[ActivityLogEntry]:
    stmt = (
        select(ActivityLogEntry)
        .where(ActivityLogEntry.proposal_id == proposal_id)
        .order_by(ActivityLogEntry.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_activity_for_export(
    db: AsyncSession, proposal_id: Optional[uuid.UUID] = None
) -> List[ActivityLogEntry]:
    """Chronological (oldest first) — an export/compliance read, unlike the
    dashboard list above which is newest-first for a timeline view.
    """
    stmt = select(ActivityLogEntry).order_by(ActivityLogEntry.created_at.asc())
    if proposal_id is not None:
        stmt = stmt.where(ActivityLogEntry.proposal_id == proposal_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


def build_activity_csv(entries: List[ActivityLogEntry]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "proposal_id",
            "event_type",
            "actor",
            "description",
            "metadata",
            "created_at",
        ]
    )
    for entry in entries:
        writer.writerow(
            [
                str(entry.id),
                str(entry.proposal_id),
                entry.event_type.value,
                entry.actor or "",
                entry.description,
                entry.event_metadata,
                entry.created_at.isoformat(),
            ]
        )
    return buffer.getvalue()
