from __future__ import annotations

from collections.abc import Iterable, Mapping
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.auditor.audits.claims import ExtractedClaim, Verifiability
from backend.auditor.checks.findings import AuditFinding, FindingType
from backend.auditor.domain.audits import ClaimStatus, FindingSeverity

SCORING_VERSION = "mvp1-risk-v1"


class RiskComponentType(StrEnum):
    EVIDENCE_NEED = "evidence_need_verifiability"
    OVERSTATEMENT = "causal_absolute_overstatement"
    NUMERICAL_INCONSISTENCY = "internal_numerical_inconsistency"
    SCOPE_AMBIGUITY = "scope_ambiguity"
    MODEL_UNCERTAINTY = "model_uncertainty"
    INTERACTING_FINDINGS = "interacting_findings"


class RiskBand(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class RiskComponentResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    component_type: RiskComponentType
    raw_value: dict[str, Any]
    points: int = Field(ge=0, le=25)
    explanation_message_key: str
    scoring_version: str = SCORING_VERSION

    @model_validator(mode="after")
    def points_match_raw_input(self) -> RiskComponentResult:
        expected = score_component(self.component_type, self.raw_value)
        if self.points != expected:
            raise ValueError("Risk component points do not match stored inputs.")
        return self


class RiskAssessment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    components: tuple[RiskComponentResult, ...]
    total: int = Field(ge=0, le=100)
    band: RiskBand
    status: ClaimStatus
    scoring_version: str = SCORING_VERSION

    @model_validator(mode="after")
    def total_matches_components(self) -> RiskAssessment:
        if self.total != min(100, sum(item.points for item in self.components)):
            raise ValueError("Risk total does not match component points.")
        if self.band is not risk_band(self.total):
            raise ValueError("Risk band does not match total.")
        return self


_SEVERITY_LEVEL = {
    FindingSeverity.INFO: 0,
    FindingSeverity.LOW: 1,
    FindingSeverity.MODERATE: 2,
    FindingSeverity.HIGH: 3,
    FindingSeverity.CRITICAL: 4,
}


def assess_claim(
    claim: ExtractedClaim,
    findings: Iterable[AuditFinding],
) -> RiskAssessment:
    selected = tuple(item for item in findings if item.claim_ordinal == claim.ordinal)
    overstatement = _max_level(
        selected,
        {
            FindingType.CAUSAL_OVERSTATEMENT,
            FindingType.CERTAINTY_OVERSTATEMENT,
            FindingType.COMPARATIVE_AMBIGUITY,
        },
    )
    numerical = _max_level(selected, {FindingType.NUMERICAL_INCONSISTENCY})
    scope = _max_level(selected, {FindingType.SCOPE_AMBIGUITY})
    active_families = sum(value > 0 for value in (overstatement, numerical, scope))
    components = (
        _component(
            RiskComponentType.EVIDENCE_NEED,
            {
                "verifiability": claim.verifiability.value,
                "claim_type": claim.primary_type.value,
            },
        ),
        _component(RiskComponentType.OVERSTATEMENT, {"severity_level": overstatement}),
        _component(
            RiskComponentType.NUMERICAL_INCONSISTENCY,
            {"severity_level": numerical},
        ),
        _component(RiskComponentType.SCOPE_AMBIGUITY, {"severity_level": scope}),
        _component(
            RiskComponentType.MODEL_UNCERTAINTY,
            {"confidence": claim.confidence},
        ),
        _component(
            RiskComponentType.INTERACTING_FINDINGS,
            {"active_families": active_families},
        ),
    )
    total = min(100, sum(item.points for item in components))
    return RiskAssessment(
        components=components,
        total=total,
        band=risk_band(total),
        status=_status(claim, numerical, overstatement, total),
    )


def reproduce_total(components: Iterable[RiskComponentResult]) -> int:
    selected = tuple(components)
    for component in selected:
        if component.scoring_version != SCORING_VERSION:
            raise ValueError("Unsupported scoring version.")
        if component.points != score_component(
            component.component_type, component.raw_value
        ):
            raise ValueError("Persisted component points do not match stored inputs.")
    return min(100, sum(component.points for component in selected))


def score_component(
    component_type: RiskComponentType,
    raw_value: Mapping[str, Any],
) -> int:
    if component_type is RiskComponentType.EVIDENCE_NEED:
        verifiability = raw_value.get("verifiability")
        claim_type = raw_value.get("claim_type")
        if verifiability == Verifiability.EXTERNALLY_VERIFIABLE.value:
            return 25 if claim_type in {"causal", "numerical", "comparative"} else 15
        if verifiability == Verifiability.NOT_VERIFIABLE.value:
            return 10
        return 5
    if component_type is RiskComponentType.OVERSTATEMENT:
        return (0, 5, 10, 15, 20)[_bounded_level(raw_value)]
    if component_type is RiskComponentType.NUMERICAL_INCONSISTENCY:
        return (0, 8, 15, 20, 25)[_bounded_level(raw_value)]
    if component_type is RiskComponentType.SCOPE_AMBIGUITY:
        return (0, 4, 8, 12, 15)[_bounded_level(raw_value)]
    if component_type is RiskComponentType.MODEL_UNCERTAINTY:
        confidence = float(raw_value.get("confidence", 0))
        if not 0 <= confidence <= 1:
            raise ValueError("Confidence must be between zero and one.")
        return round((1 - confidence) * 10)
    if component_type is RiskComponentType.INTERACTING_FINDINGS:
        return 5 if int(raw_value.get("active_families", 0)) >= 2 else 0
    raise ValueError("Unknown risk component type.")


def risk_band(total: int) -> RiskBand:
    if total < 20:
        return RiskBand.LOW
    if total < 40:
        return RiskBand.MODERATE
    if total < 70:
        return RiskBand.HIGH
    return RiskBand.CRITICAL


def _component(
    component_type: RiskComponentType, raw_value: dict[str, Any]
) -> RiskComponentResult:
    return RiskComponentResult(
        component_type=component_type,
        raw_value=raw_value,
        points=score_component(component_type, raw_value),
        explanation_message_key=f"risk.component.{component_type.value}",
    )


def _max_level(findings: tuple[AuditFinding, ...], types: set[FindingType]) -> int:
    return max(
        (
            _SEVERITY_LEVEL[item.severity]
            for item in findings
            if item.finding_type in types
        ),
        default=0,
    )


def _bounded_level(raw_value: Mapping[str, Any]) -> int:
    level = int(raw_value.get("severity_level", 0))
    if not 0 <= level <= 4:
        raise ValueError("Severity level must be between zero and four.")
    return level


def _status(
    claim: ExtractedClaim, numerical: int, overstatement: int, total: int
) -> ClaimStatus:
    if numerical:
        return ClaimStatus.INTERNALLY_INCONSISTENT
    if overstatement:
        return ClaimStatus.OVERSTATED
    if claim.verifiability is Verifiability.NOT_VERIFIABLE:
        return ClaimStatus.NOT_VERIFIABLE
    if claim.verifiability is Verifiability.EXTERNALLY_VERIFIABLE and total >= 20:
        return ClaimStatus.EVIDENCE_NEEDED
    if total >= 20:
        return ClaimStatus.REVIEW_RECOMMENDED
    return ClaimStatus.LOW_RISK
