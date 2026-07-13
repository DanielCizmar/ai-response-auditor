"""Report local Ollama server and configured-model readiness."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.auditor.ollama_runtime import (  # noqa: E402
    OllamaState,
    load_config,
    probe_ollama,
)


def main() -> int:
    config = load_config(ROOT)
    readiness = probe_ollama(config)
    print(f"Ollama state: {readiness.state.value}")

    if readiness.state is OllamaState.UNAVAILABLE:
        print(f"Ollama API unavailable at {config.base_url}: {readiness.detail}")
    elif readiness.state is OllamaState.INSTRUCTION_MODEL_MISSING:
        print(f"Missing instruction model: {config.instruction_model}")
    elif readiness.state is OllamaState.EMBEDDING_MODEL_MISSING:
        print(f"Missing embedding model: {config.embedding_model}")
    elif readiness.state is OllamaState.MODEL_LOADING:
        print(f"Instruction model is loading: {config.instruction_model}")
    else:
        print(f"Instruction model: {config.instruction_model}")
        print(f"Embedding model: {config.embedding_model}")

    if not readiness.ready:
        print("Run: corepack pnpm ollama:setup")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
