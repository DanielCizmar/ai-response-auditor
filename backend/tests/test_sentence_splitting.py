from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from backend.auditor.domain.audits import AuditLanguage
from backend.auditor.text.sentences import (
    OFFSET_CONVENTION_VERSION,
    split_sentences,
)


@pytest.mark.parametrize(
    "case",
    json.loads(Path("fixtures/text/sentence_offsets.json").read_text(encoding="utf-8"))[
        "cases"
    ],
    ids=lambda case: str(case["id"]),
)
def test_bilingual_sentence_fixtures_round_trip_exact_substrings(
    case: dict[str, Any],
) -> None:
    source = str(case["text"])
    spans = split_sentences(source, AuditLanguage(str(case["language"])))

    assert [span.text for span in spans] == case["sentences"]
    assert [source[span.start_offset : span.end_offset] for span in spans] == case[
        "sentences"
    ]
    assert all(span.offset_convention == OFFSET_CONVENTION_VERSION for span in spans)


def test_empty_and_whitespace_only_text_have_no_sentences() -> None:
    assert split_sentences("", AuditLanguage.ENGLISH) == ()
    assert split_sentences(" \n\t", AuditLanguage.SLOVAK) == ()
