# Contributing

Thank you for contributing to the Evidence-Grounded Writing Auditor. Read [AGENTS.md](AGENTS.md) and [docs/PLAN.md](docs/PLAN.md) before starting work.

## Workflow

This repository uses GitHub Flow:

1. Start from an up-to-date `main` branch.
2. Create a short-lived branch using `foundation/`, `feature/`, `fix/`, or `docs/`.
3. Implement one milestone or focused change.
4. Run all checks relevant to the change.
5. Open a pull request and complete its checklist.
6. Address review and required-check failures.
7. Squash-merge after approval. Delete the branch after merging.

Keep `main` deployable. Do not push directly to it or mix unrelated work into one pull request.

## Commits and pull requests

Use short, imperative commit messages. Conventional Commit prefixes are recommended:

- `feat:` user-visible functionality
- `fix:` defect correction
- `docs:` documentation only
- `test:` test-only changes
- `refactor:` behavior-preserving code changes
- `build:` dependencies or build tooling
- `ci:` GitHub Actions and automation
- `chore:` repository maintenance

Pull requests must explain scope, tests, privacy/security effects, migrations, and local-model effects. Include before/after screenshots for frontend changes. Do not describe unfinished behavior as complete.

## Scope and architecture

Implement the small milestones in section 15 of `docs/PLAN.md`. Do not include later milestones opportunistically. Architectural changes require an ADR in `docs/adr/` and must preserve the local-first, no-paid-services, Ollama-only constraints unless the approved plan is explicitly revised.

Never commit drafts, source documents, extracted private content, model prompts/responses, model weights, database dumps, credentials, or populated environment files.

## Local validation

Install the locked JavaScript and Python workspaces:

```powershell
corepack enable
pnpm install --frozen-lockfile
uv sync --frozen
```

On a restricted machine where Corepack cannot create global shims, use `corepack pnpm` in place of `pnpm`.

Run the locked quality, contract, and test checks:

```powershell
corepack pnpm install --frozen-lockfile
uv sync --frozen --all-groups
corepack pnpm format:python:check
corepack pnpm lint:python
corepack pnpm typecheck:python
corepack pnpm lint:web
corepack pnpm typecheck:web
corepack pnpm test
corepack pnpm build:web
corepack pnpm openapi:check
corepack pnpm secret:scan
```

For changes to local data infrastructure, also run:

```powershell
corepack pnpm infra:up
corepack pnpm test:infra
```

For changes to the Ollama runtime or model setup, run the mocked tests and, when local resources permit, the real generation smoke test:

```powershell
corepack pnpm test:python
corepack pnpm ollama:setup
corepack pnpm test:ollama
```

GitHub Actions runs these required checks on pull requests and pushes to `main`:

- Python formatting, linting, typing, and pytest.
- TypeScript linting, type checking, unit tests, and a production build.
- OpenAPI contract freshness.
- PostgreSQL/pgvector and Redis Compose smoke testing.
- Secret scanning against a hashed baseline.
- An Alembic configuration gate. Until M1.2, it verifies that no partial migration
  scaffold exists; after M1.2 it runs `alembic upgrade head` against PostgreSQL.

Playwright and generated TypeScript client checks are added when those artifacts
exist. Do not label their absence as a passing product check.

Before opening a pull request now, at minimum run:

```powershell
git diff --check
git status --short
```

List checks not run and explain why in the pull request.

## Dependency updates

Dependabot monitors the root pnpm/Python manifests and GitHub Actions. Add Docker monitoring only after maintained Dockerfiles exist:

| Ecosystem | Status or enablement point | Expected directory |
|---|---|---|
| pnpm/npm | Enabled | `/` |
| pip/uv | Enabled | `/` |
| Docker | A maintained root or service Dockerfile exists | Its containing directory |

Dependency pull requests must pass the same required checks as other changes. Do not merge major model/runtime upgrades without reviewing compatibility and evaluation effects.

## Releases

Use annotated release tags after the corresponding acceptance criteria pass:

- `mvp1-alpha`
- `mvp1-beta`
- `mvp1`
- `mvp2-alpha`
- `mvp2-beta`
- `mvp2`

Do not reuse or move published release tags.

## Reporting security or privacy issues

Do not include private document content, prompts, credentials, or exploit payloads in a public issue. Contact the repository owner privately for sensitive reports. Non-sensitive defects can use the bug-report template.
