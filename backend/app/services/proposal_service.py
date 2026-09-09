import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.proposal import Proposal


async def list_proposals(
    db: AsyncSession, skip: int = 0, limit: int = 50
) -> List[Proposal]:
    stmt = (
        select(Proposal)
        .order_by(Proposal.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_proposal_by_id(
    db: AsyncSession, proposal_id: uuid.UUID
) -> Optional[Proposal]:
    stmt = (
        select(Proposal)
        .where(Proposal.id == proposal_id)
        .options(selectinload(Proposal.sections))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
