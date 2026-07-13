"""Scan repository files for secrets using the committed hashed baseline."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {".secrets.baseline", "pnpm-lock.yaml", "uv.lock"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tracked-only",
        action="store_true",
        help="Scan only files tracked by Git, as CI does after checkout.",
    )
    return parser.parse_args()


def repository_files(*, tracked_only: bool) -> list[str]:
    command = ["git", "ls-files", "-z"]
    if not tracked_only:
        command.extend(["--cached", "--others", "--exclude-standard"])
    result = subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [
        path
        for path in result.stdout.decode("utf-8").split("\0")
        if path and path not in EXCLUDED
    ]


def main() -> int:
    args = parse_args()
    files = repository_files(tracked_only=args.tracked_only)
    if not files:
        print("No repository files found to scan.")
        return 0
    result = subprocess.run(
        [
            "detect-secrets-hook",
            "--baseline",
            str(ROOT / ".secrets.baseline"),
            *files,
        ],
        cwd=ROOT,
        check=False,
    )
    if result.returncode == 0:
        print(f"Secret scan passed for {len(files)} repository files.")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
