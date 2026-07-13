"""Typed application settings loaded from environment variables and ``.env``."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration; model names remain deployment configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_environment: str = "development"
    app_log_level: str = "INFO"
    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://auditor:auditor_local_dev@localhost:5432/auditor"
    )
    redis_url: SecretStr = SecretStr("redis://localhost:6379/0")
    ollama_base_url: str = "http://127.0.0.1:11435"
    ollama_instruction_model: str = "qwen3:4b-instruct"
    ollama_embedding_model: str = "embeddinggemma"
    ollama_request_timeout_seconds: float = Field(default=180, gt=0)
    ollama_max_concurrency: int = Field(default=1, ge=1)
    readiness_timeout_seconds: float = Field(default=2, gt=0, le=30)

    @property
    def psycopg_url(self) -> str:
        """Return a psycopg-compatible DSN without leaking it into representations."""

        return self.database_url.get_secret_value().replace(
            "postgresql+psycopg://", "postgresql://", 1
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
