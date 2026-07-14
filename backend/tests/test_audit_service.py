from __future__ import annotations

from uuid import uuid4

import psycopg
import pytest
from sqlalchemy import delete

from backend.auditor.audits.service import AuditApplication
from backend.auditor.config import get_settings
from backend.auditor.db.models import Audit
from backend.auditor.db.session import build_session_factory
from backend.auditor.domain.audits import AuditLanguage
from backend.auditor.providers.fake import FakeInstructionModel
from backend.auditor.providers.instruction import InstructionModelTimeout


@pytest.fixture
def sessions():
    settings = get_settings()
    try:
        connection = psycopg.connect(settings.psycopg_url, connect_timeout=3)
    except psycopg.OperationalError:
        pytest.skip("PostgreSQL is not available for audit pipeline integration tests")
    with connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'audits' AND column_name = 'idempotency_key'"
        )
        if cursor.fetchone() is None:
            pytest.skip("M1.11 migration has not been applied")
    engine, factory = build_session_factory(settings)
    yield factory
    engine.dispose()


def extraction_response(text: str) -> dict[str, object]:
    return {
        "claims": [
            {
                "sentence_id": "s0001",
                "exact_text": text,
                "normalized_text": text,
                "start_offset": 0,
                "end_offset": len(text),
                "atomicity": "atomic",
                "verifiability": "externally_verifiable",
                "primary_type": "causal",
                "secondary_types": [],
                "confidence": 0.95,
                "quantities": [],
                "entities": [],
            }
        ]
    }


def test_pipeline_persists_complete_result_and_replays_idempotently(sessions) -> None:
    text = "The treatment always improves recovery."
    model = FakeInstructionModel(
        [
            extraction_response(text),
            {
                "findings": [
                    {
                        "claim_ordinal": 0,
                        "finding_type": "certainty_overstatement",
                        "severity": "high",
                        "confidence": 0.94,
                        "quotation": "always",
                        "explanation": "The wording states an absolute effect.",
                    }
                ]
            },
            {
                "suggestions": [
                    {
                        "claim_ordinal": 0,
                        "replacement_text": "The treatment may improve recovery.",
                        "rationale": "Qualifies the certainty of the effect.",
                        "language": "en",
                    }
                ]
            },
        ]
    )
    application = AuditApplication(sessions, model)
    key = f"pipeline-{uuid4()}"

    result, replayed = application.create(text, AuditLanguage.ENGLISH, key)
    replay, was_replayed = application.create(text, AuditLanguage.ENGLISH, key)

    assert result.state == "succeeded"
    assert replayed is False
    assert was_replayed is True
    assert replay.id == result.id
    assert result.claims[0].exact_text == text
    assert result.claims[0].status == "overstated"
    assert result.claims[0].risk_score is not None
    assert len(result.claims[0].findings) == 1
    assert len(result.claims[0].risk_components) == 6
    assert len(result.claims[0].suggested_revisions) == 1
    assert all("text" not in event.redacted_payload for event in result.events)

    with sessions.begin() as session:
        session.execute(delete(Audit).where(Audit.id == result.id))


def test_model_assisted_timeout_returns_explicit_partial_audit(sessions) -> None:
    text = "The treatment improves recovery."
    application = AuditApplication(
        sessions,
        FakeInstructionModel(
            [extraction_response(text), InstructionModelTimeout("timed out")]
        ),
    )

    result, _ = application.create(text, AuditLanguage.ENGLISH, f"partial-{uuid4()}")

    assert result.state == "partially_succeeded"
    assert result.safe_error_code == "PARTIAL_MODEL_TIMEOUT"
    assert len(result.claims) == 1
    assert result.claims[0].risk_score is not None
    assert any(event.status == "failed" for event in result.events)

    with sessions.begin() as session:
        session.execute(delete(Audit).where(Audit.id == result.id))


def test_extraction_timeout_persists_failed_audit_without_low_risk_result(
    sessions,
) -> None:
    application = AuditApplication(
        sessions, FakeInstructionModel([InstructionModelTimeout("timed out")])
    )

    result, _ = application.create(
        "A claim.", AuditLanguage.ENGLISH, f"failed-{uuid4()}"
    )

    assert result.state == "failed"
    assert result.safe_error_code == "MODEL_TIMEOUT"
    assert result.claims == []

    with sessions.begin() as session:
        session.execute(delete(Audit).where(Audit.id == result.id))
