from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from backend.auditor.domain.audits import AuditLanguage, ClaimType
from backend.auditor.providers.instruction import (
    GenerationMetadata,
    GenerationOptions,
    InstructionModel,
    InstructionRequest,
    PydanticOutputSchema,
)
from backend.auditor.text.sentences import OFFSET_CONVENTION_VERSION, SentenceSpan

CLAIM_EXTRACTION_PROMPT_VERSION = "claim-extraction-v1"


class Atomicity(StrEnum):
    ATOMIC = "atomic"
    COMPOUND = "compound"


class Verifiability(StrEnum):
    EXTERNALLY_VERIFIABLE = "externally_verifiable"
    INTERNALLY_VERIFIABLE = "internally_verifiable"
    NOT_VERIFIABLE = "not_verifiable"


class SourceMention(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(min_length=1)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)


class AtomicClaimCandidate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # Ollama's JSON-schema grammar accepts explicit digit classes, not ``\d``.
    sentence_id: str = Field(pattern=r"^s[0-9]{4}$")
    exact_text: str = Field(min_length=1)
    normalized_text: str = Field(min_length=1)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    atomicity: Atomicity
    verifiability: Verifiability
    primary_type: ClaimType
    secondary_types: tuple[ClaimType, ...] = ()
    confidence: float = Field(ge=0, le=1)
    quantities: tuple[SourceMention, ...] = ()
    entities: tuple[SourceMention, ...] = ()

    @field_validator("secondary_types")
    @classmethod
    def secondary_types_are_unique(
        cls, values: tuple[ClaimType, ...]
    ) -> tuple[ClaimType, ...]:
        if len(values) != len(set(values)):
            raise ValueError("Secondary claim types must be unique.")
        return values

    @model_validator(mode="after")
    def validate_against_request(self, info: ValidationInfo) -> Self:
        context = info.context or {}
        source = context.get("source_text")
        sentences = context.get("sentences")
        if not isinstance(source, str) or not isinstance(sentences, dict):
            raise ValueError("Claim validation requires source and sentence context.")
        sentence = sentences.get(self.sentence_id)
        if not isinstance(sentence, SentenceSpan):
            raise ValueError("Claim references a sentence outside the request.")
        if self.atomicity is not Atomicity.ATOMIC:
            raise ValueError("Extracted claims must contain one atomic proposition.")
        if self.primary_type in self.secondary_types:
            raise ValueError("The primary claim type cannot also be secondary.")
        if not (
            sentence.start_offset
            <= self.start_offset
            < self.end_offset
            <= sentence.end_offset
        ):
            raise ValueError(
                "Claim offsets must remain inside the referenced sentence."
            )
        if source[self.start_offset : self.end_offset] != self.exact_text:
            raise ValueError("Claim offsets do not match the exact source substring.")
        for mention in (*self.quantities, *self.entities):
            if not (
                self.start_offset
                <= mention.start_offset
                < mention.end_offset
                <= self.end_offset
            ):
                raise ValueError("Mention offsets must remain inside the claim span.")
            if source[mention.start_offset : mention.end_offset] != mention.text:
                raise ValueError("Mention offsets do not match the source substring.")
        return self


class ClaimExtractionResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    claims: tuple[AtomicClaimCandidate, ...]

    @model_validator(mode="after")
    def claims_are_unique_and_bounded(self, info: ValidationInfo) -> Self:
        context = info.context or {}
        maximum = context.get("max_claims")
        if not isinstance(maximum, int):
            raise ValueError("Claim validation requires a maximum claim count.")
        if len(self.claims) > maximum:
            raise ValueError("The model returned more claims than requested.")
        identities = [
            (claim.start_offset, claim.end_offset, claim.exact_text)
            for claim in self.claims
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("Duplicate claims are not allowed.")
        return self


class ExtractedClaim(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ordinal: int = Field(ge=0)
    sentence_id: str
    exact_text: str
    normalized_text: str
    start_offset: int
    end_offset: int
    atomicity: Atomicity
    verifiability: Verifiability
    primary_type: ClaimType
    secondary_types: tuple[ClaimType, ...]
    confidence: float
    quantities: tuple[SourceMention, ...]
    entities: tuple[SourceMention, ...]


@dataclass(frozen=True)
class ClaimExtractionBatch:
    claims: tuple[ExtractedClaim, ...]
    language: AuditLanguage
    offset_convention: str
    metadata: GenerationMetadata


@dataclass(frozen=True)
class ClaimExtractionConfig:
    prompt_version: str = CLAIM_EXTRACTION_PROMPT_VERSION
    max_claims: int = 64
    max_output_tokens: int = 4_096


class ClaimExtractor(Protocol):
    def extract(
        self,
        sentences: tuple[SentenceSpan, ...],
        context: str,
        language: AuditLanguage,
        config: ClaimExtractionConfig | None = None,
    ) -> ClaimExtractionBatch: ...


class ModelClaimExtractor:
    def __init__(self, instruction_model: InstructionModel) -> None:
        self._instruction_model = instruction_model

    def extract(
        self,
        sentences: tuple[SentenceSpan, ...],
        context: str,
        language: AuditLanguage,
        config: ClaimExtractionConfig | None = None,
    ) -> ClaimExtractionBatch:
        selected_config = config or ClaimExtractionConfig()
        sentence_map = {sentence.id: sentence for sentence in sentences}
        for sentence in sentences:
            if context[sentence.start_offset : sentence.end_offset] != sentence.text:
                raise ValueError("Sentence offsets do not match extraction context.")
            if sentence.language is not language:
                raise ValueError(
                    "Sentence language does not match extraction language."
                )

        request = InstructionRequest(
            system_prompt=_system_prompt(language, selected_config.max_claims),
            user_prompt=json.dumps(
                {
                    "language": language.value,
                    "offset_convention": OFFSET_CONVENTION_VERSION,
                    "source_text": context,
                    "sentences": [
                        {
                            "id": sentence.id,
                            "text": sentence.text,
                            "start_offset": sentence.start_offset,
                            "end_offset": sentence.end_offset,
                        }
                        for sentence in sentences
                    ],
                },
                ensure_ascii=False,
            ),
            prompt_version=selected_config.prompt_version,
        )
        schema = PydanticOutputSchema(
            ClaimExtractionResponse,
            context={
                "source_text": context,
                "sentences": sentence_map,
                "max_claims": selected_config.max_claims,
            },
        )
        result = self._instruction_model.generate_structured(
            request,
            schema,
            GenerationOptions(
                temperature=0,
                max_tokens=selected_config.max_output_tokens,
                allow_repair=True,
            ),
        )
        ordered = sorted(
            result.value.claims,
            key=lambda claim: (claim.start_offset, claim.end_offset, claim.exact_text),
        )
        claims = tuple(
            ExtractedClaim(
                ordinal=ordinal,
                **candidate.model_dump(),
            )
            for ordinal, candidate in enumerate(ordered)
        )
        return ClaimExtractionBatch(
            claims=claims,
            language=language,
            offset_convention=OFFSET_CONVENTION_VERSION,
            metadata=result.metadata,
        )


def _system_prompt(language: AuditLanguage, max_claims: int) -> str:
    language_name = "English" if language is AuditLanguage.ENGLISH else "Slovak"
    return (
        "Extract atomic claims from the supplied sentences. Each output claim must "
        "express exactly one proposition and copy an exact, contiguous source span. "
        "Use global zero-based, end-exclusive Unicode code-point offsets. Reference "
        "only supplied sentence IDs. Classify with allowlisted schema values, identify "
        "quantity and entity spans only when explicit and their exact offsets are "
        "certain; otherwise return empty arrays for those optional mentions. Never "
        "return duplicate claims. Return no more than "
        f"{max_claims} claims. Analyze {language_name} text in {language_name}. "
        "Return concise structured fields only; do not provide reasoning."
    )
