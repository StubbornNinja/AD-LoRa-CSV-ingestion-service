from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ingest import auth, db
from ingest.config import Settings, load_settings
from ingest.middleware.envelope import ENVELOPE_HEADER, EnvelopeMiddleware
from ingest.routers import chirpstack, health, intake


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    if settings is None:
        settings = load_settings()

    application = FastAPI(
        title="AD ChirpStack API Gateway",
        version="1.0.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url="/api/redoc",
    )

    # Configure modules
    auth.configure(settings.ingest_api_token)
    db.configure(settings.resolved_db_path)
    intake.configure(settings)

    # Ensure directories exist
    settings.resolved_upload_dir.mkdir(parents=True, exist_ok=True)
    settings.resolved_db_path.parent.mkdir(parents=True, exist_ok=True)

    # Exception handlers — produce the envelope directly and mark with header
    # so the middleware knows not to double-wrap.
    @application.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"ok": False, "error": {"message": str(exc.detail), "code": exc.status_code}},
            headers={ENVELOPE_HEADER: "1"},
        )

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"ok": False, "error": {"message": str(exc), "code": 422}},
            headers={ENVELOPE_HEADER: "1"},
        )

    # Middleware (wraps normal responses; exception handlers above catch errors)
    application.add_middleware(EnvelopeMiddleware)

    # Routers
    application.include_router(health.router, prefix="/api/v1")
    application.include_router(intake.router, prefix="/api/v1")
    application.include_router(chirpstack.router, prefix="/api/v1")

    # Initialize database
    db.init_db()

    return application
