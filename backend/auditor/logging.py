"""Metadata-only structured logging with defense-in-depth redaction."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any


REDACTED = "[REDACTED]"
SENSITIVE_KEY = re.compile(
    r"(authorization|cookie|password|secret|token|api[_-]?key|draft|prompt|passage|text|model_response)",
    re.IGNORECASE,
)
URL_CREDENTIALS = re.compile(
    r"(\b[a-z][a-z0-9+.-]*://[^/@\s]*:)([^@\s]+)(@)", re.I
)
BEARER_TOKEN = re.compile(r"(\bBearer\s+)[^\s]+", re.I)


def redact(value: Any, *, key: str | None = None) -> Any:
    """Redact known private fields recursively and credentials embedded in strings."""

    if key is not None and SENSITIVE_KEY.search(key):
        return REDACTED
    if isinstance(value, dict):
        return {
            str(item_key): redact(item, key=str(item_key))
            for item_key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        value = URL_CREDENTIALS.sub(r"\1[REDACTED]\3", value)
        return BEARER_TOKEN.sub(r"\1[REDACTED]", value)
    return value


class JsonFormatter(logging.Formatter):
    """Emit stable JSON records containing operational metadata only."""

    _standard_attributes = set(logging.makeLogRecord({}).__dict__) | {
        "message",
        "asctime",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": redact(record.getMessage()),
        }
        for key, value in record.__dict__.items():
            if key not in self._standard_attributes and not key.startswith("_"):
                payload[key] = redact(value, key=key)
        if record.exc_info:
            payload["exception_type"] = record.exc_info[0].__name__
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("auditor")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(level.upper())
    logger.propagate = False
