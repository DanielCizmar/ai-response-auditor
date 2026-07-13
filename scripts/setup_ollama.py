"""Start Ollama, pull configured local models, and verify readiness."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.auditor.ollama_runtime import load_config, probe_ollama  # noqa: E402


def run(*command: str) -> None:
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed with exit code {result.returncode}: {' '.join(command)}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pull configured models into the running local Ollama service."
    )
    parser.add_argument(
        "--skip-start",
        action="store_true",
        help="Do not start the base Compose service (used after a GPU override start).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(ROOT)
    try:
        if not args.skip_start:
            run("docker", "compose", "up", "--detach", "--wait", "ollama")
        for model in dict.fromkeys((config.instruction_model, config.embedding_model)):
            print(f"Pulling local Ollama model: {model}", flush=True)
            run("docker", "compose", "exec", "-T", "ollama", "ollama", "pull", model)
    except (OSError, RuntimeError) as error:
        print(f"Ollama setup failed: {error}", file=sys.stderr)
        return 1

    readiness = probe_ollama(config)
    if not readiness.ready:
        print(
            f"Ollama setup incomplete: {readiness.state.value}. {readiness.detail or ''}",
            file=sys.stderr,
        )
        return 1

    print(
        "Ollama ready with instruction model "
        f"{config.instruction_model} and embedding model {config.embedding_model}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
