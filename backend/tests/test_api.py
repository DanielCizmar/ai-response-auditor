from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.errors import ApiError
from apps.api.main import create_app
from backend.auditor.audits.service import (
    AUDIT_PIPELINE_VERSION,
    AuditNotFoundError,
    AuditResult,
    IdempotencyConflictError,
)
from backend.auditor.config import Settings
from backend.auditor.readiness import DependencyStatus, ReadinessService


class FakeAuditService:
    def __init__(self) -> None:
        self.by_id: dict[UUID, AuditResult] = {}
        self.by_key: dict[str, AuditResult] = {}

    def create(
        self,
        text: str,
        language: Any,
        idempotency_key: str,
        *,
        re_audit_of_id: UUID | None = None,
    ) -> tuple[AuditResult, bool]:
        existing = self.by_key.get(idempotency_key)
        if existing is not None:
            if (
                existing.input_text != text
                or existing.language != language.value
                or existing.re_audit_of_id != re_audit_of_id
            ):
                raise IdempotencyConflictError
            return existing, True
        now = datetime.now(UTC)
        result = AuditResult.model_validate(
            {
                "id": uuid4(),
                "re_audit_of_id": re_audit_of_id,
                "source_type": "pasted_text",
                "language": language.value,
                "input_text": text,
                "state": "succeeded",
                "pipeline_version": AUDIT_PIPELINE_VERSION,
                "model_manifest": {"instruction_model": "fake-instruction-v1"},
                "scoring_version": "mvp1-risk-v1",
                "normalization_version": "unicode-code-points-v1",
                "started_at": now,
                "completed_at": now,
                "safe_error_code": None,
                "created_at": now,
                "claims": [],
                "events": [],
            }
        )
        self.by_id[result.id] = result
        self.by_key[idempotency_key] = result
        return result, False

    def get(self, audit_id: UUID) -> AuditResult:
        try:
            return self.by_id[audit_id]
        except KeyError as error:
            raise AuditNotFoundError from error


def service(**overrides: DependencyStatus) -> ReadinessService:
    statuses = {
        "database": DependencyStatus("ready", True),
        "redis": DependencyStatus("ready", True),
        "ollama": DependencyStatus("ready", True),
        "worker": DependencyStatus("not_configured", False, required=False),
    }
    statuses.update(overrides)
    return ReadinessService(
        {name: (lambda status=status: status) for name, status in statuses.items()}
    )


def client(readiness: ReadinessService | None = None) -> TestClient:
    settings = Settings(_env_file=None, app_log_level="CRITICAL")
    return TestClient(create_app(settings, readiness or service()))


def test_health_is_live_without_running_dependency_checks() -> None:
    response = client().get("/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "version": "0.0.0"}
    assert UUID(response.headers["X-Request-ID"])


def test_readiness_reports_each_required_dependency_and_optional_worker() -> None:
    response = client().get("/v1/readiness")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "dependencies": {
            "database": {
                "state": "ready",
                "ready": True,
                "required": True,
                "action": None,
            },
            "redis": {
                "state": "ready",
                "ready": True,
                "required": True,
                "action": None,
            },
            "ollama": {
                "state": "ready",
                "ready": True,
                "required": True,
                "action": None,
            },
            "worker": {
                "state": "not_configured",
                "ready": False,
                "required": False,
                "action": None,
            },
        },
    }


def test_readiness_is_503_and_preserves_action_when_model_is_missing() -> None:
    response = client(
        service(
            ollama=DependencyStatus(
                "instruction_model_missing",
                False,
                action="corepack pnpm ollama:setup",
            )
        )
    ).get("/v1/readiness")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["dependencies"]["ollama"] == {
        "state": "instruction_model_missing",
        "ready": False,
        "required": True,
        "action": "corepack pnpm ollama:setup",
    }


@pytest.mark.parametrize("dependency", ["database", "redis"])
def test_readiness_identifies_unavailable_required_dependency(dependency: str) -> None:
    response = client(
        service(**{dependency: DependencyStatus("unavailable", False)})
    ).get("/v1/readiness")

    assert response.status_code == 503
    assert response.json()["dependencies"][dependency]["state"] == "unavailable"


@pytest.mark.parametrize(
    "state",
    [
        "unavailable",
        "instruction_model_missing",
        "embedding_model_missing",
        "model_loading",
    ],
)
def test_readiness_preserves_each_non_ready_ollama_state(state: str) -> None:
    response = client(service(ollama=DependencyStatus(state, False))).get(
        "/v1/readiness"
    )

    assert response.status_code == 503
    assert response.json()["dependencies"]["ollama"]["state"] == state


def test_not_found_uses_standard_error_contract_and_request_id() -> None:
    request_id = "47de4a93-6c2c-4a35-a168-955906e99f3d"
    response = client().get("/v1/does-not-exist", headers={"X-Request-ID": request_id})

    assert response.status_code == 404
    assert response.headers["X-Request-ID"] == request_id
    assert response.json() == {
        "error": {
            "code": "NOT_FOUND",
            "message": "The requested resource was not found.",
            "request_id": request_id,
            "details": {},
        }
    }


def test_api_error_uses_standard_error_contract() -> None:
    app = create_app(Settings(_env_file=None, app_log_level="CRITICAL"), service())

    @app.get("/test-error")
    def test_error() -> None:
        raise ApiError("EXAMPLE_ERROR", "Example API error.", status_code=409)

    response = TestClient(app).get("/test-error")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EXAMPLE_ERROR"
    assert response.json()["error"]["details"] == {}


def test_unexpected_error_is_redacted_and_uses_standard_contract(capsys) -> None:
    app = create_app(Settings(_env_file=None, app_log_level="INFO"), service())

    @app.get("/test-unexpected-error")
    def test_error() -> None:
        raise RuntimeError("private draft contents")

    response = TestClient(app, raise_server_exceptions=False).get(
        "/test-unexpected-error"
    )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "private draft contents" not in capsys.readouterr().err


def test_openapi_documents_system_contracts_without_private_test_route() -> None:
    app: FastAPI = create_app(Settings(_env_file=None), service())
    schema: dict[str, Any] = app.openapi()

    assert schema["info"]["title"] == "Evidence-Grounded Writing Auditor API"
    assert "/v1/health" in schema["paths"]
    assert "/v1/readiness" in schema["paths"]
    assert "ErrorEnvelope" in schema["components"]["schemas"]


def test_invalid_request_id_is_replaced_with_uuid() -> None:
    response = client().get(
        "/v1/health", headers={"X-Request-ID": "private free-form value"}
    )

    assert UUID(response.headers["X-Request-ID"])


def test_create_get_and_reaudit_preserve_idempotency_and_lineage() -> None:
    audits = FakeAuditService()
    api = TestClient(
        create_app(
            Settings(_env_file=None, app_log_level="CRITICAL"),
            service(),
            audits,
        )
    )
    headers = {"Idempotency-Key": "request-0001"}

    created = api.post(
        "/v1/audits",
        headers=headers,
        json={"text": "A bounded claim.", "language": "en"},
    )
    assert created.status_code == 201
    audit_id = created.json()["id"]

    replay = api.post(
        "/v1/audits",
        headers=headers,
        json={"text": "A bounded claim.", "language": "en"},
    )
    assert replay.status_code == 200
    assert replay.headers["Idempotent-Replay"] == "true"
    assert replay.json()["id"] == audit_id

    fetched = api.get(f"/v1/audits/{audit_id}")
    assert fetched.status_code == 200
    assert fetched.json()["input_text"] == "A bounded claim."

    rerun = api.post(
        f"/v1/audits/{audit_id}/re-audit",
        headers={"Idempotency-Key": "request-0002"},
    )
    assert rerun.status_code == 201
    assert rerun.json()["id"] != audit_id
    assert rerun.json()["re_audit_of_id"] == audit_id


def test_create_audit_rejects_reused_key_for_different_content() -> None:
    audits = FakeAuditService()
    api = TestClient(create_app(Settings(_env_file=None), service(), audits))
    headers = {"Idempotency-Key": "request-0001"}
    api.post(
        "/v1/audits",
        headers=headers,
        json={"text": "First claim.", "language": "en"},
    )

    response = api.post(
        "/v1/audits",
        headers=headers,
        json={"text": "Different claim.", "language": "en"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_create_audit_exposes_missing_model_without_sending_text_to_pipeline() -> None:
    audits = FakeAuditService()
    api = TestClient(
        create_app(
            Settings(_env_file=None),
            service(
                ollama=DependencyStatus(
                    "instruction_model_missing",
                    False,
                    action="corepack pnpm ollama:setup",
                )
            ),
            audits,
        )
    )

    response = api.post(
        "/v1/audits",
        headers={"Idempotency-Key": "request-0001"},
        json={"text": "A private claim.", "language": "en"},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "MODEL_NOT_READY"
    assert audits.by_id == {}


def test_create_audit_rejects_whitespace_and_oversized_text() -> None:
    api = TestClient(
        create_app(Settings(_env_file=None), service(), FakeAuditService())
    )
    for text in ("   ", "x" * 10_001):
        response = api.post(
            "/v1/audits",
            headers={"Idempotency-Key": "request-0001"},
            json={"text": text, "language": "en"},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
