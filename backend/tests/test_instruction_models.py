from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

from backend.auditor.ollama_runtime import OllamaState
from backend.auditor.providers.fake import FakeInstructionModel
from backend.auditor.providers.instruction import (
    GenerationOptions,
    InstructionModelTimeout,
    InstructionRequest,
    PydanticOutputSchema,
    StructuredOutputError,
)
from backend.auditor.providers.ollama.instruction import OllamaInstructionModel


class ResultSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str


REQUEST = InstructionRequest(
    system_prompt="Return a status object.",
    user_prompt="Local test input.",
    prompt_version="test-prompt-v1",
)
SCHEMA = PydanticOutputSchema(ResultSchema)


def test_ollama_adapter_hides_provider_response_shape() -> None:
    def fetcher(
        _url: str, payload: dict[str, Any] | None, timeout: float
    ) -> dict[str, Any]:
        assert payload is not None
        assert payload["stream"] is False
        assert payload["think"] is False
        assert payload["format"] == ResultSchema.model_json_schema()
        assert timeout == 3
        return {
            "response": '{"status":"ready"}',
            "done": True,
            "prompt_eval_count": 10,
            "eval_count": 4,
        }

    model = OllamaInstructionModel(
        base_url="http://localhost:11434",
        model_name="configured-model",
        timeout_seconds=3,
        fetcher=fetcher,
    )

    result = model.generate_structured(REQUEST, SCHEMA)

    assert result.value.status == "ready"
    assert result.metadata.model == "configured-model"
    assert result.metadata.prompt_tokens == 10
    assert not hasattr(result, "response")


def test_ollama_adapter_allows_only_one_structured_repair() -> None:
    responses = iter(
        [
            {"response": '{"unexpected":true}', "done": True},
            {"response": '{"status":"repaired"}', "done": True},
        ]
    )

    def fetcher(*_args: Any) -> dict[str, Any]:
        return next(responses)

    model = OllamaInstructionModel(
        base_url="http://localhost:11434",
        model_name="configured-model",
        timeout_seconds=3,
        fetcher=fetcher,
    )

    result = model.generate_structured(REQUEST, SCHEMA)

    assert result.value.status == "repaired"
    assert result.metadata.attempts == 2
    assert result.metadata.repaired is True


def test_invalid_output_after_repair_is_explicit_failure() -> None:
    fake = FakeInstructionModel([{}, {}])

    with pytest.raises(StructuredOutputError, match="remained invalid"):
        fake.generate_structured(REQUEST, SCHEMA)


def test_fake_adapter_can_disable_repair() -> None:
    fake = FakeInstructionModel([{}, {"status": "unused"}])

    with pytest.raises(StructuredOutputError):
        fake.generate_structured(REQUEST, SCHEMA, GenerationOptions(allow_repair=False))
    assert len(fake.requests) == 1


def test_timeout_becomes_provider_independent_error() -> None:
    def timeout(*_args: Any) -> dict[str, Any]:
        raise TimeoutError

    model = OllamaInstructionModel(
        base_url="http://localhost:11434",
        model_name="configured-model",
        timeout_seconds=3,
        fetcher=timeout,
    )

    with pytest.raises(InstructionModelTimeout):
        model.generate_structured(REQUEST, SCHEMA)


def test_instruction_readiness_checks_only_the_configured_instruction_model() -> None:
    def tags(*_args: Any) -> dict[str, Any]:
        return {"models": [{"name": "configured-model:latest"}]}

    model = OllamaInstructionModel(
        base_url="http://localhost:11434",
        model_name="configured-model",
        timeout_seconds=3,
        fetcher=tags,
    )

    assert model.readiness().state is OllamaState.READY
