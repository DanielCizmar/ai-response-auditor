from __future__ import annotations

from sqlalchemy.orm import Session

from backend.auditor.audits.revisions import RevisionBatch
from backend.auditor.checks.findings import AuditFinding
from backend.auditor.db.models import (
    Claim,
    ClaimFinding,
    RiskComponent,
    SuggestedRevision,
)
from backend.auditor.domain.audits import FindingSource, RevisionValidationStatus
from backend.auditor.domain.scoring import RiskAssessment


class ReviewPersistenceError(ValueError):
    pass


class ReviewRepository:
    """Persist one stage at a time inside the caller's transaction."""

    def add_findings(
        self,
        session: Session,
        claims: tuple[Claim, ...],
        findings: tuple[AuditFinding, ...],
    ) -> tuple[ClaimFinding, ...]:
        claim_map = {claim.ordinal: claim for claim in claims}
        records: list[ClaimFinding] = []
        for finding in findings:
            claim = claim_map.get(finding.claim_ordinal)
            if claim is None:
                raise ReviewPersistenceError("Finding references an unknown claim.")
            if (
                finding.source_kind is FindingSource.DETERMINISTIC
                and finding.rule_version is None
            ):
                raise ReviewPersistenceError(
                    "Deterministic findings require a rule version."
                )
            record = ClaimFinding(
                claim_id=claim.id,
                finding_type=finding.finding_type.value,
                source_kind=finding.source_kind,
                severity=finding.severity,
                details={
                    **finding.details,
                    "confidence": finding.confidence,
                    "explanation_message_key": finding.explanation_message_key,
                },
                rule_version=finding.rule_version,
                prompt_version=finding.prompt_version,
            )
            session.add(record)
            records.append(record)
        session.flush()
        return tuple(records)

    def add_assessment(
        self,
        session: Session,
        claim: Claim,
        assessment: RiskAssessment,
    ) -> tuple[RiskComponent, ...]:
        if claim.risk_components:
            raise ReviewPersistenceError("A claim already has persisted scoring.")
        records = tuple(
            RiskComponent(
                claim_id=claim.id,
                component_type=component.component_type.value,
                raw_value=component.raw_value,
                points=component.points,
                explanation_message_key=component.explanation_message_key,
                scoring_version=component.scoring_version,
            )
            for component in assessment.components
        )
        session.add_all(records)
        claim.risk_score = assessment.total
        claim.status = assessment.status
        session.flush()
        return records

    def add_revisions(
        self,
        session: Session,
        claims: tuple[Claim, ...],
        batch: RevisionBatch,
    ) -> tuple[SuggestedRevision, ...]:
        claim_map = {claim.ordinal: claim for claim in claims}
        records: list[SuggestedRevision] = []
        for suggestion in batch.suggestions:
            claim = claim_map.get(suggestion.claim_ordinal)
            if claim is None:
                raise ReviewPersistenceError("Revision references an unknown claim.")
            record = SuggestedRevision(
                claim_id=claim.id,
                replacement_text=suggestion.replacement_text.strip(),
                rationale=suggestion.rationale.strip(),
                language=suggestion.language,
                model_version=batch.metadata.model,
                prompt_version=batch.metadata.prompt_version,
                validation_status=RevisionValidationStatus.VALID,
            )
            session.add(record)
            records.append(record)
        session.flush()
        return tuple(records)
