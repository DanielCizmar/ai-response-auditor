# Main branch protection

Configure these settings for `main` after the corresponding CI jobs exist. Do not make nonexistent checks required, because that would block every pull request.

## Enable now

- Require a pull request before merging.
- Require at least one approving review.
- Dismiss stale approvals when new commits are pushed.
- Require review from Code Owners.
- Require conversation resolution before merging.
- Block force pushes and branch deletion.
- Apply the rules to administrators where repository ownership permits.
- Allow squash merging; disable merge commits and rebase merging for a consistent history.
- Automatically delete head branches after merge.

## Enable as CI jobs are added

Require branches to be up to date before merging, then require these exact stable
workflow/job checks introduced by foundation milestone F7:

- `CI / Python quality`
- `CI / Backend tests`
- `CI / Frontend quality`
- `CI / Frontend tests and build`
- `CI / OpenAPI contract`
- `CI / Migration check`
- `CI / Infrastructure smoke`
- `Security / Secret scan`

The migration check is intentionally a configuration gate until M1.2 introduces
Alembic revisions. Add generated-client and Playwright checks only when their
milestones create those artifacts; do not require nonexistent checks.

Record final check names here when workflows are implemented; do not guess names in GitHub settings.

## Additional repository settings

- Enable vulnerability alerts and Dependabot security updates.
- Enable secret scanning and push protection when available for the repository.
- Require signed commits only if every active contributor can support the policy without blocking automation.
- Keep the Vercel production deployment attached to `main`; pull requests receive preview deployments.
- Create annotated tags only after the release criteria in `docs/PLAN.md` pass.

These settings are manual repository-owner actions. They are intentionally not applied by milestone F1.
