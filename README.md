# Evidence-Grounded Writing Auditor

A local-first web application for auditing English and Slovak academic writing. It identifies atomic claims, highlights writing risks, explains its findings, and suggests safer revisions without presenting itself as a scientific truth detector.

## Planned releases

- **MVP1:** paste text, run a local Ollama-powered audit, inspect highlighted claims, apply suggested changes, and re-audit.
- **MVP2:** audit PDF, DOCX, and LaTeX documents against a project-specific library of reference sources.

## Stack

Next.js, FastAPI, PostgreSQL with pgvector, Redis, Celery, Ollama, and Docker Compose. The complete application is designed to run locally without paid services; Vercel Hobby is used only for the portfolio frontend.

## Status

Foundation and MVP1 milestones M1.1–M1.6 are available: bilingual interface
catalogs, immutable audit schema, the local pasted-text editor, offset-safe sentence
splitting, a validated Ollama instruction boundary, and atomic claim extraction.
Audit API execution begins in later MVP1 milestones. See [docs/PLAN.md](docs/PLAN.md)
for the implementation plan and [AGENTS.md](AGENTS.md) for repository guidelines.

## Development

Prerequisites:

- Node.js 24+ with Corepack
- pnpm 10.15.1
- Python 3.12+
- uv 0.8+
- Docker with Compose

Install the locked workspaces:

```powershell
corepack enable
pnpm install --frozen-lockfile
uv sync --frozen
```

If Corepack cannot install global shims on a restricted machine, use `corepack pnpm` in place of `pnpm`.

Run the foundation smoke tests:

```powershell
pnpm test
```

The Next.js frontend foundation is available; product audit flows and the API/worker
entrypoints are delivered by their respective milestones.

### Frontend

Start the responsive editorial workbench:

```powershell
corepack pnpm dev:web
```

The shell checks `http://127.0.0.1:8000` by default. Set
`NEXT_PUBLIC_API_BASE_URL` when the local FastAPI origin differs. A disconnected
API produces a concrete setup and retry state rather than a simulated audit.
The API foundation is available; the frontend and worker runtimes are introduced by
their later milestones.

The editor accepts English or Slovak text, preserves a canonical plain-text copy,
and enforces the 10,000 Unicode-character MVP1 limit. The audit action remains
unavailable until the audit API and pipeline milestones are implemented.

### FastAPI

Start PostgreSQL, Redis, and Ollama, then run the local API:

```powershell
docker compose up --detach --wait postgres redis ollama
corepack pnpm api:dev
```

Process liveness is available at `GET /v1/health`; `GET /v1/readiness` distinguishes
database, Redis, configured-model, model-loading, and Ollama availability states.
API documentation is available at `/docs`.

### Local data infrastructure

Start PostgreSQL with pgvector and Redis, wait for both health checks, and run the connection smoke test:

```powershell
corepack pnpm infra:up
corepack pnpm test:infra
```

The services bind only to `127.0.0.1` and persist data in Docker named volumes. Local defaults are defined in `docker-compose.yml`; copy `.env.example` to `.env` only when overrides are needed.

Stop the services without deleting their data:

```powershell
corepack pnpm infra:down
```

Deleting the named volumes is intentionally not exposed as a package script because it destroys local data.

Apply or verify the audit schema after PostgreSQL is healthy:

```powershell
corepack pnpm db:migrate
corepack pnpm db:check
```

### Local Ollama

Start Ollama and pull the configured instruction and embedding models:

```powershell
corepack pnpm ollama:setup
corepack pnpm ollama:check
corepack pnpm test:ollama
```

CPU mode is the default. NVIDIA and AMD GPU overrides, hardware notes, readiness states, and model configuration are documented in [docs/development/ollama.md](docs/development/ollama.md).

## Privacy

There are no user accounts or hosted AI dependencies. Uploaded source files are processed temporarily and are not retained after extraction.
