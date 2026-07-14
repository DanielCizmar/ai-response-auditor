from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from backend.auditor.audits.claims import Atomicity, ExtractedClaim, Verifiability
from backend.auditor.audits.revisions import RevisionBatch, RevisionCandidate
from backend.auditor.checks.findings import AuditFinding, FindingType
from backend.auditor.db.models import Claim
from backend.auditor.db.repositories.review import ReviewRepository
from backend.auditor.domain.audits import (
    AuditLanguage,
    ClaimType,
    FindingSeverity,
    FindingSource,
)
from backend.auditor.domain.scoring import assess_claim
from backend.auditor.providers.instruction import GenerationMetadata


def _domain_claim() -> ExtractedClaim:
    text = "The treatment always improves recovery."
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


def test_review_repository_persists_versioned_artifacts() -> None:
    domain_claim = _domain_claim()
    record = Claim(
        id=uuid4(),
        audit_id=uuid4(),
        ordinal=0,
        exact_text=domain_claim.exact_text,
        normalized_text=domain_claim.normalized_text,
        start_offset=0,
        end_offset=len(domain_claim.exact_text),
        primary_type=ClaimType.CAUSAL,
        secondary_types=[],
        extraction_confidence=Decimal("0.9"),
    )
    record.risk_components = []
    finding = AuditFinding(
        claim_ordinal=0,
        finding_type=FindingType.CERTAINTY_OVERSTATEMENT,
        source_kind=FindingSource.MODEL_ASSISTED,
        severity=FindingSeverity.HIGH,
        confidence=0.9,
        explanation_message_key="finding.certainty_overstatement",
        details={"quotation": "always"},
        prompt_version="overstatement-check-v1",
    )
    assessment = assess_claim(domain_claim, (finding,))
    revision_batch = RevisionBatch(
        suggestions=(
            RevisionCandidate.model_validate(
                {
                    "claim_ordinal": 0,
                    "replacement_text": "The treatment may improve recovery.",
                    "rationale": "Qualifies certainty.",
                    "language": "en",
                },
                context={
                    "claims": {0: domain_claim},
                    "finding_ordinals": {0},
                    "language": AuditLanguage.ENGLISH,
                },
            ),
        ),
        metadata=GenerationMetadata(
            model="fake-instruction-v1",
            prompt_version="qualification-revision-v1",
            attempts=1,
            repaired=False,
        ),
    )
    session = MagicMock()
    repository = ReviewRepository()

    findings = repository.add_findings(session, (record,), (finding,))
    components = repository.add_assessment(session, record, assessment)
    revisions = repository.add_revisions(session, (record,), revision_batch)

    assert findings[0].prompt_version == "overstatement-check-v1"
    assert len(components) == 6
    assert {component.scoring_version for component in components} == {"mvp1-risk-v1"}
    assert record.risk_score == assessment.total
    assert record.status == assessment.status
    assert revisions[0].validation_status.value == "valid"
    assert session.flush.call_count == 3
