#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def _venv_python() -> str:
    candidate = ROOT / ".venv" / "bin" / "python"
    if candidate.exists():
        return str(candidate)
    return sys.executable


def _run(command: list[str]) -> int:
    completed = subprocess.run(command, cwd=str(ROOT), check=False)
    return int(completed.returncode)


def cmd_install() -> int:
    return _run(["bash", "scripts/install_local.sh"])


def cmd_setup() -> int:
    return _run([_venv_python(), "scripts/setup_wizard.py"])


def cmd_run() -> int:
    return _run(["bash", "scripts/dev_up.sh", "--ui-mode", "dist"])


def cmd_dev() -> int:
    return _run(["bash", "scripts/dev_up.sh", "--ui-mode", "dev"])


def cmd_down() -> int:
    return _run(["bash", "scripts/dev_down.sh"])


def cmd_preflight() -> int:
    return _run([_venv_python(), "scripts/voice_preflight.py"])


def _check_url(url: str) -> tuple[bool, str]:
    try:
        with urlopen(url, timeout=2) as response:
            return True, f"{response.status}"
    except URLError as exc:
        return False, str(exc.reason)
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def cmd_status() -> int:
    checks = [
        ("gateway", "http://127.0.0.1:8000/health"),
        ("orchestrator", "http://127.0.0.1:8001/health"),
        ("ui", "http://127.0.0.1:8000/"),
    ]

    failures = 0
    for label, url in checks:
        ok, detail = _check_url(url)
        state = "ok" if ok else "down"
        print(f"{label:13} {state:4} {url} ({detail})")
        if not ok:
            failures += 1
    return 0 if failures == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="opencommotion",
        description="OpenCommotion no-make CLI wrapper.",
    )
    parser.add_argument(
        "command",
        choices=["install", "setup", "run", "dev", "down", "preflight", "status"],
        help="Command to execute",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    command = args.command
    if command == "install":
        return cmd_install()
    if command == "setup":
        return cmd_setup()
    if command == "run":
        return cmd_run()
    if command == "dev":
        return cmd_dev()
    if command == "down":
        return cmd_down()
    if command == "preflight":
        return cmd_preflight()
    if command == "status":
        return cmd_status()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
