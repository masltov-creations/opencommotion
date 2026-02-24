#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "agents" / "scaffolds" / "templates"
RUN_DIR = ROOT / "runtime" / "agent-runs"

TEMPLATE_TO_OUTPUT = {
    "wave-context.example.json": "current-wave-context.json",
    "lane-ownership.example.json": "lane-ownership.json",
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Initialize wave coordination files from scaffold templates."
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Optional run_id override applied to both generated files.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing output files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    wrote = 0
    skipped = 0

    for template_name, output_name in TEMPLATE_TO_OUTPUT.items():
        template_path = TEMPLATE_DIR / template_name
        output_path = RUN_DIR / output_name

        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")

        if output_path.exists() and not args.force:
            print(f"skip {output_path} (already exists, use --force to overwrite)")
            skipped += 1
            continue

        payload = _load_json(template_path)
        if args.run_id:
            payload["run_id"] = args.run_id

        _write_json(output_path, payload)
        print(f"wrote {output_path}")
        wrote += 1

    print(f"done wrote={wrote} skipped={skipped}")


if __name__ == "__main__":
    main()
