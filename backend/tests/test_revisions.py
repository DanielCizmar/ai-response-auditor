from __future__ import annotations

import pytest

from backend.auditor.audits.claims import Atomicity, ExtractedClaim, Verifiability
from backend.auditor.audits.revisions import ModelRevisionSuggester
from backend.auditor.checks.findings import AuditFinding, FindingType
from backend.auditor.domain.audits import (
    AuditLanguage,
    ClaimType,
    FindingSeverity,
    FindingSource,
)
from backend.auditor.providers.fake import FakeInstructionModel
from backend.auditor.providers.instruction import StructuredOutputError


def _claim(text: str) -> ExtractedClaim:
    return ExtractedClaim(
        ordinal=0,
        sentence_id="s0001",
        exact_text=text,
        normalized_text=text,
        start_offset=0,
        end_offset=len(text),
        atomicity=Atomicity.ATOMIC,
        verifiability=Verifiability.EXTERNALLY_VERIFIABLE,
        primary_type=ClaimType.CAUSAL,
        secondary_types=(),
        confidence=0.9,
        quantities=(),
        entities=(),
    )


def _finding() -> AuditFinding:
    return AuditFinding(
        claim_ordinal=0,
        finding_type=FindingType.CERTAINTY_OVERSTATEMENT,
        source_kind=FindingSource.MODEL_ASSISTED,
        severity=FindingSeverity.HIGH,
        confidence=0.9,
        explanation_message_key="finding.certainty_overstatement",
        details={},
        prompt_version="overstatement-check-v1",
    )


def _suggest(
    response: dict[str, object], text: str = "The treatment always improves recovery."
):
    return ModelRevisionSuggester(FakeInstructionModel([response, response])).suggest(
        (_claim(text),), (_finding(),), AuditLanguage.ENGLISH
    )


def test_accepts_same_language_qualification_oriented_revision() -> None:
    response = {
        "suggestions": [
            {
                "claim_ordinal": 0,
                "replacement_text": "The treatment may improve recovery.",
                "rationale": "Qualifies the certainty without adding a fact.",
                "language": "en",
            }
        ]
    }

    batch = _suggest(response)

    assert batch.suggestions[0].replacement_text == (
        "The treatment may improve recovery."
    )


@pytest.mark.parametrize(
    "response",
    [
        {
            "suggestions": [
                {
                    "claim_ordinal": 0,
                    "replacement_text": "Tento výsledok môže zlepšiť zotavenie.",
                    "rationale": "Nesprávny jazyk.",
                    "language": "en",
                }
            ]
        },
        {
            "suggestions": [
                {
                    "claim_ordinal": 0,
                    "replacement_text": "",
                    "rationale": "Empty output.",
                    "language": "en",
                }
            ]
        },
        {
            "suggestions": [
                {
                    "claim_ordinal": 0,
                    "replacement_text": (
                        "The treatment may improve recovery for 200 patients."
                    ),
                    "rationale": "Adds an unsupported population.",
                    "language": "en",
                }
            ]
        },
    ],
)
def test_rejects_wrong_language_empty_and_meaning_expanding_revisions(
    response: dict[str, object],
) -> None:
    with pytest.raises(StructuredOutputError, match="remained invalid"):
        _suggest(response)
