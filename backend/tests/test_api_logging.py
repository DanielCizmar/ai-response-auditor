import json
import logging

from backend.auditor.logging import JsonFormatter, REDACTED, redact


def test_redaction_removes_private_fields_and_url_passwords() -> None:
    result = redact(
        {
            "draft": "private writing",
            "authorization": "Bearer private-token",
            "database_url": "postgresql://user:password@localhost/db",
            "redis_url": "redis://:private@localhost/0",
            "safe_count": 4,
        }
    )

    assert result == {
        "draft": REDACTED,
        "authorization": REDACTED,
        "database_url": "postgresql://user:[REDACTED]@localhost/db",
        "redis_url": "redis://:[REDACTED]@localhost/0",
        "safe_count": 4,
    }


def test_json_formatter_keeps_metadata_and_redacts_sensitive_extras() -> None:
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "completed", (), None)
    record.request_id = "request-1"
    record.prompt = "private prompt"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == "completed"
    assert payload["request_id"] == "request-1"
    assert payload["prompt"] == REDACTED
