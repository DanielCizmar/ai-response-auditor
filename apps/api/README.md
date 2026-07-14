# API entrypoint

The FastAPI entrypoint exposes metadata-only request logging, a shared error envelope,
and system endpoints:

- `GET /v1/health` checks process liveness without probing dependencies.
- `GET /v1/readiness` reports PostgreSQL/pgvector, Redis, Ollama, and the planned worker.
- `GET /openapi.json` and `GET /docs` expose the API contract and interactive documentation.

Run the API locally from the repository root:

```powershell
corepack pnpm api:dev
```

Regenerate the committed client contract after changing routes or schemas:

```powershell
corepack pnpm openapi:generate
```

The worker is reported as optional and `not_configured` until Celery orchestration is
introduced in milestone M2.4. Readiness is unavailable (`503`) when any currently
required dependency is unavailable or a configured Ollama model is absent/loading.

The provider-independent instruction model and atomic claim extractor are shared
backend application services. M1.11 composes them behind:

- `POST /v1/audits` with a required `Idempotency-Key` header.
- `GET /v1/audits/{audit_id}`.
- `POST /v1/audits/{audit_id}/re-audit` with a new idempotency key.

Each pipeline stage commits independently and appends a redacted event. A model
failure after usable deterministic work produces `partially_succeeded`; an essential
extraction failure produces `failed`, never a low-risk result.

After the local stack and configured model are ready, run the opt-in real pipeline
smoke with:

```powershell
$env:RUN_REAL_OLLAMA = "1"
uv run pytest backend/tests/test_real_audit_smoke.py -q
Remove-Item Env:RUN_REAL_OLLAMA
```
