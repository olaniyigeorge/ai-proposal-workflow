"""Enforces docs/reference/data-retention-policy.md's retention windows.

Not run automatically inside the API process — this is a scheduled job
(e.g. a Render Cron Job or any daily cron) invoked as:

    python -m scripts.enforce_retention          # deletes
    python -m scripts.enforce_retention --dry-run  # reports what would be deleted

Two things get deleted, independently:

1. `ActivityLogEntry` rows older than `ACTIVITY_LOG_RETENTION_MONTHS`
   (default 12), regardless of whether their parent Proposal still exists —
   the activity log's own retention window is shorter than a Proposal's, so
   it must be enforced on its own schedule, not just inherited via
   `ON DELETE CASCADE` when a Proposal is eventually deleted.
2. `Proposal` rows whose "last meaningful activity" is older than
   `PROPOSAL_RETENTION_MONTHS` (default 24). "Last meaningful activity" is
   the later of `Proposal.updated_at` and the newest `ActivityLogEntry` for
   that proposal — `updated_at` alone under-counts activity that only
   touched a `ProposalSection` row without the Proposal row itself changing
   (e.g. a section edit that doesn't also change proposal.status), so the
   activity log (which gets an entry for every state-relevant action
   regardless of which table it wrote to) is the more accurate signal.
   Deleting a Proposal cascades to its sections, intake submission, document
   artifacts, delivery records, and Claude call logs via `ON DELETE CASCADE`
   (see each model's FK definition) — this script only ever issues the one
   delete against `Proposal` itself.

No `retention_hold` flag exists yet for "documented business/legal reason to
keep this longer" (policy allows for one, schema doesn't yet) — if that's
ever needed, add the column and filter it out here before it's needed in
anger, not after something gets deleted that shouldn't have been.
"""

import argparse
import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.activity_log import ActivityLogEntry
from app.models.proposal import Proposal
from app.utils.logger import logger


def _cutoff(months: int) -> datetime:
    # Approximate months as 30-day blocks — retention windows measured in
    # months don't need calendar precision, and this avoids a dependency on
    # a calendar-math library for something this coarse-grained.
    return datetime.now(timezone.utc) - timedelta(days=30 * months)


async def _delete_expired_activity_logs(db: AsyncSession, dry_run: bool) -> int:
    cutoff = _cutoff(settings.ACTIVITY_LOG_RETENTION_MONTHS)
    if dry_run:
        count_stmt = select(func.count()).select_from(ActivityLogEntry).where(
            ActivityLogEntry.created_at < cutoff
        )
        return (await db.execute(count_stmt)).scalar_one()

    result = await db.execute(delete(ActivityLogEntry).where(ActivityLogEntry.created_at < cutoff))
    return result.rowcount or 0


async def _delete_expired_proposals(db: AsyncSession, dry_run: bool) -> int:
    cutoff = _cutoff(settings.PROPOSAL_RETENTION_MONTHS)

    # "Last meaningful activity" = max(Proposal.updated_at, latest activity
    # log entry for that proposal). A proposal with no activity log entries
    # yet (shouldn't happen post-Phase-8, but a pre-Phase-8 row could exist)
    # falls back to updated_at alone via COALESCE.
    latest_activity = (
        select(
            ActivityLogEntry.proposal_id,
            func.max(ActivityLogEntry.created_at).label("last_activity_at"),
        )
        .group_by(ActivityLogEntry.proposal_id)
        .subquery()
    )

    stale_proposals_stmt = (
        select(Proposal.id)
        .outerjoin(latest_activity, Proposal.id == latest_activity.c.proposal_id)
        .where(
            func.coalesce(latest_activity.c.last_activity_at, Proposal.updated_at) < cutoff
        )
    )
    stale_ids = [row[0] for row in (await db.execute(stale_proposals_stmt)).all()]

    if dry_run or not stale_ids:
        return len(stale_ids)

    result = await db.execute(delete(Proposal).where(Proposal.id.in_(stale_ids)))
    return result.rowcount or 0


async def run(dry_run: bool = False) -> None:
    async with AsyncSessionLocal() as db:
        activity_count = await _delete_expired_activity_logs(db, dry_run)
        proposal_count = await _delete_expired_proposals(db, dry_run)
        if not dry_run:
            await db.commit()

    verb = "Would delete" if dry_run else "Deleted"
    logger.info(
        "RETENTION_ENFORCEMENT %s %s expired activity log entries (>%sm) and %s expired proposals (>%sm)",
        verb,
        activity_count,
        settings.ACTIVITY_LOG_RETENTION_MONTHS,
        proposal_count,
        settings.PROPOSAL_RETENTION_MONTHS,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="Report what would be deleted, delete nothing."
    )
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
