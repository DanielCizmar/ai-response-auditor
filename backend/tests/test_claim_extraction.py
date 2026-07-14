from __future__ import annotations

import pytest

from backend.auditor.audits.claims import ModelClaimExtractor
from backend.auditor.audits.evaluation import (
    LabeledClaimSpan,
    claim_recall_by_language,
)
from backend.auditor.domain.audits import AuditLanguage
from backend.auditor.providers.fake import FakeInstructionModel
from backend.auditor.providers.instruction import StructuredOutputError
from backend.auditor.text.sentences import split_sentences


@pytest.mark.parametrize(
    ("language", "source", "exact_text", "claim_type"),
    [
        (
            AuditLanguage.ENGLISH,
            "The intervention increased retention by 12%.",
            "The intervention increased retention by 12%",
            "causal",
        ),
        (
            AuditLanguage.SLOVAK,
            "Intervencia zvýšila retenciu o 12 %.",
            "Intervencia zvýšila retenciu o 12 %",
            "causal",
        ),
    ],
)
def test_extracts_validated_bilingual_atomic_claims(
    language: AuditLanguage,
    source: str,
    exact_text: str,
    claim_type: str,
) -> None:
    start = source.index(exact_text)
    end = start + len(exact_text)
    quantity = "12%" if language is AuditLanguage.ENGLISH else "12 %"
    quantity_start = source.index(quantity)
    fake = FakeInstructionModel(
        [
            {
                "claims": [
                    {
                        "sentence_id": "s0001",
                        "exact_text": exact_text,
                        "normalized_text": exact_text,
                        "start_offset": start,
                        "end_offset": end,
                        "atomicity": "atomic",
                        "verifiability": "externally_verifiable",
                        "primary_type": claim_type,
                        "secondary_types": ["numerical"],
                        "confidence": 0.96,
                        "quantities": [
                            {
                                "text": quantity,
                                "start_offset": quantity_start,
                                "end_offset": quantity_start + len(quantity),
                            }
                        ],
                        "entities": [],
                    }
                ]
            }
        ]
    )
    extractor = ModelClaimExtractor(fake)

    batch = extractor.extract(split_sentences(source, language), source, language)

    assert len(batch.claims) == 1
    assert batch.claims[0].exact_text == exact_text
    assert (
        source[batch.claims[0].start_offset : batch.claims[0].end_offset] == exact_text
    )
    assert batch.metadata.model == "fake-instruction-v1"


def test_invalid_claim_span_is_repaired_once_then_fails_explicitly() -> None:
    source = "The sample included 40 participants."
    invalid = {
        "claims": [
            {
                "sentence_id": "s0001",
                "exact_text": "The sample included 41 participants",
                "normalized_text": "The sample included 41 participants",
                "start_offset": 0,
                "end_offset": 35,
                "atomicity": "atomic",
                "verifiability": "externally_verifiable",
                "primary_type": "numerical",
                "secondary_types": [],
                "confidence": 0.9,
                "quantities": [],
                "entities": [],
            }
        ]
    }
    fake = FakeInstructionModel([invalid, invalid])
    extractor = ModelClaimExtractor(fake)

    with pytest.raises(StructuredOutputError, match="remained invalid"):
        extractor.extract(
            split_sentences(source, AuditLanguage.ENGLISH),
            source,
            AuditLanguage.ENGLISH,
        )


def test_compound_claim_output_is_not_accepted() -> None:
    source = "The treatment reduced pain and improved sleep."
    candidate = {
        "claims": [
            {
                "sentence_id": "s0001",
                "exact_text": source[:-1],
                "normalized_text": source[:-1],
                "start_offset": 0,
                "end_offset": len(source) - 1,
                "atomicity": "compound",
                "verifiability": "externally_verifiable",
                "primary_type": "causal",
                "secondary_types": [],
                "confidence": 0.8,
                "quantities": [],
                "entities": [],
            }
        ]
    }
    extractor = ModelClaimExtractor(FakeInstructionModel([candidate, candidate]))

    with pytest.raises(StructuredOutputError):
        extractor.extract(
            split_sentences(source, AuditLanguage.ENGLISH),
            source,
            AuditLanguage.ENGLISH,
        )


def test_claim_recall_is_reported_separately_by_language() -> None:
    expected = (
        LabeledClaimSpan(AuditLanguage.ENGLISH, "en-1", 0, 10),
        LabeledClaimSpan(AuditLanguage.ENGLISH, "en-2", 2, 12),
        LabeledClaimSpan(AuditLanguage.SLOVAK, "sk-1", 0, 9),
    )
    predicted = (
        LabeledClaimSpan(AuditLanguage.ENGLISH, "en-1", 0, 10),
        LabeledClaimSpan(AuditLanguage.SLOVAK, "sk-1", 0, 9),
    )

    report = claim_recall_by_language(expected, predicted)

    assert report[AuditLanguage.ENGLISH].recall == 0.5
    assert report[AuditLanguage.SLOVAK].recall == 1.0
