"""Phase 8: the compliance-export side of the activity log (CLAUDE.md/
docs/decisions.md #19 — "exportable for compliance"), distinct from the
per-proposal dashboard view at GET /proposals/{id}/activity. Global — not
scoped under /proposals/{id} — since a compliance export typically needs
the whole trail, optionally filtered to one proposal.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentSalesperson, get_current_salesperson
from app.services.activity_log_service import build_activity_csv, list_activity_for_export

router = APIRouter()


@router.get(
    "/export",
    response_class=PlainTextResponse,
    summary="Export the activity log as CSV, optionally filtered to one proposal (salesperson authenticated)",
)
async def export_activity(
    proposal_id: Optional[uuid.UUID] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: CurrentSalesperson = Depends(get_current_salesperson),
) -> PlainTextResponse:
    entries = await list_activity_for_export(db, proposal_id)
    csv_content = build_activity_csv(entries)
    return PlainTextResponse(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=activity-log.csv"},
    )
