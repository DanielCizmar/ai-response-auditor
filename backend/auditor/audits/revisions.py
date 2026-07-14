from __future__ import annotations

import json
import re
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, model_validator

from backend.auditor.audits.claims import ExtractedClaim
from backend.auditor.checks.findings import AuditFinding
from backend.auditor.domain.audits import AuditLanguage
from backend.auditor.providers.instruction import (
    GenerationMetadata,
    GenerationOptions,
    InstructionModel,
    InstructionRequest,
    PydanticOutputSchema,
)

REVISION_PROMPT_VERSION = "qualification-revision-v1"
_NUMBER_PATTERN = re.compile(r"[-+]?\d+(?:[.,]\d+)?%?")
_ABSOLUTE = {
    AuditLanguage.ENGLISH: {"always", "never", "proves", "guarantees", "causes"},
    AuditLanguage.SLOVAK: {"vždy", "nikdy", "dokazuje", "zaručuje", "spôsobuje"},
}
_QUALIFIERS = {
    AuditLanguage.ENGLISH: {
        "may",
        "might",
        "suggests",
        "associated",
        "appears",
        "sample",
        "compared",
    },
    AuditLanguage.SLOVAK: {
        "môže",
        "mohol",
        "naznačuje",
        "súvisí",
        "zdá",
        "vzorke",
        "porovnaní",
    },
}
_LANGUAGE_WORDS = {
    AuditLanguage.ENGLISH: {"the", "this", "may", "with", "was", "is", "and", "in"},
    AuditLanguage.SLOVAK: {"tento", "táto", "môže", "bol", "bola", "je", "a", "v"},
}


class RevisionCandidate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    claim_ordinal: int = Field(ge=0)
    replacement_text: str = Field(min_length=1)
    rationale: str = Field(min_length=1, max_length=400)
    language: AuditLanguage

    @model_validator(mode="after")
    def validate_safe_revision(self, info: ValidationInfo) -> RevisionCandidate:
        context = info.context or {}
        claims = context.get("claims")
        selected_language = context.get("language")
        finding_ordinals = context.get("finding_ordinals")
        if not isinstance(claims, dict) or not isinstance(finding_ordinals, set):
            raise ValueError("Revision validation requires claim and finding context.")
        claim = claims.get(self.claim_ordinal)
        if not isinstance(claim, ExtractedClaim):
            raise ValueError("Revision references a claim outside the request.")
        if self.language is not selected_language:
            raise ValueError("Revision language does not match the selected language.")
        replacement = self.replacement_text.strip()
        if replacement == claim.exact_text.strip():
            raise ValueError("Revision must change the flagged claim.")
        _validate_language(replacement, self.language)
        _validate_no_meaning_expansion(claim.exact_text, replacement, self.language)
        if self.claim_ordinal in finding_ordinals:
            original_words = _words(claim.exact_text)
            revised_words = _words(replacement)
            softened = bool(original_words & _ABSOLUTE[self.language]) and not (
                original_words & _ABSOLUTE[self.language]
            ).issubset(revised_words)
            qualified = bool(revised_words & _QUALIFIERS[self.language])
            if not softened and not qualified:
                raise ValueError("Flagged revisions must qualify or soften the claim.")
        return self


class RevisionResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    suggestions: tuple[RevisionCandidate, ...]

    @model_validator(mode="after")
    def suggestions_are_unique(self) -> RevisionResponse:
        ordinals = [item.claim_ordinal for item in self.suggestions]
        if len(ordinals) != len(set(ordinals)):
            raise ValueError("Only one suggestion per claim is allowed.")
        return self


@dataclass(frozen=True)
class RevisionBatch:
    suggestions: tuple[RevisionCandidate, ...]
    metadata: GenerationMetadata


class ModelRevisionSuggester:
    def __init__(self, instruction_model: InstructionModel) -> None:
        self._instruction_model = instruction_model

    def suggest(
        self,
        claims: tuple[ExtractedClaim, ...],
        findings: tuple[AuditFinding, ...],
        language: AuditLanguage,
    ) -> RevisionBatch:
        claim_map = {claim.ordinal: claim for claim in claims}
        finding_ordinals = {finding.claim_ordinal for finding in findings}
        request = InstructionRequest(
            system_prompt=_system_prompt(language),
            user_prompt=json.dumps(
                {
                    "language": language.value,
                    "claims": [
                        {"ordinal": claim.ordinal, "text": claim.exact_text}
                        for claim in claims
                        if claim.ordinal in finding_ordinals
                    ],
                    "findings": [
                        {
                            "claim_ordinal": finding.claim_ordinal,
                            "type": finding.finding_type.value,
                            "severity": finding.severity.value,
                        }
                        for finding in findings
                    ],
                },
                ensure_ascii=False,
            ),
            prompt_version=REVISION_PROMPT_VERSION,
        )
        result = self._instruction_model.generate_structured(
            request,
            PydanticOutputSchema(
                RevisionResponse,
                context={
                    "claims": claim_map,
                    "finding_ordinals": finding_ordinals,
                    "language": language,
                },
            ),
            GenerationOptions(temperature=0, max_tokens=2_048, allow_repair=True),
        )
        return RevisionBatch(result.value.suggestions, result.metadata)


def _system_prompt(language: AuditLanguage) -> str:
    selected = "English" if language is AuditLanguage.ENGLISH else "Slovak"
    return (
        f"Suggest concise qualification-oriented revisions in {selected}. Preserve "
        "all stated quantities and named entities. Do not add facts, causes, certainty, "
        "populations, dates, or evidence. Reference only supplied claim ordinals. "
        "Return an empty suggestions list when no safe revision can be made. Provide "
        "only a concise rationale, never hidden reasoning."
    )


def _validate_no_meaning_expansion(
    original: str, replacement: str, language: AuditLanguage
) -> None:
    if _NUMBER_PATTERN.findall(original) != _NUMBER_PATTERN.findall(replacement):
        raise ValueError("Revision must preserve all quantities exactly.")
    original_absolute = _words(original) & _ABSOLUTE[language]
    added_absolute = (_words(replacement) & _ABSOLUTE[language]) - original_absolute
    if added_absolute:
        raise ValueError("Revision adds stronger absolute or causal language.")
    original_names = {
        word for word in re.findall(r"\b[^\W\d_]\w*", original) if word[0].isupper()
    }
    revised_names = {
        word for word in re.findall(r"\b[^\W\d_]\w*", replacement) if word[0].isupper()
    }
    if revised_names - original_names:
        raise ValueError("Revision adds a named entity not present in the claim.")


def _validate_language(text: str, language: AuditLanguage) -> None:
    words = _words(text)
    other = (
        AuditLanguage.SLOVAK
        if language is AuditLanguage.ENGLISH
        else AuditLanguage.ENGLISH
    )
    selected_hits = len(words & _LANGUAGE_WORDS[language])
    other_hits = len(words & _LANGUAGE_WORDS[other])
    if other_hits >= 2 and other_hits > selected_hits:
        raise ValueError("Revision appears to use the wrong language.")


def _words(text: str) -> set[str]:
    return {word.lower() for word in re.findall(r"[^\W\d_]+", text, re.UNICODE)}
