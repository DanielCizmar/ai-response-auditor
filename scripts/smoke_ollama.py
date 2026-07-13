"""Run a small structured generation through the configured local model."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.auditor.ollama_runtime import (  # noqa: E402
    load_config,
    probe_ollama,
    run_generation_smoke,
)


def main() -> int:
    config = load_config(ROOT)
    readiness = probe_ollama(config)
    if not readiness.ready:
        print(
            f"Ollama smoke test cannot start: {readiness.state.value}. "
            "Run: corepack pnpm ollama:setup",
            file=sys.stderr,
        )
        return 1

    try:
        response = run_generation_smoke(config)
    except (OSError, TimeoutError, ValueError) as error:
        print(f"Ollama generation smoke test failed: {error}", file=sys.stderr)
        return 1

    elapsed_seconds = int(response.get("total_duration", 0)) / 1_000_000_000
    print(
        f"Ollama generation smoke test passed with {config.instruction_model} "
        f"in {elapsed_seconds:.2f}s."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
