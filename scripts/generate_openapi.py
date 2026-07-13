"""Write the deterministic FastAPI schema used by the generated API client."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api.main import create_app  # noqa: E402


TARGET = ROOT / "packages" / "api-client" / "openapi.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail instead of writing when the committed schema is stale.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    schema = create_app().openapi()
    rendered = json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.check:
        if not TARGET.is_file() or TARGET.read_text(encoding="utf-8") != rendered:
            raise SystemExit(
                "OpenAPI contract is stale; run `corepack pnpm openapi:generate`."
            )
        print(f"Verified {TARGET.relative_to(ROOT)}")
        return
    TARGET.write_text(rendered, encoding="utf-8")
    print(f"Wrote {TARGET.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
