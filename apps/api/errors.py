"""Public API error types and exception handlers."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    error: ErrorBody


def _payload(
    request: Request,
    code: str,
    message: str,
    details: dict[str, Any],
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": request.state.request_id,
            "details": details,
        }
    }


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, error: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content=_payload(request, error.code, error.message, error.details),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        fields = [
            {"location": list(item["loc"]), "type": item["type"]}
            for item in error.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=_payload(
                request,
                "VALIDATION_ERROR",
                "The request could not be validated.",
                {"fields": fields},
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(
        request: Request, error: StarletteHTTPException
    ) -> JSONResponse:
        code = "NOT_FOUND" if error.status_code == 404 else "HTTP_ERROR"
        message = (
            "The requested resource was not found."
            if error.status_code == 404
            else "The request failed."
        )
        return JSONResponse(
            status_code=error.status_code,
            content=_payload(request, code, message, {}),
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(
        request: Request, error: Exception
    ) -> JSONResponse:
        request.app.state.logger.exception(
            "Unhandled API error",
            extra={
                "request_id": request.state.request_id,
                "error_type": type(error).__name__,
            },
        )
        return JSONResponse(
            status_code=500,
            content=_payload(
                request,
                "INTERNAL_ERROR",
                "An unexpected error occurred.",
                {},
            ),
        )
