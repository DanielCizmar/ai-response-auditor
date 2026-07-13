from typing import Any
from urllib.error import URLError

import pytest

from backend.auditor.ollama_runtime import (
    OllamaConfig,
    OllamaState,
    canonical_model_name,
    probe_ollama,
    run_generation_smoke,
)


CONFIG = OllamaConfig(
    base_url="http://localhost:11434",
    instruction_model="instruction-model",
    embedding_model="embedding-model",
    timeout_seconds=1,
)


def test_readiness_reports_unavailable_server() -> None:
    def unavailable(*_args: Any) -> dict[str, Any]:
        raise URLError("offline")

    readiness = probe_ollama(CONFIG, unavailable)

    assert readiness.state is OllamaState.UNAVAILABLE
    assert readiness.ready is False
    assert "offline" in (readiness.detail or "")


def test_readiness_reports_missing_instruction_model() -> None:
    def only_embedding(*_args: Any) -> dict[str, Any]:
        return {"models": [{"name": "embedding-model:latest"}]}

    readiness = probe_ollama(CONFIG, only_embedding)

    assert readiness.state is OllamaState.INSTRUCTION_MODEL_MISSING
    assert readiness.available_models == ("embedding-model:latest",)


def test_readiness_reports_missing_embedding_model() -> None:
    def only_instruction(*_args: Any) -> dict[str, Any]:
        return {"models": [{"model": "instruction-model:latest"}]}

    readiness = probe_ollama(CONFIG, only_instruction)

    assert readiness.state is OllamaState.EMBEDDING_MODEL_MISSING


def test_readiness_accepts_configured_models() -> None:
    def all_models(*_args: Any) -> dict[str, Any]:
        return {
            "models": [
                {"name": "instruction-model:latest"},
                {"model": "embedding-model:latest"},
            ]
        }

    readiness = probe_ollama(CONFIG, all_models)

    assert readiness.state is OllamaState.READY
    assert readiness.ready is True


def test_readiness_reports_active_model_loading() -> None:
    def all_models(*_args: Any) -> dict[str, Any]:
        return {
            "models": [
                {"name": "instruction-model:latest"},
                {"name": "embedding-model:latest"},
            ]
        }

    readiness = probe_ollama(CONFIG, all_models, model_loading=True)

    assert readiness.state is OllamaState.MODEL_LOADING
    assert readiness.ready is False


def test_canonical_model_name_preserves_explicit_tag() -> None:
    assert canonical_model_name("model:4b") == "model:4b"
    assert canonical_model_name("model") == "model:latest"


def test_generation_smoke_requires_expected_structured_result() -> None:
    def generated(
        _url: str, payload: dict[str, Any] | None, _timeout: float
    ) -> dict[str, Any]:
        assert payload is not None
        assert payload["model"] == CONFIG.instruction_model
        assert payload["stream"] is False
        assert payload["think"] is False
        return {"response": '{"status":"ready"}', "done": True}

    response = run_generation_smoke(CONFIG, generated)

    assert response["done"] is True


def test_generation_smoke_rejects_unexpected_result() -> None:
    def generated(*_args: Any) -> dict[str, Any]:
        return {"response": '{"status":"wrong"}', "done": True}

    with pytest.raises(ValueError, match="Unexpected structured generation"):
        run_generation_smoke(CONFIG, generated)
