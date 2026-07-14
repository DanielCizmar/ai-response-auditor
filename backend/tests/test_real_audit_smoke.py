from __future__ import annotations

import os
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from apps.api.main import create_app
from backend.auditor.config import get_settings
from backend.auditor.db.models import Audit
from backend.auditor.db.session import build_session_factory


@pytest.mark.skipif(
    os.environ.get("RUN_REAL_OLLAMA") != "1",
    reason="Set RUN_REAL_OLLAMA=1 for the configured local-model smoke test",
)
def test_real_ollama_completes_a_persisted_api_audit() -> None:
    settings = get_settings()
    audit_id: UUID | None = None
    try:
        with TestClient(create_app(settings)) as client:
            response = client.post(
                "/v1/audits",
                headers={"Idempotency-Key": f"real-smoke-{uuid4()}"},
                json={
                    "text": (
                        "Regular physical activity may improve sleep quality in adults."
                    ),
                    "language": "en",
                },
            )
        assert response.status_code == 201
        payload = response.json()
        audit_id = UUID(payload["id"])
        assert payload["state"] in {
            "succeeded",
            "partially_succeeded",
        }, payload["safe_error_code"]
        assert payload["claims"]
        assert all(claim["risk_score"] is not None for claim in payload["claims"])
    finally:
        if audit_id is not None:
            engine, sessions = build_session_factory(settings)
            with sessions.begin() as session:
                session.execute(delete(Audit).where(Audit.id == audit_id))
            engine.dispose()
