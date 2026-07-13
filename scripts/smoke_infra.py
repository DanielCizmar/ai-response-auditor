"""Verify the local PostgreSQL/pgvector and Redis Compose services."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SmokeFailure(RuntimeError):
    """Raised when a local infrastructure assertion fails."""


def compose_exec(service: str, *command: str) -> str:
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", service, *command],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip() or "no output"
        raise SmokeFailure(f"{service} command failed: {details}")
    return result.stdout.strip()


def check_postgres() -> None:
    query = (
        "SELECT current_database() || ':' || current_user || ':' || extversion "
        "FROM pg_extension WHERE extname = 'vector';"
    )
    output = compose_exec(
        "postgres",
        "sh",
        "-ec",
        f'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "{query}"',
    )
    fields = output.split(":")
    if len(fields) != 3 or not all(fields):
        raise SmokeFailure(
            "PostgreSQL connected, but the vector extension/version was not returned."
        )
    database, role, vector_version = fields
    print(
        f"PostgreSQL ready: database={database}, role={role}, vector={vector_version}"
    )


def check_redis() -> None:
    if compose_exec("redis", "redis-cli", "--raw", "PING") != "PONG":
        raise SmokeFailure("Redis did not return PONG.")

    key = "auditor:infrastructure-smoke"
    value = "ready"
    try:
        if compose_exec("redis", "redis-cli", "--raw", "SET", key, value) != "OK":
            raise SmokeFailure("Redis SET did not return OK.")
        if compose_exec("redis", "redis-cli", "--raw", "GET", key) != value:
            raise SmokeFailure("Redis GET did not return the stored smoke-test value.")
    finally:
        compose_exec("redis", "redis-cli", "--raw", "DEL", key)

    print("Redis ready: PING, SET, GET, and cleanup succeeded")


def main() -> int:
    try:
        check_postgres()
        check_redis()
    except (OSError, SmokeFailure) as error:
        print(f"Infrastructure smoke test failed: {error}", file=sys.stderr)
        return 1

    print("Local data infrastructure smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
