from __future__ import annotations

import pytest

from backend.auditor.audits.claims import Atomicity, ExtractedClaim, Verifiability
from backend.auditor.checks.findings import AuditFinding, FindingType
from backend.auditor.domain.audits import (
    ClaimStatus,
    ClaimType,
    FindingSeverity,
    FindingSource,
)
from backend.auditor.domain.scoring import (
    RiskComponentResult,
    assess_claim,
    reproduce_total,
)


def _claim() -> ExtractedClaim:
    return ExtractedClaim(
        ordinal=0,
        sentence_id="s0001",
        exact_text="Retention was 20%.",
        normalized_text="Retention was 20%.",
        start_offset=0,
        end_offset=18,
        atomicity=Atomicity.ATOMIC,
        verifiability=Verifiability.EXTERNALLY_VERIFIABLE,
        primary_type=ClaimType.NUMERICAL,
        secondary_types=(),
        confidence=0.8,
        quantities=(),
        entities=(),
    )


def _finding(
    finding_type: FindingType,
    source: FindingSource,
    severity: FindingSeverity,
) -> AuditFinding:
    return AuditFinding(
        claim_ordinal=0,
        finding_type=finding_type,
        source_kind=source,
        severity=severity,
        confidence=1,
        explanation_message_key=f"finding.{finding_type.value}",
        details={},
        rule_version="rule-v1" if source is FindingSource.DETERMINISTIC else None,
        prompt_version="prompt-v1" if source is FindingSource.MODEL_ASSISTED else None,
    )


def test_score_reproduces_exactly_from_stored_component_inputs() -> None:
    findings = (
        _finding(
            FindingType.NUMERICAL_INCONSISTENCY,
            FindingSource.DETERMINISTIC,
            FindingSeverity.CRITICAL,
        ),
        _finding(
            FindingType.CAUSAL_OVERSTATEMENT,
            FindingSource.MODEL_ASSISTED,
            FindingSeverity.HIGH,
        ),
    )

    assessment = assess_claim(_claim(), findings)

    assert assessment.status is ClaimStatus.INTERNALLY_INCONSISTENT
    assert reproduce_total(assessment.components) == assessment.total
    assert assessment.total == 72


def test_reproduction_rejects_points_that_do_not_match_stored_inputs() -> None:
    assessment = assess_claim(_claim(), ())
    original = assessment.components[0]
    corrupt = RiskComponentResult.model_construct(
        component_type=original.component_type,
        raw_value=original.raw_value,
        points=0,
        explanation_message_key=original.explanation_message_key,
        scoring_version=original.scoring_version,
    )

    with pytest.raises(ValueError, match="do not match"):
        reproduce_total((corrupt,))
