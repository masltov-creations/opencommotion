#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
UI_SRC_ROOT = ROOT / "apps" / "ui" / "src"
UI_BUILD_MARKER = ROOT / "apps" / "ui" / "dist" / ".opencommotion-build-hash"
COMMANDS = [
    "install",
    "setup",
    "run",
    "dev",
    "update",
    "fresh",
    "down",
    "preflight",
    "status",
    "test",
    "test-ui",
    "test-e2e",
    "test-complete",
    "fresh-agent-e2e",
    "doctor",
    "quickstart",
]
COMMAND_FLAG_ALIASES = {
    "-install": "install",
    "-setup": "setup",
    "-run": "run",
    "-dev": "dev",
    "-update": "update",
    "-fresh": "fresh",
    "-down": "down",
    "-stop": "down",
    "-preflight": "preflight",
    "-status": "status",
    "-test": "test",
    "-test-ui": "test-ui",
    "-test-e2e": "test-e2e",
    "-test-complete": "test-complete",
    "-fresh-agent-e2e": "fresh-agent-e2e",
    "-doctor": "doctor",
    "-quickstart": "quickstart",
}


def _venv_python() -> str:
    candidate = ROOT / ".venv" / "bin" / "python"
    if candidate.exists():
        return str(candidate)
    return sys.executable


def _env_with_pythonpath() -> dict[str, str]:
    env = os.environ.copy()
    root = str(ROOT)
    current = env.get("PYTHONPATH", "").strip()
    if current:
        parts = [part for part in current.split(":") if part]
        if root not in parts:
            env["PYTHONPATH"] = f"{root}:{current}"
    else:
        env["PYTHONPATH"] = root
    return env


def _run(command: list[str]) -> int:
    completed = subprocess.run(
        command,
        cwd=str(ROOT),
        check=False,
        env=_env_with_pythonpath(),
    )
    return int(completed.returncode)


def cmd_install() -> int:
    return _run(["bash", "scripts/install_local.sh"])


def cmd_setup() -> int:
    return _run([_venv_python(), "scripts/setup_wizard.py"])


def cmd_run() -> int:
    ui_code = _ensure_ui_dist_current()
    if ui_code != 0:
        return ui_code
    return _run(["bash", "scripts/dev_up.sh", "--ui-mode", "dist"])


def cmd_dev() -> int:
    return _run(["bash", "scripts/dev_up.sh", "--ui-mode", "dev"])


def _ui_hash_inputs() -> list[Path]:
    files: list[Path] = []
    if UI_SRC_ROOT.exists():
        files.extend(sorted(p for p in UI_SRC_ROOT.rglob("*") if p.is_file()))
    static_candidates = [
        ROOT / "apps" / "ui" / "index.html",
        ROOT / "apps" / "ui" / "package.json",
        ROOT / "package.json",
        ROOT / "package-lock.json",
    ]
    for candidate in static_candidates:
        if candidate.exists():
            files.append(candidate)
    return files


def _ui_source_hash() -> str:
    digest = hashlib.sha256()
    for path in _ui_hash_inputs():
        rel = str(path.relative_to(ROOT)).encode("utf-8")
        digest.update(rel)
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _ensure_ui_dist_current() -> int:
    if os.getenv("OPENCOMMOTION_SKIP_UI_BUILD", "").strip().lower() in {"1", "true", "yes", "on"}:
        return 0
    if not (ROOT / "apps" / "ui" / "package.json").exists():
        return 0
    if shutil.which("npm") is None:
        return 0

    source_hash = _ui_source_hash()
    index_path = ROOT / "apps" / "ui" / "dist" / "index.html"
    previous_hash = UI_BUILD_MARKER.read_text(encoding="utf-8").strip() if UI_BUILD_MARKER.exists() else ""
    if index_path.exists() and previous_hash == source_hash:
        return 0

    print("Building UI assets...")
    code = _run(["npm", "run", "ui:build"])
    if code != 0:
        print("npm ui:build failed. Retrying via node + vite.js (permission-safe path)...")
        code = _run_ui_build_via_node()
    if code != 0:
        print(
            "UI build failed. If you saw 'vite: Permission denied', run: "
            "chmod +x node_modules/.bin/vite apps/ui/node_modules/.bin/vite 2>/dev/null || true"
        )
        return code
    UI_BUILD_MARKER.parent.mkdir(parents=True, exist_ok=True)
    UI_BUILD_MARKER.write_text(source_hash + "\n", encoding="utf-8")
    return 0


def _run_ui_build_via_node() -> int:
    node_bin = shutil.which("node")
    if node_bin is None:
        return 127

    candidates = [
        ROOT / "node_modules" / "vite" / "bin" / "vite.js",
        ROOT / "apps" / "ui" / "node_modules" / "vite" / "bin" / "vite.js",
    ]
    for vite_entry in candidates:
        if not vite_entry.exists():
            continue
        completed = subprocess.run(
            [node_bin, str(vite_entry), "build"],
            cwd=str(ROOT / "apps" / "ui"),
            check=False,
            env=_env_with_pythonpath(),
        )
        if completed.returncode == 0:
            return 0
    return 127


def _stack_running() -> bool:
    gateway_ok, _ = _check_url("http://127.0.0.1:8000/health")
    orchestrator_ok, _ = _check_url("http://127.0.0.1:8001/health")
    return gateway_ok or orchestrator_ok


def cmd_update() -> int:
    was_running = _stack_running()
    if was_running:
        print("Detected running stack. Stopping before update...")
        stop_code = cmd_down()
        if stop_code != 0:
            return stop_code

    print("Pulling latest changes...")
    pull_code = _run(["git", "pull", "--ff-only", "origin", "main"])
    if pull_code != 0:
        if was_running:
            print("Update pull failed; restarting previous stack state...")
            _ = cmd_run()
        return pull_code

    print("Installing/updating dependencies...")
    install_code = cmd_install()
    if install_code != 0:
        if was_running:
            print("Install failed; restarting previous stack state...")
            _ = cmd_run()
        return install_code

    if was_running:
        print("Restarting stack...")
        run_code = cmd_run()
        if run_code != 0:
            return run_code
        print("Update complete. Stack is running.")
        return 0

    print("Update complete. Stack was not running; start with: opencommotion -run")
    return 0


def _safe_remove(path: Path, dry_run: bool) -> None:
    try:
        path.relative_to(ROOT)
    except ValueError as exc:
        raise RuntimeError(f"Refusing to remove path outside project root: {path}") from exc

    if not path.exists():
        return
    rel = path.relative_to(ROOT)
    if dry_run:
        print(f"[dry-run] would remove {rel}")
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    print(f"removed {rel}")


def cmd_fresh() -> int:
    dry_run = os.getenv("OPENCOMMOTION_FRESH_DRY_RUN", "").strip().lower() in {"1", "true", "yes"}
    reset_env = os.getenv("OPENCOMMOTION_FRESH_RESET_ENV", "").strip().lower() in {"1", "true", "yes"}
    keep_bundles = os.getenv("OPENCOMMOTION_FRESH_KEEP_BUNDLES", "").strip().lower() in {"1", "true", "yes"}
    running = _stack_running()

    if running:
        if dry_run:
            print("[dry-run] would stop running stack before fresh reset")
        else:
            print("Detected running stack. Stopping before fresh reset...")
            stop_code = cmd_down()
            if stop_code != 0:
                return stop_code
    elif dry_run:
        print("[dry-run] stack is not running")

    cleanup_paths = [
        ROOT / ".venv",
        ROOT / "node_modules",
        ROOT / "apps" / "ui" / "node_modules",
        ROOT / "runtime" / "logs",
        ROOT / "runtime" / "agent-runs",
        ROOT / "data" / "audio",
        ROOT / "data" / "artifacts" / "artifacts.db",
        ROOT / "test-results",
    ]
    if not keep_bundles:
        cleanup_paths.append(ROOT / "data" / "artifacts" / "bundles")
    if reset_env:
        cleanup_paths.append(ROOT / ".env")

    print("Running fresh reset...")
    for path in cleanup_paths:
        _safe_remove(path, dry_run=dry_run)

    if dry_run:
        print("[dry-run] fresh reset complete")
        return 0

    install_code = cmd_install()
    if install_code != 0:
        return install_code

    run_code = cmd_run()
    if run_code != 0:
        return run_code

    print("Fresh start complete. Open: http://127.0.0.1:8000/?setup=1")
    return 0


def cmd_down() -> int:
    return _run(["bash", "scripts/dev_down.sh"])


def cmd_preflight() -> int:
    return _run([_venv_python(), "scripts/voice_preflight.py"])


def cmd_test() -> int:
    return _run(
        [
            _venv_python(),
            "-m",
            "pytest",
            "-q",
            "-s",
            "--capture=no",
            "tests/unit",
            "tests/integration",
        ]
    )


def cmd_test_ui() -> int:
    return _run(["npm", "run", "ui:test"])


def cmd_test_e2e() -> int:
    return _run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail; "
                "export OPENCOMMOTION_LLM_PROVIDER=heuristic; "
                "export OPENCOMMOTION_LLM_ALLOW_FALLBACK=true; "
                "export OPENCOMMOTION_STT_ENGINE=auto; "
                "export OPENCOMMOTION_TTS_ENGINE=tone-fallback; "
                "export OPENCOMMOTION_VOICE_REQUIRE_REAL_ENGINES=false; "
                "bash scripts/dev_up.sh --ui-mode dev; "
                "trap 'bash scripts/dev_down.sh' EXIT; "
                "PW_LIB_DIR=\"$(bash scripts/ensure_playwright_libs.sh)\"; "
                "for i in $(seq 1 30); do "
                "curl -fsS http://127.0.0.1:8000/health >/dev/null && "
                "curl -fsS http://127.0.0.1:8001/health >/dev/null && break; "
                "sleep 1; "
                "done; "
                "LD_LIBRARY_PATH=\"$PW_LIB_DIR:${LD_LIBRARY_PATH:-}\" npm run e2e"
            ),
        ]
    )


def cmd_test_complete() -> int:
    sequence = [
        ("test", cmd_test),
        ("test-ui", cmd_test_ui),
        ("test-e2e", cmd_test_e2e),
        ("security", lambda: _run(["bash", "-lc", ". .venv/bin/activate && python -m pip check && python -m pip install -q pip-audit && pip-audit -r requirements.txt --no-deps --disable-pip --progress-spinner off --timeout 10 && PYTHONPATH=$(pwd) pytest -q -s --capture=no tests/integration/test_security_baseline.py && npm audit --audit-level=high"])),
        ("perf", lambda: _run(["bash", "-lc", ". .venv/bin/activate && PYTHONPATH=$(pwd) pytest -q -s --capture=no tests/integration/test_performance_thresholds.py && npm --workspace @opencommotion/ui run test -- src/runtime/sceneRuntime.test.ts"])),
    ]
    for _, fn in sequence:
        code = fn()
        if code != 0:
            return code
    return 0


def cmd_fresh_agent_e2e() -> int:
    return _run(["bash", "scripts/fresh_agent_consumer_e2e.sh"])


def _tool_exists(name: str) -> bool:
    return shutil.which(name) is not None


def cmd_doctor() -> int:
    checks: list[tuple[str, bool, str]] = []
    checks.append(("python3", _tool_exists("python3"), "required"))
    checks.append(("node", _tool_exists("node"), "required for UI dev/test"))
    checks.append(("npm", _tool_exists("npm"), "required for UI dev/test"))
    checks.append(("codex", _tool_exists("codex"), "recommended for codex-cli provider"))
    checks.append(("openclaw", _tool_exists("openclaw"), "recommended for openclaw-cli provider"))
    checks.append(("espeak/espeak-ng", _tool_exists("espeak") or _tool_exists("espeak-ng"), "optional local TTS"))
    checks.append(("piper", _tool_exists("piper"), "optional high-quality local TTS"))

    failures = 0
    for label, ok, note in checks:
        state = "ok" if ok else "missing"
        print(f"{label:15} {state:7} {note}")
        if label in {"python3"} and not ok:
            failures += 1

    print("\nvoice preflight:")
    preflight_code = cmd_preflight()
    if preflight_code != 0:
        failures += 1

    print("\nservice status:")
    status_code = cmd_status()
    if status_code != 0:
        print("stack not running (this is okay if you have not started it yet)")
    return 1 if failures else 0


def cmd_quickstart() -> int:
    sequence = [
        ("install", cmd_install),
        ("setup", cmd_setup),
        ("run", cmd_run),
        ("status", cmd_status),
    ]
    for _, fn in sequence:
        code = fn()
        if code != 0:
            return code
    return 0


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
        description="OpenCommotion no-make CLI.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=COMMANDS,
        help="Command to execute",
    )
    for flag, command in COMMAND_FLAG_ALIASES.items():
        parser.add_argument(
            flag,
            action="store_true",
            help=f"Alias for '{command}' command",
        )
    return parser


def _selected_command(args: argparse.Namespace, parser: argparse.ArgumentParser) -> str | None:
    selected: list[str] = []
    if args.command:
        selected.append(args.command)
    for flag, command in COMMAND_FLAG_ALIASES.items():
        attr = flag.lstrip("-").replace("-", "_")
        if getattr(args, attr, False):
            selected.append(command)
    unique = sorted(set(selected))
    if not unique:
        parser.print_help()
        return None
    if len(unique) > 1:
        parser.error(f"Choose one command at a time; got: {', '.join(unique)}")
    return unique[0]


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    command = _selected_command(args, parser)
    if command is None:
        return 2
    if command == "install":
        return cmd_install()
    if command == "setup":
        return cmd_setup()
    if command == "run":
        return cmd_run()
    if command == "dev":
        return cmd_dev()
    if command == "update":
        return cmd_update()
    if command == "fresh":
        return cmd_fresh()
    if command == "down":
        return cmd_down()
    if command == "preflight":
        return cmd_preflight()
    if command == "status":
        return cmd_status()
    if command == "test":
        return cmd_test()
    if command == "test-ui":
        return cmd_test_ui()
    if command == "test-e2e":
        return cmd_test_e2e()
    if command == "test-complete":
        return cmd_test_complete()
    if command == "fresh-agent-e2e":
        return cmd_fresh_agent_e2e()
    if command == "doctor":
        return cmd_doctor()
    if command == "quickstart":
        return cmd_quickstart()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
