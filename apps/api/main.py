"""FastAPI application factory and system endpoints."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.responses import Response

from apps.api.audits import build_audit_router
from apps.api.errors import ErrorEnvelope, install_error_handlers
from backend.auditor import __version__
from backend.auditor.audits.service import AuditApplication, AuditService
from backend.auditor.config import Settings, get_settings
from backend.auditor.db.session import build_session_factory
from backend.auditor.logging import configure_logging
from backend.auditor.providers.ollama.instruction import OllamaInstructionModel
from backend.auditor.readiness import ReadinessService, build_readiness_service


class HealthResponse(BaseModel):
    status: str
    version: str


class DependencyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    state: str
    ready: bool
    required: bool
    action: str | None = None


class ReadinessResponse(BaseModel):
    status: str
    dependencies: dict[str, DependencyResponse]


def _request_id(value: str | None) -> str:
    try:
        return str(UUID(value)) if value else str(uuid4())
    except ValueError:
        return str(uuid4())


def create_app(
    settings: Settings | None = None,
    readiness_service: ReadinessService | None = None,
    audit_service: AuditService | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.app_log_level)
    logger = logging.getLogger("auditor.api")
    service = readiness_service or build_readiness_service(settings)
    engine = None
    if audit_service is None:
        engine, sessions = build_session_factory(settings)
        audit_service = AuditApplication(
            sessions,
            OllamaInstructionModel(
                base_url=settings.ollama_base_url,
                model_name=settings.ollama_instruction_model,
                timeout_seconds=settings.ollama_request_timeout_seconds,
            ),
        )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        logger.info("API started", extra={"environment": settings.app_environment})
        yield
        if engine is not None:
            engine.dispose()
        logger.info("API stopped")

    app = FastAPI(
        title="Evidence-Grounded Writing Auditor API",
        description=(
            "Local-first writing-risk and evidence-alignment API. "
            "It is not a scientific truth detector."
        ),
        version=__version__,
        docs_url="/docs",
        openapi_url="/openapi.json",
        responses={
            404: {"model": ErrorEnvelope, "description": "Resource not found"},
            422: {"model": ErrorEnvelope, "description": "Request validation failed"},
            500: {"model": ErrorEnvelope, "description": "Unexpected server error"},
        },
        lifespan=lifespan,
    )
    app.state.logger = logger
    install_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allowed_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Accept", "Content-Type", "Idempotency-Key", "X-Request-ID"],
        expose_headers=["Idempotent-Replay", "X-Request-ID"],
    )

    @app.middleware("http")
    async def request_metadata(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request.state.request_id = _request_id(request.headers.get("X-Request-ID"))
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        logger.info(
            "HTTP request completed",
            extra={
                "request_id": request.state.request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
        return response

    @app.get("/v1/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(status="healthy", version=__version__)

    @app.get(
        "/v1/readiness",
        response_model=ReadinessResponse,
        responses={503: {"model": ReadinessResponse}},
        tags=["system"],
    )
    def readiness() -> ReadinessResponse | JSONResponse:
        dependencies = service.check()
        ready = all(item.ready for item in dependencies.values() if item.required)
        body = ReadinessResponse(
            status="ready" if ready else "not_ready",
            dependencies={
                name: DependencyResponse.model_validate(item)
                for name, item in dependencies.items()
            },
        )
        if not ready:
            return JSONResponse(status_code=503, content=body.model_dump())
        return body

    app.include_router(build_audit_router(audit_service, service))

    return app


app = create_app()
