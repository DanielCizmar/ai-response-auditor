"""Small, dependency-free Ollama runtime readiness helpers."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


JsonObject = dict[str, Any]
JsonFetcher = Callable[[str, JsonObject | None, float], JsonObject]


class OllamaState(StrEnum):
    UNAVAILABLE = "unavailable"
    INSTRUCTION_MODEL_MISSING = "instruction_model_missing"
    EMBEDDING_MODEL_MISSING = "embedding_model_missing"
    MODEL_LOADING = "model_loading"
    READY = "ready"


@dataclass(frozen=True)
class OllamaConfig:
    base_url: str
    instruction_model: str
    embedding_model: str
    timeout_seconds: float


@dataclass(frozen=True)
class OllamaReadiness:
    state: OllamaState
    instruction_model: str
    embedding_model: str
    available_models: tuple[str, ...] = ()
    detail: str | None = None

    @property
    def ready(self) -> bool:
        return self.state is OllamaState.READY


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", maxsplit=1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_config(
    root: Path,
    environment: Mapping[str, str] | None = None,
) -> OllamaConfig:
    values = _read_env_file(root / ".env")
    values.update(environment if environment is not None else os.environ)
    return OllamaConfig(
        base_url=values.get("OLLAMA_BASE_URL", "http://127.0.0.1:11435").rstrip("/"),
        instruction_model=values.get(
            "OLLAMA_INSTRUCTION_MODEL", "qwen3:4b-instruct"
        ),
        embedding_model=values.get("OLLAMA_EMBEDDING_MODEL", "embeddinggemma"),
        timeout_seconds=float(values.get("OLLAMA_REQUEST_TIMEOUT_SECONDS", "180")),
    )


def fetch_json(
    url: str,
    payload: JsonObject | None,
    timeout_seconds: float,
) -> JsonObject:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
        parsed = json.loads(response.read().decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("Ollama returned a non-object JSON response.")
    return parsed


def canonical_model_name(name: str) -> str:
    normalized = name.strip()
    return normalized if ":" in normalized else f"{normalized}:latest"


def probe_ollama(
    config: OllamaConfig,
    fetcher: JsonFetcher = fetch_json,
    *,
    model_loading: bool = False,
) -> OllamaReadiness:
    try:
        response = fetcher(f"{config.base_url}/api/tags", None, config.timeout_seconds)
        models = response.get("models", [])
        if not isinstance(models, list):
            raise ValueError("Ollama model list is not an array.")
        available = tuple(
            sorted(
                {
                    canonical_model_name(str(model.get("name") or model.get("model")))
                    for model in models
                    if isinstance(model, dict)
                    and (model.get("name") or model.get("model"))
                }
            )
        )
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as error:
        return OllamaReadiness(
            state=OllamaState.UNAVAILABLE,
            instruction_model=config.instruction_model,
            embedding_model=config.embedding_model,
            detail=str(error),
        )

    if canonical_model_name(config.instruction_model) not in available:
        return OllamaReadiness(
            state=OllamaState.INSTRUCTION_MODEL_MISSING,
            instruction_model=config.instruction_model,
            embedding_model=config.embedding_model,
            available_models=available,
        )
    if canonical_model_name(config.embedding_model) not in available:
        return OllamaReadiness(
            state=OllamaState.EMBEDDING_MODEL_MISSING,
            instruction_model=config.instruction_model,
            embedding_model=config.embedding_model,
            available_models=available,
        )
    if model_loading:
        return OllamaReadiness(
            state=OllamaState.MODEL_LOADING,
            instruction_model=config.instruction_model,
            embedding_model=config.embedding_model,
            available_models=available,
        )
    return OllamaReadiness(
        state=OllamaState.READY,
        instruction_model=config.instruction_model,
        embedding_model=config.embedding_model,
        available_models=available,
    )


def run_generation_smoke(
    config: OllamaConfig,
    fetcher: JsonFetcher = fetch_json,
) -> JsonObject:
    schema: JsonObject = {
        "type": "object",
        "properties": {"status": {"type": "string", "const": "ready"}},
        "required": ["status"],
        "additionalProperties": False,
    }
    response = fetcher(
        f"{config.base_url}/api/generate",
        {
            "model": config.instruction_model,
            "prompt": 'Return a JSON object with exactly {"status":"ready"}.',
            "format": schema,
            "stream": False,
            "think": False,
            "keep_alive": "0",
            "options": {"temperature": 0, "num_predict": 16},
        },
        config.timeout_seconds,
    )
    raw_content = response.get("response")
    if not isinstance(raw_content, str):
        raise ValueError("Ollama generation response did not contain text.")
    content = json.loads(raw_content)
    if content != {"status": "ready"}:
        raise ValueError(f"Unexpected structured generation result: {content!r}")
    if response.get("done") is not True:
        raise ValueError("Ollama generation did not report completion.")
    return response
