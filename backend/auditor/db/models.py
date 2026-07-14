from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.auditor.db.base import Base
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
from backend.auditor.domain.identifiers import uuid7


def enum_type(enum: type[Any], name: str) -> SAEnum:
    return SAEnum(
        enum,
        name=name,
        values_callable=lambda values: [value.value for value in values],
    )


class Audit(Base):
    __tablename__ = "audits"
    __table_args__ = (
        Index("ix_audits_input_hash", "input_hash"),
        Index("ix_audits_state", "state"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid7
    )
    source_type: Mapped[AuditSourceType] = mapped_column(
        enum_type(AuditSourceType, "audit_source_type"), nullable=False
    )
    language: Mapped[AuditLanguage] = mapped_column(
        enum_type(AuditLanguage, "audit_language"), nullable=False
    )
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[AuditState] = mapped_column(
        enum_type(AuditState, "audit_state"), nullable=False
    )
    pipeline_version: Mapped[str] = mapped_column(String(64), nullable=False)
    model_manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    scoring_version: Mapped[str] = mapped_column(String(64), nullable=False)
    normalization_version: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    safe_error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    claims: Mapped[list[Claim]] = relationship(
        back_populates="audit", cascade="all, delete-orphan"
    )
    events: Mapped[list[AuditEvent]] = relationship(
        back_populates="audit", cascade="all, delete-orphan"
    )


class Claim(Base):
    __tablename__ = "claims"
    __table_args__ = (
        UniqueConstraint("audit_id", "ordinal", name="uq_claims_audit_ordinal"),
        CheckConstraint("start_offset >= 0", name="ck_claims_start_nonnegative"),
        CheckConstraint("end_offset > start_offset", name="ck_claims_offset_order"),
        CheckConstraint(
            "extraction_confidence BETWEEN 0 AND 1", name="ck_claims_confidence"
        ),
        CheckConstraint("risk_score BETWEEN 0 AND 100", name="ck_claims_risk_score"),
        Index("ix_claims_audit_status", "audit_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid7
    )
    audit_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("audits.id", ondelete="CASCADE"),
        nullable=False,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    exact_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    primary_type: Mapped[ClaimType | None] = mapped_column(
        enum_type(ClaimType, "claim_type")
    )
    secondary_types: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), nullable=False, default=list
    )
    status: Mapped[ClaimStatus | None] = mapped_column(
        enum_type(ClaimStatus, "claim_status")
    )
    extraction_confidence: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), nullable=False
    )
    risk_score: Mapped[int | None] = mapped_column(SmallInteger)

    audit: Mapped[Audit] = relationship(back_populates="claims")
    findings: Mapped[list[ClaimFinding]] = relationship(cascade="all, delete-orphan")
    risk_components: Mapped[list[RiskComponent]] = relationship(
        cascade="all, delete-orphan"
    )
    suggested_revisions: Mapped[list[SuggestedRevision]] = relationship(
        cascade="all, delete-orphan"
    )


class ClaimFinding(Base):
    __tablename__ = "claim_findings"
    __table_args__ = (
        Index("ix_claim_findings_claim_type", "claim_id", "finding_type"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid7
    )
    claim_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("claims.id", ondelete="CASCADE"),
        nullable=False,
    )
    finding_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_kind: Mapped[FindingSource] = mapped_column(
        enum_type(FindingSource, "finding_source"), nullable=False
    )
    severity: Mapped[FindingSeverity] = mapped_column(
        enum_type(FindingSeverity, "finding_severity"), nullable=False
    )
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    rule_version: Mapped[str | None] = mapped_column(String(64))
    prompt_version: Mapped[str | None] = mapped_column(String(64))


class RiskComponent(Base):
    __tablename__ = "risk_components"
    __table_args__ = (
        CheckConstraint("points >= 0", name="ck_risk_components_points_nonnegative"),
        Index("ix_risk_components_claim", "claim_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid7
    )
    claim_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("claims.id", ondelete="CASCADE"),
        nullable=False,
    )
    component_type: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    points: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    explanation_message_key: Mapped[str] = mapped_column(String(128), nullable=False)
    scoring_version: Mapped[str] = mapped_column(String(64), nullable=False)


class SuggestedRevision(Base):
    __tablename__ = "suggested_revisions"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid7
    )
    claim_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("claims.id", ondelete="CASCADE"),
        nullable=False,
    )
    replacement_text: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[AuditLanguage] = mapped_column(
        enum_type(AuditLanguage, "audit_language"), nullable=False
    )
    model_version: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    validation_status: Mapped[RevisionValidationStatus] = mapped_column(
        enum_type(RevisionValidationStatus, "revision_validation_status"),
        nullable=False,
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        UniqueConstraint("audit_id", "sequence", name="uq_audit_events_audit_sequence"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid7
    )
    audit_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("audits.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    redacted_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    audit: Mapped[Audit] = relationship(back_populates="events")


Index("ix_audits_created_at_desc", Audit.created_at.desc())
Index("ix_claims_audit_risk", Claim.audit_id, Claim.risk_score.desc())
