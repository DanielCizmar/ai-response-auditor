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
backend application services. They are not exposed as audit routes until M1.11.
