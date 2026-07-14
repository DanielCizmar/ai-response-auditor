from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from backend.auditor.domain.audits import AuditLanguage


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
