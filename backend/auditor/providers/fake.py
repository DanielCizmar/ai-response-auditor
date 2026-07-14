from __future__ import annotations

import json
from collections import deque
from collections.abc import Iterable
from typing import Any

from pydantic import ValidationError

from backend.auditor.providers.instruction import (
    GenerationMetadata,
    GenerationOptions,
    InstructionRequest,
    OutputT,
    PydanticOutputSchema,
    StructuredOutputError,
    StructuredResult,
)


class FakeInstructionModel:
    """Deterministic structured model used by tests and ordinary CI."""

    def __init__(
        self,
        responses: Iterable[dict[str, Any] | str | Exception],
        *,
        model_name: str = "fake-instruction-v1",
    ) -> None:
        self._responses = deque(responses)
        self._model_name = model_name
        self.requests: list[InstructionRequest] = []

    @property
    def model_name(self) -> str:
        return self._model_name

    def generate_structured(
        self,
        request: InstructionRequest,
        schema: PydanticOutputSchema[OutputT],
        options: GenerationOptions | None = None,
    ) -> StructuredResult[OutputT]:
        selected_options = options or GenerationOptions()
        self.requests.append(request)
        maximum_attempts = 2 if selected_options.allow_repair else 1

        for attempt in range(1, maximum_attempts + 1):
            if not self._responses:
                raise StructuredOutputError(
                    "The fake model has no configured response."
                )
            response = self._responses.popleft()
            if isinstance(response, Exception):
                raise response
            raw = response if isinstance(response, str) else json.dumps(response)
            try:
                value = schema.validate_json(raw)
            except (ValidationError, ValueError):
                if attempt == maximum_attempts:
                    raise StructuredOutputError(
                        "Structured output remained invalid after bounded repair."
                    ) from None
                continue
            return StructuredResult(
                value=value,
                metadata=GenerationMetadata(
                    model=self.model_name,
                    prompt_version=request.prompt_version,
                    attempts=attempt,
                    repaired=attempt > 1,
                ),
            )

        raise AssertionError("Unreachable structured generation state.")
