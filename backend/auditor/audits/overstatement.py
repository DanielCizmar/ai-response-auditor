from __future__ import annotations

import json
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, model_validator

from backend.auditor.audits.claims import ExtractedClaim
from backend.auditor.checks.findings import AuditFinding, FindingType
from backend.auditor.domain.audits import (
    AuditLanguage,
    FindingSeverity,
    FindingSource,
)
from backend.auditor.providers.instruction import (
    GenerationMetadata,
    GenerationOptions,
    InstructionModel,
    InstructionRequest,
    PydanticOutputSchema,
)

OVERSTATEMENT_PROMPT_VERSION = "overstatement-check-v1"
_ALLOWED_TYPES = {
    FindingType.CAUSAL_OVERSTATEMENT,
    FindingType.CERTAINTY_OVERSTATEMENT,
    FindingType.COMPARATIVE_AMBIGUITY,
    FindingType.SCOPE_AMBIGUITY,
}


class ModelFinding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    claim_ordinal: int = Field(ge=0)
    finding_type: FindingType
    severity: FindingSeverity
    confidence: float = Field(ge=0, le=1)
    quotation: str = Field(min_length=1)
    explanation: str = Field(min_length=1, max_length=400)

    @model_validator(mode="after")
    def validate_against_claims(self, info: ValidationInfo) -> ModelFinding:
        claims = (info.context or {}).get("claims")
        if not isinstance(claims, dict):
            raise ValueError("Finding validation requires claim context.")
        claim = claims.get(self.claim_ordinal)
        if not isinstance(claim, ExtractedClaim):
            raise ValueError("Finding references a claim outside the request.")
        if self.finding_type not in _ALLOWED_TYPES:
            raise ValueError("Finding type is not an overstatement or scope check.")
        if self.quotation not in claim.exact_text:
            raise ValueError("Finding quotation is not part of the supplied claim.")
        return self


class OverstatementResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    findings: tuple[ModelFinding, ...]

    @model_validator(mode="after")
    def findings_are_unique(self) -> OverstatementResponse:
        identities = [
            (finding.claim_ordinal, finding.finding_type) for finding in self.findings
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("Duplicate model-assisted findings are not allowed.")
        return self


@dataclass(frozen=True)
class OverstatementBatch:
    findings: tuple[AuditFinding, ...]
    metadata: GenerationMetadata


class ModelOverstatementChecker:
    def __init__(self, instruction_model: InstructionModel) -> None:
        self._instruction_model = instruction_model

    def check(
        self,
        claims: tuple[ExtractedClaim, ...],
        language: AuditLanguage,
    ) -> OverstatementBatch:
        claim_map = {claim.ordinal: claim for claim in claims}
        request = InstructionRequest(
            system_prompt=_system_prompt(language),
            user_prompt=json.dumps(
                {
                    "language": language.value,
                    "claims": [
                        {"ordinal": claim.ordinal, "text": claim.exact_text}
                        for claim in claims
                    ],
                },
                ensure_ascii=False,
            ),
            prompt_version=OVERSTATEMENT_PROMPT_VERSION,
        )
        result = self._instruction_model.generate_structured(
            request,
            PydanticOutputSchema(OverstatementResponse, context={"claims": claim_map}),
            GenerationOptions(temperature=0, max_tokens=2_048, allow_repair=True),
        )
        findings = tuple(
            AuditFinding(
                claim_ordinal=finding.claim_ordinal,
                finding_type=finding.finding_type,
                source_kind=FindingSource.MODEL_ASSISTED,
                severity=finding.severity,
                confidence=finding.confidence,
                explanation_message_key=f"finding.{finding.finding_type.value}",
                details={
                    "quotation": finding.quotation,
                    "explanation": finding.explanation,
                },
                prompt_version=OVERSTATEMENT_PROMPT_VERSION,
            )
            for finding in result.value.findings
        )
        return OverstatementBatch(findings=findings, metadata=result.metadata)


def _system_prompt(language: AuditLanguage) -> str:
    selected = "English" if language is AuditLanguage.ENGLISH else "Slovak"
    return (
        "Identify only explicit causal or certainty overstatement, ambiguous "
        "comparisons, and missing or shifting population, time, geography, or "
        "comparison scope. Reference only supplied claim ordinals and quote an "
        "exact substring from that claim. Use allowlisted schema values. Write each "
        f"concise explanation in {selected}. Return no hidden reasoning."
    )
