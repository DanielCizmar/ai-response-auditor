from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.auditor.audits.claims import Atomicity, ExtractedClaim, Verifiability
from backend.auditor.audits.evaluation import (
    LabeledFinding,
    finding_precision_by_language,
)
from backend.auditor.audits.overstatement import ModelOverstatementChecker
from backend.auditor.domain.audits import AuditLanguage, ClaimType
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
        primary_type=ClaimType.FACTUAL,
        secondary_types=(),
        confidence=0.9,
        quantities=(),
        entities=(),
    )


def test_bilingual_labeled_examples_meet_initial_precision() -> None:
    cases = json.loads(
        Path("fixtures/text/overstatement_checks.json").read_text(encoding="utf-8")
    )
    expected = []
    predicted = []
    for case in cases:
        language = AuditLanguage(case["language"])
        response = {
            "findings": [
                {
                    "claim_ordinal": 0,
                    "finding_type": case["finding_type"],
                    "severity": "high",
                    "confidence": 0.9,
                    "quotation": case["claim"],
                    "explanation": (
                        "The wording exceeds the stated scope."
                        if language is AuditLanguage.ENGLISH
                        else "Formulácia presahuje uvedený rozsah."
                    ),
                }
            ]
        }
        batch = ModelOverstatementChecker(FakeInstructionModel([response])).check(
            (_claim(case["claim"]),), language
        )
        expected.append(LabeledFinding(language, case["id"], case["finding_type"]))
        predicted.extend(
            LabeledFinding(language, case["id"], item.finding_type.value)
            for item in batch.findings
        )

    report = finding_precision_by_language(tuple(expected), tuple(predicted))

    assert report[AuditLanguage.ENGLISH].precision >= 0.9
    assert report[AuditLanguage.SLOVAK].precision >= 0.9


def test_finding_must_reference_an_exact_claim_quotation() -> None:
    claim = _claim("The program guarantees improvement.")
    invalid = {
        "findings": [
            {
                "claim_ordinal": 0,
                "finding_type": "certainty_overstatement",
                "severity": "high",
                "confidence": 0.9,
                "quotation": "invented quotation",
                "explanation": "The certainty is too strong.",
            }
        ]
    }

    with pytest.raises(StructuredOutputError, match="remained invalid"):
        ModelOverstatementChecker(FakeInstructionModel([invalid, invalid])).check(
            (claim,), AuditLanguage.ENGLISH
        )
