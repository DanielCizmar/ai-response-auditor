from __future__ import annotations

import hashlib

import psycopg
import pytest

from backend.auditor.config import get_settings
from backend.auditor.domain.identifiers import uuid7


def test_uuid7_identifiers_have_expected_version_and_variant() -> None:
    identifier = uuid7()

    assert identifier.version == 7
    assert identifier.variant == "specified in RFC 4122"


@pytest.fixture
def database_connection() -> psycopg.Connection[tuple[object, ...]]:
    settings = get_settings()
    try:
        connection = psycopg.connect(
            settings.psycopg_url, autocommit=True, connect_timeout=3
        )
    except psycopg.OperationalError:
        pytest.skip("PostgreSQL is not available for migration integration tests")

    with connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass('public.audits')")
        if cursor.fetchone() == (None,):
            connection.close()
            pytest.skip("M1.2 migration has not been applied")

    yield connection
    connection.close()


def test_finalized_audit_input_and_results_are_immutable(
    database_connection: psycopg.Connection[tuple[object, ...]],
) -> None:
    audit_id = uuid7()
    claim_id = uuid7()
    source = "The measured increase was 12%."
    input_hash = hashlib.sha256(source.encode()).hexdigest()

    with database_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO audits (
                id, source_type, language, input_text, input_hash, state,
                pipeline_version, model_manifest, scoring_version,
                normalization_version
            ) VALUES (%s, 'pasted_text', 'en', %s, %s, 'running',
                      'pipeline-v1', '{}', 'score-v1', 'canonical-v1')
            """,
            (audit_id, source, input_hash),
        )
        cursor.execute(
            """
            INSERT INTO claims (
                id, audit_id, ordinal, exact_text, normalized_text,
                start_offset, end_offset, primary_type, secondary_types,
                status, extraction_confidence, risk_score
            ) VALUES (%s, %s, 0, %s, %s, 0, %s, 'numerical', '{}',
                      'review_recommended', 0.95, 25)
            """,
            (claim_id, audit_id, source, source, len(source)),
        )

        with pytest.raises(psycopg.errors.RaiseException, match="offsets do not match"):
            cursor.execute(
                """
                INSERT INTO claims (
                    id, audit_id, ordinal, exact_text, normalized_text,
                    start_offset, end_offset, primary_type, secondary_types,
                    status, extraction_confidence, risk_score
                ) VALUES (%s, %s, 1, 'wrong text', 'wrong text', 0, 10,
                          'factual', '{}', 'review_recommended', 0.9, 20)
                """,
                (uuid7(), audit_id),
            )

        with pytest.raises(psycopg.errors.RaiseException, match="input.*immutable"):
            cursor.execute(
                "UPDATE audits SET input_text = 'changed' WHERE id = %s", (audit_id,)
            )

        cursor.execute(
            "UPDATE audits SET state = 'succeeded', completed_at = now() WHERE id = %s",
            (audit_id,),
        )

        with pytest.raises(psycopg.errors.RaiseException, match="finalized audits"):
            cursor.execute(
                "UPDATE audits SET safe_error_code = 'CHANGED' WHERE id = %s",
                (audit_id,),
            )

        with pytest.raises(psycopg.errors.RaiseException, match="results.*immutable"):
            cursor.execute(
                "UPDATE claims SET risk_score = 1 WHERE id = %s", (claim_id,)
            )

        with pytest.raises(psycopg.errors.RaiseException, match="results.*immutable"):
            cursor.execute(
                """
                INSERT INTO claims (
                    id, audit_id, ordinal, exact_text, normalized_text,
                    start_offset, end_offset, primary_type, secondary_types,
                    status, extraction_confidence, risk_score
                ) VALUES (%s, %s, 1, %s, %s, 0, %s, 'factual', '{}',
                          'low_risk', 0.99, 0)
                """,
                (uuid7(), audit_id, source, source, len(source)),
            )

        cursor.execute("DELETE FROM audits WHERE id = %s", (audit_id,))


def test_audit_events_are_append_only(
    database_connection: psycopg.Connection[tuple[object, ...]],
) -> None:
    audit_id = uuid7()
    event_id = uuid7()
    source = "A short draft."
    input_hash = hashlib.sha256(source.encode()).hexdigest()

    with database_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO audits (
                id, source_type, language, input_text, input_hash, state,
                pipeline_version, model_manifest, scoring_version,
                normalization_version
            ) VALUES (%s, 'pasted_text', 'en', %s, %s, 'running',
                      'pipeline-v1', '{}', 'score-v1', 'canonical-v1')
            """,
            (audit_id, source, input_hash),
        )
        cursor.execute(
            """
            INSERT INTO audit_events (
                id, audit_id, sequence, event_type, stage, status, redacted_payload
            ) VALUES (%s, %s, 1, 'stage_started', 'validate', 'running', '{}')
            """,
            (event_id, audit_id),
        )

        with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
            cursor.execute(
                "UPDATE audit_events SET status = 'changed' WHERE id = %s", (event_id,)
            )

        cursor.execute(
            "UPDATE audits SET state = 'succeeded', completed_at = now() WHERE id = %s",
            (audit_id,),
        )
        with pytest.raises(psycopg.errors.RaiseException, match="results.*immutable"):
            cursor.execute(
                """
                INSERT INTO audit_events (
                    id, audit_id, sequence, event_type, stage, status, redacted_payload
                ) VALUES (%s, %s, 2, 'late_event', 'finalize', 'changed', '{}')
                """,
                (uuid7(), audit_id),
            )

        cursor.execute("DELETE FROM audits WHERE id = %s", (audit_id,))


def test_database_claim_offsets_count_unicode_code_points(
    database_connection: psycopg.Connection[tuple[object, ...]],
) -> None:
    audit_id = uuid7()
    source = "Údaj 😀 vzrástol."
    exact_text = "😀 vzrástol"
    start = source.index(exact_text)
    end = start + len(exact_text)

    with database_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO audits (
                id, source_type, language, input_text, input_hash, state,
                pipeline_version, model_manifest, scoring_version,
                normalization_version
            ) VALUES (%s, 'pasted_text', 'sk', %s, %s, 'running',
                      'pipeline-v1', '{}', 'score-v1', 'unicode-code-points-v1')
            """,
            (audit_id, source, hashlib.sha256(source.encode()).hexdigest()),
        )
        cursor.execute(
            """
            INSERT INTO claims (
                id, audit_id, ordinal, exact_text, normalized_text,
                start_offset, end_offset, primary_type, secondary_types,
                status, extraction_confidence, risk_score
            ) VALUES (%s, %s, 0, %s, %s, %s, %s, 'factual', '{}',
                      NULL, 0.9, NULL)
            """,
            (uuid7(), audit_id, exact_text, exact_text, start, end),
        )
        cursor.execute("DELETE FROM audits WHERE id = %s", (audit_id,))
