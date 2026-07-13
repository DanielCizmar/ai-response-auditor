from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.errors import ApiError
from apps.api.main import create_app
from backend.auditor.config import Settings
from backend.auditor.readiness import DependencyStatus, ReadinessService


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
            "database": {"state": "ready", "ready": True, "required": True, "action": None},
            "redis": {"state": "ready", "ready": True, "required": True, "action": None},
            "ollama": {"state": "ready", "ready": True, "required": True, "action": None},
            "worker": {"state": "not_configured", "ready": False, "required": False, "action": None},
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
    response = client().get("/v1/health", headers={"X-Request-ID": "private free-form value"})

    assert UUID(response.headers["X-Request-ID"])
