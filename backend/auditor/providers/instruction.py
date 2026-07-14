from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol, TypeVar

from pydantic import BaseModel

OutputT = TypeVar("OutputT", bound=BaseModel)


@dataclass(frozen=True)
class InstructionRequest:
    system_prompt: str
    user_prompt: str
    prompt_version: str


@dataclass(frozen=True)
class GenerationOptions:
    temperature: float = 0
    max_tokens: int = 2_048
    allow_repair: bool = True
    keep_alive: str = "5m"


@dataclass(frozen=True)
class GenerationMetadata:
    model: str
    prompt_version: str
    attempts: int
    repaired: bool
    prompt_tokens: int | None = None
    generated_tokens: int | None = None


@dataclass(frozen=True)
class StructuredResult[OutputT: BaseModel]:
    value: OutputT
    metadata: GenerationMetadata


@dataclass(frozen=True)
class PydanticOutputSchema[OutputT: BaseModel]:
    """A Pydantic schema plus request-specific validation context."""

    model: type[OutputT]
    context: Mapping[str, object] = field(default_factory=dict)

    def json_schema(self) -> dict[str, object]:
        return self.model.model_json_schema()

    def validate_json(self, raw_json: str) -> OutputT:
        return self.model.model_validate_json(raw_json, context=dict(self.context))


class InstructionModel(Protocol):
    @property
    def model_name(self) -> str: ...

    def generate_structured(
        self,
        request: InstructionRequest,
        schema: PydanticOutputSchema[OutputT],
        options: GenerationOptions | None = None,
    ) -> StructuredResult[OutputT]: ...


class InstructionModelError(RuntimeError):
    """Base exception carrying no private prompt or response content."""


class InstructionModelUnavailable(InstructionModelError):
    pass


class InstructionModelTimeout(InstructionModelError):
    pass


class StructuredOutputError(InstructionModelError):
    pass
