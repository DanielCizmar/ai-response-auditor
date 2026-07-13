"""Dependency readiness checks independent of FastAPI route objects."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import psycopg
import redis

from backend.auditor.config import Settings
from backend.auditor.ollama_runtime import OllamaConfig, probe_ollama


@dataclass(frozen=True)
class DependencyStatus:
    state: str
    ready: bool
    required: bool = True
    action: str | None = None


class ReadinessProbe(Protocol):
    def __call__(self) -> DependencyStatus: ...


class ReadinessService:
    """Aggregate independently testable dependency probes."""

    def __init__(self, probes: dict[str, ReadinessProbe]) -> None:
        self._probes = probes

    def check(self) -> dict[str, DependencyStatus]:
        return {name: probe() for name, probe in self._probes.items()}


def database_probe(settings: Settings) -> DependencyStatus:
    try:
        with psycopg.connect(
            settings.psycopg_url,
            connect_timeout=max(1, int(settings.readiness_timeout_seconds)),
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
                )
                if cursor.fetchone() is None:
                    return DependencyStatus(
                        state="vector_extension_missing", ready=False
                    )
    except (psycopg.Error, OSError):
        return DependencyStatus(state="unavailable", ready=False)
    return DependencyStatus(state="ready", ready=True)


def redis_probe(settings: Settings) -> DependencyStatus:
    client = redis.Redis.from_url(
        settings.redis_url.get_secret_value(),
        socket_connect_timeout=settings.readiness_timeout_seconds,
        socket_timeout=settings.readiness_timeout_seconds,
    )
    try:
        ready = bool(client.ping())
    except (redis.RedisError, OSError):
        return DependencyStatus(state="unavailable", ready=False)
    finally:
        client.close()
    return DependencyStatus(state="ready" if ready else "unavailable", ready=ready)


def ollama_probe(settings: Settings) -> DependencyStatus:
    result = probe_ollama(
        OllamaConfig(
            base_url=settings.ollama_base_url.rstrip("/"),
            instruction_model=settings.ollama_instruction_model,
            embedding_model=settings.ollama_embedding_model,
            timeout_seconds=settings.readiness_timeout_seconds,
        )
    )
    action = None
    if result.state.value in {"instruction_model_missing", "embedding_model_missing"}:
        action = "corepack pnpm ollama:setup"
    return DependencyStatus(state=result.state.value, ready=result.ready, action=action)


def build_readiness_service(settings: Settings) -> ReadinessService:
    def bind(
        probe: Callable[[Settings], DependencyStatus],
    ) -> ReadinessProbe:
        def bound_probe() -> DependencyStatus:
            return probe(settings)

        return bound_probe

    return ReadinessService(
        {
            "database": bind(database_probe),
            "redis": bind(redis_probe),
            "ollama": bind(ollama_probe),
            # Celery orchestration is introduced in M2.4, not foundation F5.
            "worker": lambda: DependencyStatus(
                state="not_configured", ready=False, required=False
            ),
        }
    )
