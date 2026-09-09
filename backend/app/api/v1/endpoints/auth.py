from fastapi import APIRouter, Depends
from app.core.security import CurrentSalesperson, get_current_salesperson
from app.schemas.common import SalespersonProfileResponse

router = APIRouter()


@router.get("/me", response_model=SalespersonProfileResponse)
async def get_authenticated_salesperson(
    current_user: CurrentSalesperson = Depends(get_current_salesperson),
) -> SalespersonProfileResponse:
    """Trivial protected endpoint verifying salesperson authentication (Phase 0)."""
    return SalespersonProfileResponse(
        user_id=current_user.user_id,
        email=current_user.email,
        role=current_user.role,
    )
