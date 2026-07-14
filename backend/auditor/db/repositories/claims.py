from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from backend.auditor.audits.claims import ClaimExtractionBatch
from backend.auditor.db.models import Audit, Claim


class InvalidClaimSpanError(ValueError):
    pass


class ClaimRepository:
    def add_extraction_batch(
        self,
        session: Session,
        audit: Audit,
        batch: ClaimExtractionBatch,
    ) -> tuple[Claim, ...]:
        if audit.language is not batch.language:
            raise InvalidClaimSpanError("Claim language does not match the audit.")

        records: list[Claim] = []
        for claim in batch.claims:
            if (
                audit.input_text[claim.start_offset : claim.end_offset]
                != claim.exact_text
            ):
                raise InvalidClaimSpanError(
                    "Claim offsets do not match the immutable audit input."
                )
            record = Claim(
                audit_id=audit.id,
                ordinal=claim.ordinal,
                exact_text=claim.exact_text,
                normalized_text=claim.normalized_text,
                start_offset=claim.start_offset,
                end_offset=claim.end_offset,
                primary_type=claim.primary_type,
                atomicity=claim.atomicity,
                verifiability=claim.verifiability,
                secondary_types=[value.value for value in claim.secondary_types],
                status=None,
                extraction_confidence=Decimal(str(claim.confidence)),
                risk_score=None,
            )
            session.add(record)
            records.append(record)
        session.flush()
        return tuple(records)
