# AGENTS.md

## Purpose and source of truth

This repository contains the **Evidence-Grounded Writing Auditor**, a local-first application for reviewing English and Slovak writing.

Before changing code, read in this order:

1. This file.
2. `docs/PLAN.md`, which defines the approved scope, architecture, milestones, and delivery order.
3. Relevant ADRs in `docs/adr/`.
4. Any more specific `AGENTS.md` in the directory being edited.
5. Relevant package-level README files.

If a request conflicts with `docs/PLAN.md`, identify the conflict before implementing it. Do not silently weaken security, privacy, provenance, or product-truthfulness constraints.

## Product releases

### MVP1: bilingual pasted-text audit

MVP1 audits English or Slovak text pasted into the browser. It extracts and classifies atomic claims, runs deterministic and model-assisted writing checks, calculates explainable risk, highlights claims, suggests safer revisions, supports re-auditing, and preserves local audit history.

MVP1 has no evidence corpus. It must not claim that text is scientifically supported, contradicted, or unsupported by research.

Allowed MVP1 statuses:

- `low_risk`
- `review_recommended`
- `evidence_needed`
- `internally_inconsistent`
- `overstated`
- `not_verifiable`

### MVP2: file and evidence audit

MVP2 adds two separate workflows:

- `audit_target`: PDF, DOCX, or LaTeX writing being audited.
- `reference_source`: papers or documentation used as the project's evidence corpus.

Never treat an audit target as evidence for itself implicitly.

Allowed evidence verdicts:

- `supported`
- `partially_supported`
- `contradicted`
- `unsupported`
- `related_but_insufficient`

When no adequate evidence is found, the English interface must use exactly:

> This claim is not supported by the papers currently included in this project.

Persist a language-independent message key and render a reviewed Slovak translation from the locale catalog.

The application is an evidence-alignment and writing-review tool. Never describe it as a scientific truth detector.

## Non-negotiable architecture

- There is no registration, login, authentication, user table, or multi-user functionality.
- The application is a single-installation, single-workspace tool.
- The complete application must build and run without paid services.
- Full functionality runs locally through Docker Compose.
- GitHub is the source of truth for version control and CI.
- Vercel Hobby hosts the portfolio frontend and preview deployments only.
- The Vercel build must support fixture/demo and disconnected-backend states.
- Never imply that Vercel can directly access a private local Ollama instance.
- Ollama is the only required model runtime. Never add a silent hosted-model fallback.
- Model names are configuration, not domain constants.
- Use a modular monolith with explicit, testable Python pipeline stages.
- Do not introduce microservices or an agent framework without an approved ADR and demonstrated need.
- PostgreSQL is authoritative. Redis is transient coordination infrastructure only.
- Uploaded PDF, DOCX, and LaTeX originals are temporary and must be deleted after extraction, terminal failure, or cancellation.
- Extracted text, provenance, embeddings, audits, and generated report metadata may persist locally.

Approved stack:

- Next.js, React, TypeScript, Tailwind CSS, shadcn/ui, TipTap, PDF.js, and TanStack Query.
- Python 3.12+, FastAPI, Pydantic, SQLAlchemy 2, and Alembic.
- PostgreSQL, pgvector, PostgreSQL full-text search, Redis, and Celery.
- PyMuPDF for machine-readable PDF extraction.
- Ollama for local instruction and embedding models.

## Repository boundaries

Follow the planned monorepo layout:

```text
apps/web              Next.js and Vercel application
apps/api              FastAPI entrypoint
apps/worker           Celery entrypoint
backend/auditor       Shared Python domain and application package
packages/ui           Shared UI components and design tokens
packages/api-client   Generated TypeScript API client
packages/i18n         English and Slovak catalogs
migrations            Alembic revisions
evals                 Synthetic datasets and evaluation runners
fixtures              Text and document fixtures
infra                 Compose, Docker, and Ollama configuration
docs/adr               Architecture decision records
```

Do not duplicate backend domain logic between API and worker entrypoints. Business logic must not depend directly on FastAPI route objects, Celery task objects, React components, Redis state, or raw Ollama response formats.

## Development workflow

- Work in the small milestones defined in section 15 of `docs/PLAN.md`.
- Implement only the milestone requested by the user.
- Do not opportunistically include later milestones.
- Confirm prerequisite milestones exist before implementing dependent work.
- Keep each pull request focused and independently reviewable.
- Use short-lived `foundation/*`, `feature/*`, `fix/*`, or `docs/*` branches.
- Preserve unrelated changes and untracked user files.
- Use squash merging through pull requests.
- Keep `main` deployable.
- Use Alembic for all schema changes.
- Update OpenAPI and the generated TypeScript client together when contracts change.
- Create or supersede an ADR when changing an approved architectural decision.
- Never delete historical ADRs.

Before editing:

1. Read the milestone's goal, deliverables, tests, completion criteria, and dependencies.
2. Inspect the repository and Git status.
3. Read all applicable instructions.
4. Identify existing user changes and avoid overwriting them.
5. Inspect the relevant implementation and tests.

After editing:

1. Run checks proportional to the change.
2. Inspect the diff for accidental scope expansion or private data.
3. Report files changed, exact validation commands/results, skipped tests, preserved changes, remaining setup, and known limitations.
4. Do not describe unimplemented behavior as complete.

## AI and deterministic logic

Keep probabilistic judgments separate from deterministic logic.

Models may:

- Extract and classify atomic claims.
- Produce bounded model-assisted writing findings.
- Verify supplied claim–evidence relationships.
- Produce concise evidence-linked explanations.
- Suggest revisions.

Deterministic Python must handle supported patterns for:

- Numbers and numeric ranges.
- Percentages.
- Units.
- Dates.
- Sample sizes.
- Explicit internal inconsistencies.
- Final risk-score calculation.

An LLM never invents the final risk score. Calculate it from persisted, versioned components. A model result must not hide or overwrite a conflicting deterministic finding.

Use stable internal interfaces such as:

```text
InstructionModel
EmbeddingModel
ClaimExtractor
EvidenceReranker
ClaimEvidenceVerifier
RevisionSuggester
```

Ollama is the MVP implementation behind these interfaces. Tests and ordinary CI use deterministic fake adapters.

Every model output must pass a Pydantic schema. Validate:

- Allowlisted enums and required fields.
- Claim offsets against exact source substrings.
- Referenced claim and evidence IDs against IDs supplied to the model.
- Evidence quotations as substrings of supplied passages.
- Suggested-revision language.

Permit at most one structured-output repair attempt. Continued invalid output becomes an explicit partial or failed stage, never a low-risk result. Do not request or persist hidden chain-of-thought; retain concise validated explanations only.

Readiness must distinguish Ollama unavailable, configured model missing, model loading, and ready. Do not start a real audit unless required models are ready.

## Data, provenance, and reliability

- Audits are immutable. Re-auditing creates a new audit.
- Freeze target content and selected reference processing versions for an evidence audit.
- Preserve provenance from source offsets through claims, candidates, verifier results, risk components, and revisions.
- Record pipeline, prompt, instruction model, embedding model, retrieval, deterministic-check, and scoring versions.
- Use explicit states such as `queued`, `running`, `succeeded`, `partially_succeeded`, `failed`, `cancel_requested`, and `cancelled`.
- Each pipeline stage persists outputs in a database transaction and emits an audit event.
- Jobs must be idempotent and safe under duplicate Celery delivery.
- Workers check cooperative cancellation before model calls and between batches.
- Empty retrieval is a valid outcome and never means a claim is false.
- Do not put full drafts, passages, prompts, or model responses in logs or error payloads.

Use one documented Unicode offset convention across Python and TypeScript. Test Slovak diacritics, emoji, combining characters, paragraphs, lists, and hard breaks.

For MVP2 retrieval:

- Every document, passage, audit, and claim belongs to a project.
- Every retrieval repository method requires `project_id`.
- Start retrieval SQL from the audit's frozen selected reference documents.
- Never perform global vector search and filter in application code afterward.
- Include project ID, corpus hash, query hash, and model versions in cache keys.
- Maintain adversarial tests proving that one project cannot retrieve another project's passages.

Project separation is a correctness boundary, not authentication or hostile multi-tenant security.

## Document-processing safety

- Stream uploads; do not load complete files into memory.
- Generate temporary paths. User filenames are display metadata only.
- Validate file signatures independently of filename extensions and browser MIME values.
- Enforce upload bytes, pages, extracted words, archive entries, expanded size, and decompression-ratio limits.
- Run PyMuPDF in an isolated and resource-limited worker where practical.
- Reject encrypted, malformed, or non-machine-readable PDFs. OCR is out of scope.
- Defend DOCX processing against ZIP traversal and decompression bombs.
- Parse LaTeX text only. Never compile it or execute TeX/shell commands.
- Initially reject LaTeX archives, external includes, and generated-file dependencies.
- Delete originals in success, terminal failure, and cancellation paths.
- Maintain an idempotent orphan-cleanup task and cleanup tests.

Because PDFs are not retained, PDF.js may display the browser's session-local `File`. After reload, require the user to reselect the original and verify its SHA-256 before enabling original-page highlighting.

## Frontend and content direction

The UI is a bilingual editorial evidence workbench, not a generic dashboard. The audited document is primary; charts and metric cards are secondary.

Use the design direction in section 12 of `docs/PLAN.md`:

- Source Serif 4 for audited prose.
- Source Sans 3 for interface text.
- IBM Plex Mono for scores, quantities, IDs, and coordinates.
- The approved ink, mineral, cool-paper, and semantic status palette.

The signature interaction is a provenance thread connecting the selected claim, explanation, and—during MVP2—the evidence passage and source location.

- Never rely on color alone. Pair color with underline style, label, and active state.
- Support keyboard navigation, visible focus, screen readers, reduced motion, responsive layouts, and mobile claim inspection.
- Use direct action labels such as **Audit text**, **Audit a document**, **Add a reference source**, **Apply suggestion**, and **Retry processing**.
- Keep audit-target and reference-source upload actions visually and verbally separate.
- Give empty, failed, missing-model, and disconnected states a concrete next action.

Maintain `en` and `sk` catalogs. Persist language-independent enums/message keys. Ask Ollama to analyze and revise in the selected language. Switching interface language must not rerun an audit.

TipTap claim marks are derived presentation state:

- Persist canonical text and immutable audit offsets.
- Render marks with persisted claim and audit IDs.
- Do not permanently author audit marks into document content.
- Treat highlights as stale after edits.
- Do not shift old claims heuristically and imply they remain audited.
- Handle overlapping claims explicitly.

## Testing requirements

Use:

- pytest for backend unit and integration tests.
- Real PostgreSQL/pgvector and Redis for relevant integration tests.
- Vitest and React Testing Library for frontend tests.
- Playwright for end-to-end flows.
- Alembic migration tests from empty and representative prior databases.
- Deterministic fake Ollama adapters in ordinary CI.
- Local or explicitly configured self-hosted runners for real Ollama evaluation.

Every applicable feature must test failure and empty states, not just the happy path.

High-risk coverage includes:

- Invalid structured output, repair failure, missing Ollama, missing model, and timeouts.
- English and Slovak offsets, classifications, and revision language.
- Unsupported, contradicted, numerical, causal, and scope-distorted claims where applicable.
- Malformed/encrypted PDFs and unsafe DOCX/LaTeX files.
- Temporary-file deletion after success, failure, cancellation, and interruption.
- Celery retries, idempotency, duplicate delivery, cancellation, and partial processing.
- Cross-project retrieval isolation.
- CPU-only local startup and audit smoke tests.
- Vercel fixture/demo and disconnected-backend behavior.

Do not weaken deterministic tests to accommodate model variation. Version evaluation datasets and thresholds with the tested model/prompt manifest.

## Scope exclusions

Do not add these without an explicit plan revision:

- Registration, login, authentication, users, or collaboration.
- Hosted LLM fallback or required paid services.
- Permanent uploaded-original storage.
- OCR or scanned-PDF support.
- Mathematical proof verification.
- Plagiarism detection.
- External scholarly search.
- Complex table or figure interpretation.
- Automatic thesis generation or systematic reviews.
- Google Docs, Word, browser, native desktop, or mobile extensions.
- GROBID as an MVP dependency.
- LangGraph or another agent framework.

## Milestone order

Unless the user explicitly requests another milestone, begin with the earliest incomplete milestone in section 15 of `docs/PLAN.md`:

1. Foundation F1–F8.
2. MVP1 M1.1–M1.18.
3. MVP2 M2.1–M2.26.

The first vertical slice is defined in section 16 of the plan. Do not expand it with file ingestion or evidence retrieval.

## Instruction priority

When repository instructions conflict, use this order:

1. Explicit user request.
2. Nearest applicable `AGENTS.md`.
3. Repository-root `AGENTS.md`.
4. Approved ADRs.
5. `docs/PLAN.md`.
6. Existing repository conventions.

Security, privacy, provenance, data-retention, and product-truthfulness constraints must never be weakened silently.
