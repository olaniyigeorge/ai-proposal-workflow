from fastapi import APIRouter
from app.api.v1.endpoints import auth, health, intake, proposals

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(intake.router, tags=["Intake"])
api_router.include_router(proposals.router, prefix="/proposals", tags=["Proposals"])
