from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from apps.api.errors import ApiError
from backend.auditor.audits.service import (
    AuditNotFoundError,
    AuditResult,
    AuditService,
    IdempotencyConflictError,
)
from backend.auditor.domain.audits import AuditLanguage
from backend.auditor.readiness import ReadinessService

IdempotencyKey = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$",
    ),
]


class CreateAuditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=10_000)
    language: AuditLanguage

    @field_validator("text")
    @classmethod
    def text_has_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Audit text must contain a non-whitespace character.")
        return value


def build_audit_router(
    audit_service: AuditService,
    readiness_service: ReadinessService,
) -> APIRouter:
    router = APIRouter(prefix="/v1/audits", tags=["audits"])

    @router.post(
        "",
        response_model=AuditResult,
        status_code=201,
        responses={
            409: {"description": "Idempotency key conflict"},
            503: {"description": "A required local service or model is not ready"},
        },
    )
    def create_audit(
        request: CreateAuditRequest,
        response: Response,
        idempotency_key: IdempotencyKey,
    ) -> AuditResult:
        _require_ready(readiness_service)
        result, replayed = _create(
            audit_service, request.text, request.language, idempotency_key
        )
        if replayed:
            response.status_code = 200
            response.headers["Idempotent-Replay"] = "true"
        return result

    @router.get(
        "/{audit_id}",
        response_model=AuditResult,
        responses={404: {"description": "Audit not found"}},
    )
    def get_audit(audit_id: UUID) -> AuditResult:
        try:
            return audit_service.get(audit_id)
        except AuditNotFoundError as error:
            raise ApiError(
                "AUDIT_NOT_FOUND", "The requested audit was not found.", status_code=404
            ) from error

    @router.post(
        "/{audit_id}/re-audit",
        response_model=AuditResult,
        status_code=201,
        responses={
            404: {"description": "Source audit not found"},
            409: {"description": "Idempotency key conflict"},
            503: {"description": "A required local service or model is not ready"},
        },
    )
    def re_audit(
        audit_id: UUID,
        response: Response,
        idempotency_key: IdempotencyKey,
        request: CreateAuditRequest | None = None,
    ) -> AuditResult:
        _require_ready(readiness_service)
        try:
            original = audit_service.get(audit_id)
        except AuditNotFoundError as error:
            raise ApiError(
                "AUDIT_NOT_FOUND", "The requested audit was not found.", status_code=404
            ) from error
        result, replayed = _create(
            audit_service,
            request.text if request is not None else original.input_text,
            (
                request.language
                if request is not None
                else AuditLanguage(original.language)
            ),
            idempotency_key,
            re_audit_of_id=audit_id,
        )
        if replayed:
            response.status_code = 200
            response.headers["Idempotent-Replay"] = "true"
        return result

    return router


def _create(
    service: AuditService,
    text: str,
    language: AuditLanguage,
    idempotency_key: str,
    *,
    re_audit_of_id: UUID | None = None,
) -> tuple[AuditResult, bool]:
    try:
        return service.create(
            text,
            language,
            idempotency_key,
            re_audit_of_id=re_audit_of_id,
        )
    except AuditNotFoundError as error:
        raise ApiError(
            "AUDIT_NOT_FOUND", "The requested audit was not found.", status_code=404
        ) from error
    except IdempotencyConflictError as error:
        raise ApiError(
            "IDEMPOTENCY_CONFLICT",
            "The idempotency key was already used for another audit request.",
            status_code=409,
        ) from error


def _require_ready(service: ReadinessService) -> None:
    dependencies = service.check()
    unavailable = {
        name: status
        for name, status in dependencies.items()
        if status.required and not status.ready
    }
    if not unavailable:
        return
    ollama = unavailable.get("ollama")
    if ollama is not None and ollama.state in {
        "instruction_model_missing",
        "embedding_model_missing",
        "model_loading",
    }:
        raise ApiError(
            "MODEL_NOT_READY",
            "The configured local model is not ready.",
            status_code=503,
            details={"state": ollama.state, "action": ollama.action},
        )
    raise ApiError(
        "SERVICE_NOT_READY",
        "A required local service is not ready.",
        status_code=503,
        details={"dependencies": sorted(unavailable)},
    )
