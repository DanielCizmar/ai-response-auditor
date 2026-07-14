from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from backend.auditor.audits.claims import (
    CLAIM_EXTRACTION_PROMPT_VERSION,
    Atomicity,
    ClaimExtractionBatch,
    ExtractedClaim,
    ModelClaimExtractor,
    Verifiability,
)
from backend.auditor.audits.overstatement import (
    OVERSTATEMENT_PROMPT_VERSION,
    ModelOverstatementChecker,
)
from backend.auditor.audits.revisions import (
    REVISION_PROMPT_VERSION,
    ModelRevisionSuggester,
    RevisionBatch,
)
from backend.auditor.checks.findings import AuditFinding
from backend.auditor.checks.numerical import (
    NUMERICAL_RULE_VERSION,
    find_numerical_conflicts,
)
from backend.auditor.db.models import Audit, AuditEvent, Claim
from backend.auditor.db.repositories.claims import ClaimRepository
from backend.auditor.db.repositories.review import ReviewRepository
from backend.auditor.db.session import SessionFactory
from backend.auditor.domain.audits import (
    AuditLanguage,
    AuditSourceType,
    AuditState,
    ClaimStatus,
    ClaimType,
    FindingSeverity,
    FindingSource,
    RevisionValidationStatus,
)
from backend.auditor.domain.scoring import SCORING_VERSION, assess_claim
from backend.auditor.providers.instruction import (
    InstructionModel,
    InstructionModelError,
    InstructionModelTimeout,
    InstructionModelUnavailable,
    StructuredOutputError,
)
from backend.auditor.text.sentences import (
    OFFSET_CONVENTION_VERSION,
    SENTENCE_SEGMENTER_VERSION,
    split_sentences,
)

AUDIT_PIPELINE_VERSION = "mvp1-audit-pipeline-v1"
MAX_AUDIT_CHARACTERS = 10_000


class AuditNotFoundError(LookupError):
    pass


class IdempotencyConflictError(ValueError):
    pass


class FindingResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    finding_type: str
    source_kind: FindingSource
    severity: FindingSeverity
    details: dict[str, Any]
    rule_version: str | None
    prompt_version: str | None


class RiskComponentResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    component_type: str
    raw_value: dict[str, Any]
    points: int
    explanation_message_key: str
    scoring_version: str


class RevisionResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    replacement_text: str
    rationale: str
    language: AuditLanguage
    model_version: str
    prompt_version: str
    validation_status: RevisionValidationStatus


class ClaimResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ordinal: int
    exact_text: str
    normalized_text: str
    start_offset: int
    end_offset: int
    atomicity: Atomicity
    verifiability: Verifiability
    primary_type: ClaimType | None
    secondary_types: list[str]
    status: ClaimStatus | None
    extraction_confidence: float
    risk_score: int | None
    findings: list[FindingResult]
    risk_components: list[RiskComponentResult]
    suggested_revisions: list[RevisionResult]


class EventResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sequence: int
    event_type: str
    stage: str
    status: str
    redacted_payload: dict[str, Any]
    created_at: datetime


class AuditResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    re_audit_of_id: UUID | None
    source_type: AuditSourceType
    language: AuditLanguage
    input_text: str
    state: AuditState
    pipeline_version: str
    model_manifest: dict[str, Any]
    scoring_version: str
    normalization_version: str
    started_at: datetime | None
    completed_at: datetime | None
    safe_error_code: str | None
    created_at: datetime
    claims: list[ClaimResult]
    events: list[EventResult]


class AuditService(Protocol):
    def create(
        self,
        text: str,
        language: AuditLanguage,
        idempotency_key: str,
        *,
        re_audit_of_id: UUID | None = None,
    ) -> tuple[AuditResult, bool]: ...

    def get(self, audit_id: UUID) -> AuditResult: ...


class AuditApplication:
    """Run the bounded MVP1 pipeline while committing every stage independently."""

    def __init__(
        self,
        sessions: SessionFactory,
        instruction_model: InstructionModel,
    ) -> None:
        self._sessions = sessions
        self._model = instruction_model
        self._claim_repository = ClaimRepository()
        self._review_repository = ReviewRepository()
        self._extractor = ModelClaimExtractor(instruction_model)
        self._overstatement = ModelOverstatementChecker(instruction_model)
        self._revisions = ModelRevisionSuggester(instruction_model)

    def create(
        self,
        text: str,
        language: AuditLanguage,
        idempotency_key: str,
        *,
        re_audit_of_id: UUID | None = None,
    ) -> tuple[AuditResult, bool]:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        input_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        existing_id: UUID | None = None
        try:
            with self._sessions.begin() as session:
                existing = session.scalar(
                    select(Audit).where(Audit.idempotency_key == idempotency_key)
                )
                if existing is not None:
                    self._validate_replay(
                        existing, input_hash, language, re_audit_of_id
                    )
                    existing_id = existing.id
                else:
                    if (
                        re_audit_of_id is not None
                        and session.get(Audit, re_audit_of_id) is None
                    ):
                        raise AuditNotFoundError("The source audit does not exist.")
                    audit = Audit(
                        idempotency_key=idempotency_key,
                        re_audit_of_id=re_audit_of_id,
                        source_type=AuditSourceType.PASTED_TEXT,
                        language=language,
                        input_text=text,
                        input_hash=input_hash,
                        state=AuditState.QUEUED,
                        pipeline_version=AUDIT_PIPELINE_VERSION,
                        model_manifest=self._model_manifest(),
                        scoring_version=SCORING_VERSION,
                        normalization_version=OFFSET_CONVENTION_VERSION,
                    )
                    session.add(audit)
                    session.flush()
                    self._add_event(
                        session, audit, "audit_created", "validate", "queued"
                    )
                    existing_id = audit.id
        except IntegrityError:
            # A concurrent request may win the unique-key insert after our lookup.
            with self._sessions() as session:
                existing = session.scalar(
                    select(Audit).where(Audit.idempotency_key == idempotency_key)
                )
                if existing is None:
                    raise
                self._validate_replay(existing, input_hash, language, re_audit_of_id)
                existing_id = existing.id

        if existing_id is None:
            raise AssertionError("Audit creation did not produce an identifier.")
        if existing is not None:
            return self.get(existing_id), True

        try:
            self._start(existing_id)
            sentences = split_sentences(text, language)
            self._record_stage(
                existing_id,
                "sentences_split",
                "split_sentences",
                "succeeded",
                {"sentence_count": len(sentences)},
            )
            extraction = self._extractor.extract(sentences, text, language)
            claims = extraction.claims
            self._persist_claims(existing_id, extraction)
        except InstructionModelError as error:
            self._fail(existing_id, "extract_claims", _safe_model_error(error))
            return self.get(existing_id), False
        except Exception:
            self._fail(existing_id, "pipeline", "PIPELINE_FAILED")
            raise

        try:
            partial_errors: list[str] = []
            deterministic_findings = find_numerical_conflicts(claims)
            model_findings: tuple[AuditFinding, ...] = ()
            try:
                model_findings = self._overstatement.check(claims, language).findings
            except InstructionModelError as error:
                code = _safe_model_error(error)
                partial_errors.append(code)
                self._record_stage(
                    existing_id,
                    "stage_failed",
                    "model_assisted_checks",
                    "failed",
                    {"error_code": code},
                )
            findings = (*deterministic_findings, *model_findings)
            self._persist_findings(existing_id, findings)
            self._persist_scores(existing_id, claims, findings)

            if findings:
                try:
                    revisions = self._revisions.suggest(claims, findings, language)
                    self._persist_revisions(existing_id, revisions)
                except InstructionModelError as error:
                    code = _safe_model_error(error)
                    partial_errors.append(code)
                    self._record_stage(
                        existing_id,
                        "stage_failed",
                        "suggest_revisions",
                        "failed",
                        {"error_code": code},
                    )
            self._finish(existing_id, partial_errors)
        except Exception:
            self._fail(existing_id, "pipeline", "PIPELINE_FAILED")
            raise
        return self.get(existing_id), False

    def get(self, audit_id: UUID) -> AuditResult:
        with self._sessions() as session:
            audit = session.scalar(
                select(Audit)
                .where(Audit.id == audit_id)
                .options(
                    selectinload(Audit.claims).selectinload(Claim.findings),
                    selectinload(Audit.claims).selectinload(Claim.risk_components),
                    selectinload(Audit.claims).selectinload(Claim.suggested_revisions),
                    selectinload(Audit.events),
                )
            )
            if audit is None:
                raise AuditNotFoundError("The audit does not exist.")
            audit.claims.sort(key=lambda claim: claim.ordinal)
            audit.events.sort(key=lambda event: event.sequence)
            return AuditResult.model_validate(audit)

    def _start(self, audit_id: UUID) -> None:
        with self._sessions.begin() as session:
            audit = self._require(session, audit_id)
            audit.state = AuditState.RUNNING
            audit.started_at = datetime.now(UTC)
            self._add_event(session, audit, "audit_started", "validate", "running")

    def _persist_claims(self, audit_id: UUID, batch: ClaimExtractionBatch) -> None:
        with self._sessions.begin() as session:
            audit = self._require(session, audit_id)
            self._claim_repository.add_extraction_batch(session, audit, batch)
            self._add_event(
                session,
                audit,
                "stage_completed",
                "extract_claims",
                "succeeded",
                {
                    "claim_count": len(batch.claims),
                    "model": batch.metadata.model,
                    "attempts": batch.metadata.attempts,
                    "repaired": batch.metadata.repaired,
                },
            )

    def _persist_findings(
        self, audit_id: UUID, findings: tuple[AuditFinding, ...]
    ) -> None:
        with self._sessions.begin() as session:
            audit = self._require(session, audit_id)
            claims = self._claims(session, audit_id)
            self._review_repository.add_findings(session, claims, findings)
            self._add_event(
                session,
                audit,
                "stage_completed",
                "writing_checks",
                "succeeded",
                {"finding_count": len(findings)},
            )

    def _persist_scores(
        self,
        audit_id: UUID,
        claims: tuple[ExtractedClaim, ...],
        findings: tuple[AuditFinding, ...],
    ) -> None:
        with self._sessions.begin() as session:
            audit = self._require(session, audit_id)
            records = {
                claim.ordinal: claim for claim in self._claims(session, audit_id)
            }
            for claim in claims:
                self._review_repository.add_assessment(
                    session, records[claim.ordinal], assess_claim(claim, findings)
                )
            self._add_event(
                session,
                audit,
                "stage_completed",
                "calculate_risk",
                "succeeded",
                {"scored_claim_count": len(claims)},
            )

    def _persist_revisions(self, audit_id: UUID, batch: RevisionBatch) -> None:
        with self._sessions.begin() as session:
            audit = self._require(session, audit_id)
            claims = self._claims(session, audit_id)
            self._review_repository.add_revisions(session, claims, batch)
            self._add_event(
                session,
                audit,
                "stage_completed",
                "suggest_revisions",
                "succeeded",
                {"suggestion_count": len(batch.suggestions)},
            )

    def _finish(self, audit_id: UUID, partial_errors: list[str]) -> None:
        with self._sessions.begin() as session:
            audit = self._require(session, audit_id)
            final_state = (
                AuditState.PARTIALLY_SUCCEEDED
                if partial_errors
                else AuditState.SUCCEEDED
            )
            self._add_event(
                session,
                audit,
                "audit_completed",
                "finalize",
                final_state.value,
                {"partial_failure_count": len(partial_errors)},
            )
            session.flush()
            audit.state = final_state
            audit.safe_error_code = (
                f"PARTIAL_{partial_errors[0]}" if partial_errors else None
            )
            audit.completed_at = datetime.now(UTC)

    def _fail(self, audit_id: UUID, stage: str, code: str) -> None:
        with self._sessions.begin() as session:
            audit = self._require(session, audit_id)
            self._add_event(
                session,
                audit,
                "stage_failed",
                stage,
                "failed",
                {"error_code": code},
            )
            session.flush()
            audit.state = AuditState.FAILED
            audit.safe_error_code = code
            audit.completed_at = datetime.now(UTC)

    def _record_stage(
        self,
        audit_id: UUID,
        event_type: str,
        stage: str,
        status: str,
        payload: dict[str, Any],
    ) -> None:
        with self._sessions.begin() as session:
            self._add_event(
                session,
                self._require(session, audit_id),
                event_type,
                stage,
                status,
                payload,
            )

    @staticmethod
    def _require(session: Session, audit_id: UUID) -> Audit:
        audit = session.get(Audit, audit_id)
        if audit is None:
            raise AuditNotFoundError("The audit does not exist.")
        return audit

    @staticmethod
    def _claims(session: Session, audit_id: UUID) -> tuple[Claim, ...]:
        return tuple(
            session.scalars(
                select(Claim).where(Claim.audit_id == audit_id).order_by(Claim.ordinal)
            )
        )

    @staticmethod
    def _add_event(
        session: Session,
        audit: Audit,
        event_type: str,
        stage: str,
        status: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        sequence = session.scalar(
            select(func.coalesce(func.max(AuditEvent.sequence), 0)).where(
                AuditEvent.audit_id == audit.id
            )
        )
        session.add(
            AuditEvent(
                audit_id=audit.id,
                sequence=int(sequence or 0) + 1,
                event_type=event_type,
                stage=stage,
                status=status,
                redacted_payload=payload or {},
            )
        )

    def _model_manifest(self) -> dict[str, Any]:
        return {
            "instruction_model": self._model.model_name,
            "claim_prompt": CLAIM_EXTRACTION_PROMPT_VERSION,
            "overstatement_prompt": OVERSTATEMENT_PROMPT_VERSION,
            "revision_prompt": REVISION_PROMPT_VERSION,
            "numerical_rules": NUMERICAL_RULE_VERSION,
            "sentence_segmenter": SENTENCE_SEGMENTER_VERSION,
        }

    @staticmethod
    def _validate_replay(
        audit: Audit,
        input_hash: str,
        language: AuditLanguage,
        re_audit_of_id: UUID | None,
    ) -> None:
        if (
            audit.input_hash != input_hash
            or audit.language is not language
            or audit.re_audit_of_id != re_audit_of_id
        ):
            raise IdempotencyConflictError(
                "The idempotency key was already used for another request."
            )


def _safe_model_error(error: InstructionModelError) -> str:
    if isinstance(error, InstructionModelTimeout):
        return "MODEL_TIMEOUT"
    if isinstance(error, InstructionModelUnavailable):
        return "MODEL_UNAVAILABLE"
    if isinstance(error, StructuredOutputError):
        return "INVALID_MODEL_OUTPUT"
    return "MODEL_FAILED"
