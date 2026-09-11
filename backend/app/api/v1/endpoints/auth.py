import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentSalesperson, get_current_salesperson
from app.domain.exceptions import DisplayNameTakenError
from app.models.salesperson_account import SalespersonAccount
from app.schemas.common import SalespersonProfileResponse
from app.schemas.salesperson_account import SalespersonAccountResponse, UpdateDisplayNameRequest
from app.services.salesperson_account_service import (
    approve,
    get_account,
    list_all,
    list_pending,
    reject,
    update_display_name,
)

router = APIRouter()


@router.get("/me", response_model=SalespersonProfileResponse)
async def get_authenticated_salesperson(
    current_user: CurrentSalesperson = Depends(get_current_salesperson),
) -> SalespersonProfileResponse:
    """Trivial protected endpoint verifying salesperson authentication (Phase 0).

    Reaching this at all already proves the account is approved — the
    approval gate lives in get_current_salesperson itself (app/core/security.py),
    so any authenticated call that gets this far is a signed-in, approved
    salesperson, not just a valid Supabase session.
    """
    return SalespersonProfileResponse(
        user_id=current_user.user_id,
        email=current_user.email,
        role=current_user.role,
        display_name=current_user.display_name,
    )


@router.patch(
    "/me",
    response_model=SalespersonProfileResponse,
    summary="Set your own display name — used when self-claiming an unassigned proposal",
)
async def update_my_display_name(
    body: UpdateDisplayNameRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentSalesperson = Depends(get_current_salesperson),
) -> SalespersonProfileResponse:
    stmt = select(SalespersonAccount).where(SalespersonAccount.supabase_user_id == current.user_id)
    account = (await db.execute(stmt)).scalar_one_or_none()
    if account is None:
        # Only reachable via the dev token, which has no backing account row
        # (see app/core/security.py) — nothing to rename.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This session has no salesperson account to update.",
        )

    try:
        account = await update_display_name(db, account, body.display_name.strip())
    except DisplayNameTakenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return SalespersonProfileResponse(
        user_id=current.user_id,
        email=current.email,
        role=current.role,
        display_name=account.display_name,
    )


@router.get(
    "/accounts",
    response_model=List[SalespersonAccountResponse],
    summary="List every salesperson account — the Team tab's data source (any approved salesperson)",
)
async def list_accounts(
    db: AsyncSession = Depends(get_db),
    _: CurrentSalesperson = Depends(get_current_salesperson),
) -> List[SalespersonAccountResponse]:
    return await list_all(db)


@router.get(
    "/pending",
    response_model=List[SalespersonAccountResponse],
    summary="List real accounts awaiting approval (any approved salesperson)",
)
async def list_pending_accounts(
    db: AsyncSession = Depends(get_db),
    _: CurrentSalesperson = Depends(get_current_salesperson),
) -> List[SalespersonAccountResponse]:
    return await list_pending(db)


@router.post(
    "/pending/{account_id}/approve",
    response_model=SalespersonAccountResponse,
    summary="Approve a pending account — no separate approver role (decisions #21)",
)
async def approve_pending_account(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentSalesperson = Depends(get_current_salesperson),
) -> SalespersonAccountResponse:
    account = await get_account(db, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return await approve(db, account, current.email)


@router.post(
    "/pending/{account_id}/reject",
    response_model=SalespersonAccountResponse,
    summary="Reject a pending account",
)
async def reject_pending_account(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentSalesperson = Depends(get_current_salesperson),
) -> SalespersonAccountResponse:
    account = await get_account(db, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return await reject(db, account, current.email)
