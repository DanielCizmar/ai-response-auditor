from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.auditor.audits.claims import Atomicity, ExtractedClaim, Verifiability
from backend.auditor.checks.numerical import (
    QuantityKind,
    find_numerical_conflicts,
    parse_quantities,
)
from backend.auditor.domain.audits import ClaimType


def _claim(text: str, ordinal: int = 0, start: int = 0) -> ExtractedClaim:
    return ExtractedClaim(
        ordinal=ordinal,
        sentence_id=f"s{ordinal + 1:04d}",
        exact_text=text,
        normalized_text=text,
        start_offset=start,
        end_offset=start + len(text),
        atomicity=Atomicity.ATOMIC,
        verifiability=Verifiability.EXTERNALLY_VERIFIABLE,
        primary_type=ClaimType.NUMERICAL,
        secondary_types=(),
        confidence=0.95,
        quantities=(),
        entities=(),
    )


@pytest.mark.parametrize(
    ("text", "kind", "normalized"),
    [
        ("The result was 12.5%.", QuantityKind.PERCENTAGE, "12.5"),
        ("The package weighed 20 kg.", QuantityKind.UNIT, "20"),
        ("The interval was 10–12 mg.", QuantityKind.RANGE, "10..12"),
        ("The study began 2026-07-14.", QuantityKind.DATE, "2026-07-14"),
        ("The sample had n = 40.", QuantityKind.SAMPLE_SIZE, "40"),
        ("Hodnota bola 42.", QuantityKind.NUMBER, "42"),
    ],
)
def test_parses_supported_quantity_patterns(
    text: str, kind: QuantityKind, normalized: str
) -> None:
    quantities = parse_quantities(_claim(text))

    assert len(quantities) == 1
    assert quantities[0].kind is kind
    assert quantities[0].normalized_value == normalized
    assert text[quantities[0].start_offset : quantities[0].end_offset] == (
        quantities[0].raw_text
    )


def test_bilingual_numerical_conflict_fixtures_are_deterministic() -> None:
    fixture_path = Path("fixtures/text/numerical_checks.json")
    cases = json.loads(fixture_path.read_text(encoding="utf-8"))

    for case in cases:
        offset = 0
        claims = []
        for ordinal, text in enumerate(case["claims"]):
            claims.append(_claim(text, ordinal, offset))
            offset += len(text) + 1

        findings = find_numerical_conflicts(tuple(claims))

        assert len(findings) == case["expected_findings"], case["id"]
        assert {item.details["quantity_kind"] for item in findings} == {
            case["expected_kind"]
        }
        assert all(item.confidence == 1 for item in findings)


def test_different_subjects_are_not_reported_as_conflicting() -> None:
    claims = (
        _claim("Retention was 20%.", 0),
        _claim("Attendance was 30%.", 1, 20),
    )

    assert find_numerical_conflicts(claims) == ()


def test_conflicts_follow_a_subject_across_wording_changes() -> None:
    claims = (
        _claim("Retention reached 20%.", 0),
        _claim("Retention was 30%.", 1, 23),
    )

    assert len(find_numerical_conflicts(claims)) == 2


def test_equivalent_date_formats_do_not_conflict() -> None:
    claims = (
        _claim("Launch date was 2026-07-14.", 0),
        _claim("Launch date was 14.7.2026.", 1, 29),
    )

    assert find_numerical_conflicts(claims) == ()
