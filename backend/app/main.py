from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.api import api_router
from app.api.v1.endpoints.health import router as health_router
from app.core.config import settings
from app.utils.logger import logger

INTAKE_PATH = f"{settings.API_V1_STR}/intake"


def create_application() -> FastAPI:
    application = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=f"{settings.API_V1_STR}/docs",
        redoc_url=f"{settings.API_V1_STR}/redoc",
    )

    if settings.BACKEND_CORS_ORIGINS:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=settings.BACKEND_CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Root health check
    application.include_router(health_router, tags=["Health"])

    # API v1 routes
    application.include_router(api_router, prefix=settings.API_V1_STR)

    @application.exception_handler(RequestValidationError)
    async def intake_schema_drift_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """FastAPI's default 422 on `/intake` is exactly the "schema drift"
        signal called out in docs/edge-cases.md — a Form/Sheet field the n8n
        Code node maps that IntakePayload no longer accepts (renamed/removed
        field), or a new column n8n passes through under its raw header
        hitting `extra="forbid"`. n8n's own alert branch may or may not be
        wired/reachable for a given failure, so this logs independently, at
        ERROR with a greppable tag, so a log-based monitor (CloudWatch/Datadog/
        Sentry alert rule, etc.) can page an admin without depending on n8n at
        all. Every other route keeps the default validation-error handling —
        only the message tag differs so INTAKE_SCHEMA_DRIFT can be filtered on.
        """
        body = await request.body()
        errors = jsonable_encoder(exc.errors())
        if request.url.path == INTAKE_PATH:
            logger.error(
                "INTAKE_SCHEMA_DRIFT path=%s errors=%s raw_body=%s",
                request.url.path,
                errors,
                body.decode("utf-8", errors="replace"),
            )
        else:
            logger.warning(
                "VALIDATION_ERROR path=%s errors=%s", request.url.path, errors
            )
        return JSONResponse(status_code=422, content={"detail": errors})

    return application


app = create_application()
