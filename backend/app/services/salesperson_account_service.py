"""Gates real Supabase Auth sign-ins behind approval — see
app/models/salesperson_account.py for the full rationale.
"""

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exceptions import DisplayNameTakenError
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


async def list_all(db: AsyncSession) -> List[SalespersonAccount]:
    """Every account regardless of status — the "Team" tab's data source.
    Pending accounts get an inline approve/reject action in that same view;
    this is deliberately not restricted to "public info only" the way a
    multi-tenant app might, since every field here (email, display_name,
    status) is exactly what CLAUDE.md's single-role model already treats as
    visible to any authenticated salesperson (decisions #21) — there's no
    narrower audience to protect it from within this app.
    """
    stmt = select(SalespersonAccount).order_by(SalespersonAccount.created_at.asc())
    return list((await db.execute(stmt)).scalars().all())


async def update_display_name(
    db: AsyncSession, account: SalespersonAccount, display_name: str
) -> SalespersonAccount:
    """Self-service rename (PATCH /auth/me). Enforced unique at the DB level
    (migration e4f5a6b7c8d9) — this catches that constraint and raises a
    clear domain error instead of letting an IntegrityError surface as a
    500, since "someone else already has this name" is an expected, not
    exceptional, outcome here.
    """
    account.display_name = display_name
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise DisplayNameTakenError(display_name) from exc
    await db.refresh(account)
    return account


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
