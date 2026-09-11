"""Gates real Supabase Auth sign-ins behind approval — see
app/models/salesperson_account.py for the full rationale.
"""

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.salesperson_account import SalespersonAccount, SalespersonAccountStatus


async def get_or_create_pending(
    db: AsyncSession, supabase_user_id: str, email: str
) -> SalespersonAccount:
    """Self-registering: the first authenticated request from a given
    Supabase user creates their PENDING row if one doesn't exist yet. Never
    creates a second row for the same user — the unique constraint on
    supabase_user_id is the backstop, this is the checked-first path.
    """
    stmt = select(SalespersonAccount).where(
        SalespersonAccount.supabase_user_id == supabase_user_id
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return existing

    account = SalespersonAccount(
        supabase_user_id=supabase_user_id,
        email=email,
        status=SalespersonAccountStatus.PENDING,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


async def list_pending(db: AsyncSession) -> List[SalespersonAccount]:
    stmt = (
        select(SalespersonAccount)
        .where(SalespersonAccount.status == SalespersonAccountStatus.PENDING)
        .order_by(SalespersonAccount.created_at.asc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_account(db: AsyncSession, account_id) -> Optional[SalespersonAccount]:
    stmt = select(SalespersonAccount).where(SalespersonAccount.id == account_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def approve(
    db: AsyncSession, account: SalespersonAccount, approved_by: str
) -> SalespersonAccount:
    account.status = SalespersonAccountStatus.APPROVED
    account.approved_by = approved_by
    account.approved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(account)
    return account


async def reject(
    db: AsyncSession, account: SalespersonAccount, approved_by: str
) -> SalespersonAccount:
    account.status = SalespersonAccountStatus.REJECTED
    account.approved_by = approved_by
    account.approved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(account)
    return account
