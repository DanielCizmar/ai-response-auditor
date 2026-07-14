from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from backend.auditor.domain.audits import AuditLanguage


@dataclass(frozen=True)
class LabeledFinding:
    language: AuditLanguage
    case_id: str
    finding_type: str


@dataclass(frozen=True)
class LanguagePrecision:
    language: AuditLanguage
    matched: int
    predicted: int

    @property
    def precision(self) -> float:
        return 1.0 if self.predicted == 0 else self.matched / self.predicted


@dataclass(frozen=True)
class LabeledClaimSpan:
    language: AuditLanguage
    case_id: str
    start_offset: int
    end_offset: int


@dataclass(frozen=True)
class LanguageRecall:
    language: AuditLanguage
    matched: int
    expected: int

    @property
    def recall(self) -> float:
        return 1.0 if self.expected == 0 else self.matched / self.expected


def claim_recall_by_language(
    expected: tuple[LabeledClaimSpan, ...],
    predicted: tuple[LabeledClaimSpan, ...],
) -> dict[AuditLanguage, LanguageRecall]:
    expected_sets: dict[AuditLanguage, set[tuple[str, int, int]]] = defaultdict(set)
    predicted_sets: dict[AuditLanguage, set[tuple[str, int, int]]] = defaultdict(set)
    for span in expected:
        expected_sets[span.language].add(
            (span.case_id, span.start_offset, span.end_offset)
        )
    for span in predicted:
        predicted_sets[span.language].add(
            (span.case_id, span.start_offset, span.end_offset)
        )

    return {
        language: LanguageRecall(
            language=language,
            matched=len(expected_sets[language] & predicted_sets[language]),
            expected=len(expected_sets[language]),
        )
        for language in AuditLanguage
    }


def finding_precision_by_language(
    expected: tuple[LabeledFinding, ...],
    predicted: tuple[LabeledFinding, ...],
) -> dict[AuditLanguage, LanguagePrecision]:
    expected_sets: dict[AuditLanguage, set[tuple[str, str]]] = defaultdict(set)
    predicted_sets: dict[AuditLanguage, set[tuple[str, str]]] = defaultdict(set)
    for finding in expected:
        expected_sets[finding.language].add((finding.case_id, finding.finding_type))
    for finding in predicted:
        predicted_sets[finding.language].add((finding.case_id, finding.finding_type))
    return {
        language: LanguagePrecision(
            language=language,
            matched=len(expected_sets[language] & predicted_sets[language]),
            predicted=len(predicted_sets[language]),
        )
        for language in AuditLanguage
    }
