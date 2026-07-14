from __future__ import annotations

import re
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.auditor.domain.audits import AuditLanguage

OFFSET_CONVENTION_VERSION = "unicode-code-points-v1"
SENTENCE_SEGMENTER_VERSION = "sentence-segmenter-v1"

_LIST_PREFIX = re.compile(r"(?:[-*•]\s+|\d{1,4}[.)]\s+)")
_CLOSING_PUNCTUATION = frozenset("\"'’”)]}")
_COMMON_ABBREVIATIONS = frozenset(
    {
        "dr.",
        "mr.",
        "mrs.",
        "ms.",
        "prof.",
        "sr.",
        "jr.",
        "e.g.",
        "i.e.",
        "et al.",
    }
)
_SLOVAK_ABBREVIATIONS = frozenset(
    {
        "napr.",
        "t. j.",
        "t.j.",
        "tzv.",
        "resp.",
        "č.",
        "s.",
        "str.",
        "obr.",
    }
)


class SentenceSpan(BaseModel):
    """One exact sentence span using Unicode code-point offsets."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=r"^s\d{4}$")
    ordinal: int = Field(ge=0)
    text: str = Field(min_length=1)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    language: AuditLanguage
    offset_convention: str = OFFSET_CONVENTION_VERSION
    segmenter_version: str = SENTENCE_SEGMENTER_VERSION

    @model_validator(mode="after")
    def offset_order_is_valid(self) -> Self:
        if self.end_offset <= self.start_offset:
            raise ValueError("Sentence end offset must follow its start offset.")
        return self


def split_sentences(text: str, language: AuditLanguage) -> tuple[SentenceSpan, ...]:
    """Split canonical text without changing or normalizing source characters."""

    spans: list[tuple[int, int]] = []
    line_start = 0
    for raw_line in text.splitlines(keepends=True):
        line = raw_line.rstrip("\r\n")
        _split_line(text, line_start, line_start + len(line), language, spans)
        line_start += len(raw_line)
    if line_start < len(text) or (text and not text.splitlines(keepends=True)):
        _split_line(text, line_start, len(text), language, spans)

    sentences = tuple(
        SentenceSpan(
            id=f"s{ordinal + 1:04d}",
            ordinal=ordinal,
            text=text[start:end],
            start_offset=start,
            end_offset=end,
            language=language,
        )
        for ordinal, (start, end) in enumerate(spans)
    )
    _validate_round_trip(text, sentences)
    return sentences


def _split_line(
    source: str,
    line_start: int,
    line_end: int,
    language: AuditLanguage,
    spans: list[tuple[int, int]],
) -> None:
    start = _skip_whitespace(source, line_start, line_end)
    prefix = _LIST_PREFIX.match(source, start, line_end)
    if prefix is not None:
        start = prefix.end()
    start = _skip_whitespace(source, start, line_end)
    end = _trim_end(source, start, line_end)
    if start >= end:
        return

    sentence_start = start
    cursor = start
    while cursor < end:
        character = source[cursor]
        if character not in ".!?":
            cursor += 1
            continue
        if character == "." and _period_is_nonterminal(
            source, sentence_start, cursor, end, language
        ):
            cursor += 1
            continue

        boundary_end = cursor + 1
        while boundary_end < end and source[boundary_end] in ".!?":
            boundary_end += 1
        while boundary_end < end and source[boundary_end] in _CLOSING_PUNCTUATION:
            boundary_end += 1

        if boundary_end < end and not source[boundary_end].isspace():
            cursor = boundary_end
            continue

        candidate_start = _skip_whitespace(source, sentence_start, boundary_end)
        candidate_end = _trim_end(source, candidate_start, boundary_end)
        if candidate_start < candidate_end:
            spans.append((candidate_start, candidate_end))
        sentence_start = _skip_whitespace(source, boundary_end, end)
        cursor = sentence_start

    final_start = _skip_whitespace(source, sentence_start, end)
    final_end = _trim_end(source, final_start, end)
    if final_start < final_end:
        spans.append((final_start, final_end))


def _period_is_nonterminal(
    source: str,
    sentence_start: int,
    period: int,
    line_end: int,
    language: AuditLanguage,
) -> bool:
    if period > sentence_start and period + 1 < line_end:
        if source[period - 1].isdigit() and source[period + 1].isdigit():
            return True
        if source[period + 1] == ".":
            return True

    preceding_text = source[sentence_start : period + 1].casefold()
    abbreviations = _COMMON_ABBREVIATIONS
    if language is AuditLanguage.SLOVAK:
        abbreviations = abbreviations | _SLOVAK_ABBREVIATIONS
    if any(preceding_text.endswith(value) for value in abbreviations):
        return True

    token_start = period
    while token_start > sentence_start and not source[token_start - 1].isspace():
        token_start -= 1
    token = source[token_start : period + 1]
    if len(token) == 2 and token[0].isalpha():
        next_start = _skip_whitespace(source, period + 1, line_end)
        return next_start < line_end and source[next_start].isupper()
    return False


def _skip_whitespace(source: str, start: int, end: int) -> int:
    while start < end and source[start].isspace():
        start += 1
    return start


def _trim_end(source: str, start: int, end: int) -> int:
    while end > start and source[end - 1].isspace():
        end -= 1
    return end


def _validate_round_trip(source: str, sentences: tuple[SentenceSpan, ...]) -> None:
    previous_end = 0
    for sentence in sentences:
        if sentence.start_offset < previous_end:
            raise ValueError("Sentence spans overlap or are out of order.")
        if source[sentence.start_offset : sentence.end_offset] != sentence.text:
            raise ValueError(
                "Sentence offsets do not map to the exact source substring."
            )
        previous_end = sentence.end_offset
