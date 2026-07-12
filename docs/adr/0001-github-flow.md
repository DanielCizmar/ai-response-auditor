# ADR 0001: GitHub as source of truth with GitHub Flow

- Status: Accepted
- Date: 2026-07-12
- Decision owners: Repository owner

## Context

The project needs a simple collaboration and release process before application scaffolding begins. Work is divided into small milestones, `main` must remain deployable, Vercel preview deployments will be created from pull requests, and architectural decisions need a reviewable history.

Long-lived release/development branches would add coordination overhead without providing value to the current single-repository, small-contributor workflow.

## Decision

GitHub is the source of truth for code, documentation, issues, pull requests, reviews, CI results, and release tags.

Use GitHub Flow:

1. Create a short-lived branch from `main`.
2. Implement one focused milestone or issue.
3. Open a pull request and pass required checks and review.
4. Squash-merge into protected `main`.
5. Delete the merged branch.

Use `foundation/*`, `feature/*`, `fix/*`, and `docs/*` branch prefixes. Release accepted product stages with annotated tags defined in `docs/PLAN.md`.

Repository protection settings are documented in `docs/github/branch-protection.md` and are enabled incrementally as stable CI jobs become available.

## Consequences

- `main` remains the single integration and production branch.
- Changes receive a reviewable pull request and a focused final commit.
- GitHub and Vercel can provide per-pull-request status and previews.
- Contributors must keep branches short-lived and rebase/update when required checks demand it.
- Urgent fixes still use pull requests unless repository recovery makes that impossible.
- Branch protection and repository settings require manual owner configuration; this ADR does not apply external settings automatically.

## Alternatives considered

- **Git Flow:** rejected because long-lived `develop` and release branches add unnecessary ceremony for small incremental milestones.
- **Direct commits to `main`:** rejected because they bypass review, required checks, and preview validation.
- **Trunk-based commits without pull requests:** rejected for the same review and CI-governance reasons.
