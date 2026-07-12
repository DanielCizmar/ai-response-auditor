# Evidence-Grounded Writing Auditor

A local-first web application for auditing English and Slovak academic writing. It identifies atomic claims, highlights writing risks, explains its findings, and suggests safer revisions without presenting itself as a scientific truth detector.

## Planned releases

- **MVP1:** paste text, run a local Ollama-powered audit, inspect highlighted claims, apply suggested changes, and re-audit.
- **MVP2:** audit PDF, DOCX, and LaTeX documents against a project-specific library of reference sources.

## Stack

Next.js, FastAPI, PostgreSQL with pgvector, Redis, Celery, Ollama, and Docker Compose. The complete application is designed to run locally without paid services; Vercel Hobby is used only for the portfolio frontend.

## Status

The project is currently in the planning and foundation stage. See [docs/PLAN.md](docs/PLAN.md) for the implementation plan and [AGENTS.md](AGENTS.md) for repository guidelines.

## Development

Prerequisites:

- Node.js 24+ with Corepack
- pnpm 10.15.1
- Python 3.12+
- uv 0.8+

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

Application services are intentionally not scaffolded yet. Their setup is delivered by later foundation milestones.

## Privacy

There are no user accounts or hosted AI dependencies. Uploaded source files are processed temporarily and are not retained after extraction.
