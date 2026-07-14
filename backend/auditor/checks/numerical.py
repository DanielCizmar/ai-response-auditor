from __future__ import annotations

import re
import unicodedata
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from backend.auditor.audits.claims import ExtractedClaim
from backend.auditor.checks.findings import AuditFinding, FindingType
from backend.auditor.domain.audits import FindingSeverity, FindingSource

NUMERICAL_RULE_VERSION = "numerical-rules-v1"


class QuantityKind(StrEnum):
    NUMBER = "number"
    PERCENTAGE = "percentage"
    UNIT = "unit"
    DATE = "date"
    RANGE = "range"
    SAMPLE_SIZE = "sample_size"


class ParsedQuantity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: QuantityKind
    raw_text: str
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    normalized_value: str
    unit: str | None = None
    subject_key: str


_NUMBER = r"[-+]?\d+(?:[.,]\d+)?"
_MONTHS = (
    r"january|february|march|april|may|june|july|august|september|october|"
    r"november|december|január|február|marec|apríl|máj|jún|júl|august|"
    r"september|október|november|december"
)
_PATTERNS: tuple[tuple[QuantityKind, re.Pattern[str]], ...] = (
    (
        QuantityKind.DATE,
        re.compile(
            rf"\b(?:\d{{4}}-\d{{1,2}}-\d{{1,2}}|\d{{1,2}}[./]\s*\d{{1,2}}[./]\s*\d{{4}}|\d{{1,2}}\.\s*(?:{_MONTHS})\s+\d{{4}}|(?:{_MONTHS})\s+\d{{1,2}},?\s+\d{{4}})\b",
            re.IGNORECASE,
        ),
    ),
    (
        QuantityKind.SAMPLE_SIZE,
        re.compile(
            rf"(?:\b[nN]\s*=\s*{_NUMBER}\b|\b{_NUMBER}\s+(?:participants?|subjects?|respondents?|patients?|účastníkov|účastníci|respondentov|pacientov|osôb)\b)",
            re.IGNORECASE,
        ),
    ),
    (
        QuantityKind.RANGE,
        re.compile(
            rf"(?:\b(?:between|from|od)\s+{_NUMBER}\s+(?:and|to|do|až)\s+{_NUMBER}(?:\s*%|\s*[A-Za-z°]+)?|\b{_NUMBER}\s*[–—-]\s*{_NUMBER}(?:\s*%|\s*[A-Za-z°]+)?)",
            re.IGNORECASE,
        ),
    ),
    (QuantityKind.PERCENTAGE, re.compile(rf"\b{_NUMBER}\s*%")),
    (
        QuantityKind.UNIT,
        re.compile(
            rf"\b{_NUMBER}\s*(?:kg|mg|g|km|cm|mm|m|°c|°f|hours?|hrs?|days?|weeks?|months?|years?|hodín|hodiny|dní|dni|týždňov|mesiacov|rokov)\b",
            re.IGNORECASE,
        ),
    ),
    (QuantityKind.NUMBER, re.compile(rf"(?<![\w.]){_NUMBER}(?![\w])")),
)
_STOP_WORDS = {
    "a",
    "an",
    "and",
    "at",
    "by",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "the",
    "to",
    "was",
    "were",
    "je",
    "aj",
    "na",
    "od",
    "o",
    "sa",
    "v",
    "vo",
    "z",
    "zo",
    "bol",
    "bola",
    "bolo",
    "boli",
    "result",
    "value",
    "study",
    "výsledok",
    "hodnota",
    "štúdia",
    "reached",
    "dosiahla",
    "dosiahol",
}
_MONTH_NUMBERS = {
    "january": 1,
    "január": 1,
    "february": 2,
    "február": 2,
    "march": 3,
    "marec": 3,
    "april": 4,
    "apríl": 4,
    "may": 5,
    "máj": 5,
    "june": 6,
    "jún": 6,
    "july": 7,
    "júl": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "október": 10,
    "november": 11,
    "december": 12,
}
_UNIT_ALIASES = {
    "hour": "h",
    "hours": "h",
    "hr": "h",
    "hrs": "h",
    "hodín": "h",
    "hodiny": "h",
    "day": "day",
    "days": "day",
    "dní": "day",
    "dni": "day",
    "week": "week",
    "weeks": "week",
    "týždňov": "week",
    "month": "month",
    "months": "month",
    "mesiacov": "month",
    "year": "year",
    "years": "year",
    "rokov": "year",
}


def parse_quantities(claim: ExtractedClaim) -> tuple[ParsedQuantity, ...]:
    occupied: list[tuple[int, int]] = []
    parsed: list[ParsedQuantity] = []
    for kind, pattern in _PATTERNS:
        for match in pattern.finditer(claim.exact_text):
            local_start, local_end = match.span()
            if any(local_start < end and local_end > start for start, end in occupied):
                continue
            raw = match.group()
            unit = _unit_for(kind, raw)
            parsed.append(
                ParsedQuantity(
                    kind=kind,
                    raw_text=raw,
                    start_offset=claim.start_offset + local_start,
                    end_offset=claim.start_offset + local_end,
                    normalized_value=_normalize_value(kind, raw),
                    unit=unit,
                    subject_key=_subject_key(claim.exact_text, local_start, local_end),
                )
            )
            occupied.append((local_start, local_end))
    return tuple(sorted(parsed, key=lambda value: value.start_offset))


def find_numerical_conflicts(
    claims: tuple[ExtractedClaim, ...],
) -> tuple[AuditFinding, ...]:
    indexed: dict[tuple[str, str], list[tuple[ExtractedClaim, ParsedQuantity]]] = {}
    for claim in claims:
        for quantity in parse_quantities(claim):
            key = (quantity.kind.value, quantity.unit or "")
            indexed.setdefault(key, []).append((claim, quantity))

    findings: list[AuditFinding] = []
    seen: set[tuple[int, int, str]] = set()
    for values in indexed.values():
        for index, (left_claim, left) in enumerate(values):
            for right_claim, right in values[index + 1 :]:
                if left_claim.ordinal == right_claim.ordinal:
                    continue
                if left.kind is not QuantityKind.SAMPLE_SIZE and not _subjects_overlap(
                    left.subject_key, right.subject_key
                ):
                    continue
                if left.normalized_value == right.normalized_value:
                    continue
                for claim, current, other_claim, other in (
                    (left_claim, left, right_claim, right),
                    (right_claim, right, left_claim, left),
                ):
                    identity = (claim.ordinal, other_claim.ordinal, current.kind.value)
                    if identity in seen:
                        continue
                    seen.add(identity)
                    findings.append(
                        AuditFinding(
                            claim_ordinal=claim.ordinal,
                            finding_type=FindingType.NUMERICAL_INCONSISTENCY,
                            source_kind=FindingSource.DETERMINISTIC,
                            severity=FindingSeverity.CRITICAL,
                            confidence=1,
                            explanation_message_key=(
                                "finding.numerical.internal_inconsistency"
                            ),
                            details={
                                "quantity_kind": current.kind.value,
                                "value": current.normalized_value,
                                "unit": current.unit,
                                "related_claim_ordinal": other_claim.ordinal,
                                "related_value": other.normalized_value,
                            },
                            rule_version=NUMERICAL_RULE_VERSION,
                        )
                    )
    return tuple(sorted(findings, key=lambda item: item.claim_ordinal))


def _normalize_number(raw: str) -> str:
    compact = raw.strip().replace(" ", "").replace(",", ".")
    value = Decimal(compact)
    return format(value.normalize(), "f")


def _normalize_value(kind: QuantityKind, raw: str) -> str:
    lowered = unicodedata.normalize("NFC", raw.strip().lower())
    numbers = re.findall(_NUMBER, lowered)
    normalized_numbers = [_normalize_number(number) for number in numbers]
    if kind is QuantityKind.DATE:
        return _normalize_date(lowered)
    if kind is QuantityKind.RANGE:
        return "..".join(normalized_numbers[:2])
    return normalized_numbers[-1] if normalized_numbers else lowered


def _unit_for(kind: QuantityKind, raw: str) -> str | None:
    if kind is QuantityKind.PERCENTAGE:
        return "%"
    if kind in {QuantityKind.UNIT, QuantityKind.RANGE}:
        match = re.search(r"(%|°[cf]|[A-Za-z]+)\s*$", raw, re.IGNORECASE)
        if not match:
            return None
        unit = match.group(1).lower()
        return _UNIT_ALIASES.get(unit, unit)
    if kind is QuantityKind.SAMPLE_SIZE:
        return "people"
    return None


def _subject_key(text: str, start: int, end: int) -> str:
    without_value = f"{text[:start]} {text[end:]}".lower()
    words = re.findall(r"[^\W\d_]+", without_value, re.UNICODE)
    meaningful = sorted({word for word in words if word not in _STOP_WORDS})
    return " ".join(meaningful)


def _subjects_overlap(left: str, right: str) -> bool:
    return bool(set(left.split()) & set(right.split()))


def _normalize_date(raw: str) -> str:
    iso = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", raw)
    if iso:
        year, month, day = (int(value) for value in iso.groups())
        return f"{year:04d}-{month:02d}-{day:02d}"
    numeric = re.fullmatch(r"(\d{1,2})[./]\s*(\d{1,2})[./]\s*(\d{4})", raw)
    if numeric:
        day, month, year = (int(value) for value in numeric.groups())
        return f"{year:04d}-{month:02d}-{day:02d}"
    values = re.findall(r"[^\W\d_]+|\d+", raw, re.UNICODE)
    month_index = next(
        (index for index, value in enumerate(values) if value in _MONTH_NUMBERS),
        None,
    )
    if month_index is None:
        return re.sub(r"\s+", "", raw)
    numbers = [int(value) for value in values if value.isdigit()]
    day, year = numbers[0], numbers[-1]
    return f"{year:04d}-{_MONTH_NUMBERS[values[month_index]]:02d}-{day:02d}"
