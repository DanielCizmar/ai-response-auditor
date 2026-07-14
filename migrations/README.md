# Database migrations

Alembic owns the PostgreSQL schema. Run migrations from the repository root:

```powershell
uv run python -m alembic upgrade head
```

Audit rows freeze their input and version identity immediately. Once an audit enters
a terminal state, PostgreSQL triggers reject updates to the audit and its result
records. Re-auditing creates a new audit instead of changing the prior one.

The M1.11 migration adds durable idempotency keys, explicit re-audit lineage, and
the atomicity/verifiability fields needed to reconstruct persisted claim results.
