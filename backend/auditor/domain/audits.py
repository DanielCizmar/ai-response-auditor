from __future__ import annotations

from enum import StrEnum


class AuditLanguage(StrEnum):
    ENGLISH = "en"
    SLOVAK = "sk"


class AuditSourceType(StrEnum):
    PASTED_TEXT = "pasted_text"


class AuditState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"


class ClaimStatus(StrEnum):
    LOW_RISK = "low_risk"
    REVIEW_RECOMMENDED = "review_recommended"
    EVIDENCE_NEEDED = "evidence_needed"
    INTERNALLY_INCONSISTENT = "internally_inconsistent"
    OVERSTATED = "overstated"
    NOT_VERIFIABLE = "not_verifiable"


class ClaimType(StrEnum):
    FACTUAL = "factual"
    CAUSAL = "causal"
    NUMERICAL = "numerical"
    COMPARATIVE = "comparative"
    DEFINITIONAL = "definitional"
    RECOMMENDATION = "recommendation"
    OTHER = "other"


class FindingSource(StrEnum):
    DETERMINISTIC = "deterministic"
    MODEL_ASSISTED = "model_assisted"


class FindingSeverity(StrEnum):
    INFO = "info"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class RevisionValidationStatus(StrEnum):
    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"
