from fastapi import APIRouter
from app.api.v1.endpoints import activity, auth, client_feedback, feedback, health, intake, proposals, public

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(client_feedback.router, prefix="/client", tags=["Public client-facing (unauthenticated)"])
api_router.include_router(intake.router, tags=["Intake (webhook)"])
api_router.include_router(public.router, prefix="/public", tags=["Public document access (unauthenticated)"])
api_router.include_router(feedback.router, prefix="/salesperson", tags=["Salesperson (authenticated)"])
api_router.include_router(proposals.router, prefix="/proposals", tags=["Proposals (authenticated)"])
api_router.include_router(activity.router, prefix="/activity", tags=["Activity log (authenticated)"])