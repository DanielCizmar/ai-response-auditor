from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.auditor.domain.audits import FindingSeverity, FindingSource


class FindingType(StrEnum):
    NUMERICAL_INCONSISTENCY = "numerical_inconsistency"
    CAUSAL_OVERSTATEMENT = "causal_overstatement"
    CERTAINTY_OVERSTATEMENT = "certainty_overstatement"
    COMPARATIVE_AMBIGUITY = "comparative_ambiguity"
    SCOPE_AMBIGUITY = "scope_ambiguity"


class AuditFinding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    claim_ordinal: int = Field(ge=0)
    finding_type: FindingType
    source_kind: FindingSource
    severity: FindingSeverity
    confidence: float = Field(ge=0, le=1)
    explanation_message_key: str = Field(min_length=1, max_length=128)
    details: dict[str, Any]
    rule_version: str | None = Field(default=None, max_length=64)
    prompt_version: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def version_matches_source(self) -> AuditFinding:
        if self.source_kind is FindingSource.DETERMINISTIC:
            if not self.rule_version or self.prompt_version is not None:
                raise ValueError("Deterministic findings require only a rule version.")
        elif not self.prompt_version or self.rule_version is not None:
            raise ValueError("Model-assisted findings require only a prompt version.")
        return self
