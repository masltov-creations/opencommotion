#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
UI_SRC_ROOT = ROOT / "apps" / "ui" / "src"
UI_TRACKED_DIST_ROOT = ROOT / "apps" / "ui" / "dist"
UI_RUNTIME_DIST_ROOT = ROOT / "runtime" / "ui-dist"
UI_BUILD_MARKER = UI_RUNTIME_DIST_ROOT / ".opencommotion-build-hash"
PIPER_WINDOWS_URL = "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip"
PIPER_MODEL_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/high/en_US-lessac-high.onnx?download=true"
PIPER_CONFIG_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/high/en_US-lessac-high.onnx.json?download=true"
PIPER_BIN_REL = Path("runtime/tools/piper/piper/piper.exe")
PIPER_MODEL_REL = Path("data/models/piper/en_US-lessac-high.onnx")
PIPER_CONFIG_REL = Path("data/models/piper/en_US-lessac-high.onnx.json")
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
    "voice-setup",
    "doctor",
    "quickstart",
    "version",
    "where",
    "uninstall",
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
    "-voice-setup": "voice-setup",
    "-doctor": "doctor",
    "-quickstart": "quickstart",
    "-version": "version",
    "-where": "where",
    "-uninstall": "uninstall",
}


def _venv_python() -> str:
    if os.name == "nt":
        windows_candidates = [
            ROOT / ".venv-1" / "Scripts" / "python.exe",
            ROOT / ".venv" / "Scripts" / "python.exe",
        ]
        for candidate in windows_candidates:
            if candidate.exists():
                return str(candidate)
        return sys.executable

    candidate = ROOT / ".venv" / "bin" / "python"
    if candidate.exists():
        return str(candidate)
    return sys.executable


def _project_version() -> str:
    package_path = ROOT / "package.json"
    try:
        payload = json.loads(package_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "0.0.0"
    version = str(payload.get("version", "")).strip()
    return version or "0.0.0"


def _project_revision() -> str:
    env_revision = str(os.getenv("OPENCOMMOTION_BUILD_REVISION", "")).strip()
    if env_revision:
        return env_revision
    try:
        revision = (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(ROOT),
                stderr=subprocess.DEVNULL,
                text=True,
            )
            .strip()
        )
    except Exception:  # noqa: BLE001
        return "dev"
    return revision or "dev"


def _project_identity() -> str:
    return f"OpenCommotion {_project_version()} ({_project_revision()})"


def _env_with_pythonpath() -> dict[str, str]:
    env = os.environ.copy()
    env_file = ROOT / ".env"
    if env_file.exists():
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export ") :].strip()
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                env.setdefault(key, value)
    root = str(ROOT)
    current = env.get("PYTHONPATH", "").strip()
    if current:
        parts = [part for part in current.split(":") if part]
        if root not in parts:
            env["PYTHONPATH"] = f"{root}:{current}"
    else:
        env["PYTHONPATH"] = root
    env.setdefault("OPENCOMMOTION_UI_DIST_ROOT", str(UI_RUNTIME_DIST_ROOT))
    env.setdefault("OPENCOMMOTION_UI_BUILD_OUT_DIR", str(UI_RUNTIME_DIST_ROOT))
    return env


def _run(command: list[str]) -> int:
    completed = subprocess.run(
        command,
        cwd=str(ROOT),
        check=False,
        env=_env_with_pythonpath(),
    )
    return int(completed.returncode)


def _download_file(url: str, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(url, timeout=120) as response:
        target_path.write_bytes(response.read())


def _ensure_env_file_exists() -> Path:
    env_path = ROOT / ".env"
    if env_path.exists():
        return env_path
    example_path = ROOT / ".env.example"
    if example_path.exists():
        env_path.write_text(example_path.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        env_path.write_text("", encoding="utf-8")
    return env_path


def _set_env_values(values: dict[str, str]) -> None:
    env_path = _ensure_env_file_exists()
    original_text = env_path.read_text(encoding="utf-8")
    source_lines = original_text.splitlines()
    seen_keys: set[str] = set()
    output_lines: list[str] = []

    for line in source_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            output_lines.append(line)
            continue
        key, _ = line.split("=", 1)
        normalized_key = key.strip()
        if normalized_key in values:
            output_lines.append(f"{normalized_key}={values[normalized_key]}")
            seen_keys.add(normalized_key)
        else:
            output_lines.append(line)

    missing_keys = [key for key in values if key not in seen_keys]
    if missing_keys and output_lines and output_lines[-1].strip():
        output_lines.append("")
    for key in missing_keys:
        output_lines.append(f"{key}={values[key]}")

    env_path.write_text("\n".join(output_lines) + "\n", encoding="utf-8")


def _verify_piper_engine() -> int:
    return _run(
        [
            _venv_python(),
            "-c",
            (
                "from services.agents.voice.tts.worker import synthesize_segments; "
                "result=synthesize_segments('OpenCommotion Piper verification'); "
                "print('engine=' + str(result.get('engine'))); "
                "raise SystemExit(0 if result.get('engine') == 'piper' else 1)"
            ),
        ]
    )


def _npm_executable() -> str | None:
    candidates = ["npm.cmd", "npm.exe", "npm"] if os.name == "nt" else ["npm"]
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def _bash_executable() -> str:
    if os.name != "nt":
        return "bash"
    preferred = [
        Path("C:/Program Files/Git/bin/bash.exe"),
        Path("C:/Program Files/Git/usr/bin/bash.exe"),
    ]
    for candidate in preferred:
        if candidate.exists():
            return str(candidate)
    resolved = shutil.which("bash")
    return resolved or "bash"


def _vite_entry_candidates() -> list[Path]:
    return [
        ROOT / "node_modules" / "vite" / "bin" / "vite.js",
        ROOT / "apps" / "ui" / "node_modules" / "vite" / "bin" / "vite.js",
    ]


def _ui_toolchain_ready() -> bool:
    return any(path.exists() for path in _vite_entry_candidates())


def _repair_vite_exec_bits() -> None:
    candidates = [
        ROOT / "node_modules" / ".bin" / "vite",
        ROOT / "apps" / "ui" / "node_modules" / ".bin" / "vite",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            mode = path.stat().st_mode
            path.chmod(mode | 0o111)
        except OSError:
            # Best effort only. Fallback execution path below avoids requiring +x.
            pass


def _install_ui_dependencies() -> int:
    npm_exec = _npm_executable()
    if npm_exec is None:
        return 127
    print("Installing UI dependencies...")
    code = _run([npm_exec, "install", "--silent"])
    if code != 0:
        return code
    # Workspaces should be covered by root install; keep this as a repair pass for older checkouts.
    return _run([npm_exec, "install", "--workspace", "@opencommotion/ui", "--silent"])


def cmd_install() -> int:
    return _run([_bash_executable(), "scripts/install_local.sh"])


def cmd_setup() -> int:
    return _run([_venv_python(), "scripts/setup_wizard.py"])


def cmd_run() -> int:
    ui_code = _ensure_ui_dist_current()
    if ui_code != 0:
        return ui_code
    if os.name == "nt":
        python_bin = shlex.quote(_venv_python().replace("\\", "/"))
        return _run(
            [
                _bash_executable(),
                "-lc",
                (
                    "set -euo pipefail; "
                    "export OPENCOMMOTION_USE_CURRENT_PYTHON=1; "
                    f"export OPENCOMMOTION_PYTHON_BIN={python_bin}; "
                    "bash scripts/dev_up.sh --ui-mode dist"
                ),
            ]
        )
    return _run([_bash_executable(), "scripts/dev_up.sh", "--ui-mode", "dist"])


def cmd_dev() -> int:
    ui_code = _ensure_ui_dist_current()
    if ui_code != 0:
        return ui_code
    if os.name == "nt":
        python_bin = shlex.quote(_venv_python().replace("\\", "/"))
        return _run(
            [
                _bash_executable(),
                "-lc",
                (
                    "set -euo pipefail; "
                    "export OPENCOMMOTION_USE_CURRENT_PYTHON=1; "
                    f"export OPENCOMMOTION_PYTHON_BIN={python_bin}; "
                    "bash scripts/dev_up.sh --ui-mode dev"
                ),
            ]
        )
    return _run([_bash_executable(), "scripts/dev_up.sh", "--ui-mode", "dev"])


def _ui_hash_inputs() -> list[Path]:
    files: list[Path] = []
    if UI_SRC_ROOT.exists():
        files.extend(sorted(p for p in UI_SRC_ROOT.rglob("*") if p.is_file()))
    static_candidates = [
        ROOT / "apps" / "ui" / "index.html",
        ROOT / "apps" / "ui" / "package.json",
        ROOT / "package.json",
        ROOT / "package-lock.json",
        ROOT / ".env",
        ROOT / ".env.local",
        ROOT / ".env.production",
        ROOT / ".env.development",
        ROOT / "apps" / "ui" / ".env",
        ROOT / "apps" / "ui" / ".env.local",
        ROOT / "apps" / "ui" / ".env.production",
        ROOT / "apps" / "ui" / ".env.development",
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


def _seed_runtime_dist_from_tracked() -> bool:
    tracked_index = UI_TRACKED_DIST_ROOT / "index.html"
    runtime_index = UI_RUNTIME_DIST_ROOT / "index.html"
    if runtime_index.exists():
        return True
    if not tracked_index.exists():
        return False
    UI_RUNTIME_DIST_ROOT.parent.mkdir(parents=True, exist_ok=True)
    if UI_RUNTIME_DIST_ROOT.exists():
        shutil.rmtree(UI_RUNTIME_DIST_ROOT)
    shutil.copytree(UI_TRACKED_DIST_ROOT, UI_RUNTIME_DIST_ROOT)
    return (UI_RUNTIME_DIST_ROOT / "index.html").exists()


def _ensure_ui_dist_current() -> int:
    if os.getenv("OPENCOMMOTION_SKIP_UI_BUILD", "").strip().lower() in {"1", "true", "yes", "on"}:
        _seed_runtime_dist_from_tracked()
        return 0
    if not (ROOT / "apps" / "ui" / "package.json").exists():
        return 0
    npm_exec = _npm_executable()
    if npm_exec is None:
        _seed_runtime_dist_from_tracked()
        return 0

    if not _ui_toolchain_ready():
        deps_code = _install_ui_dependencies()
        if deps_code != 0:
            print("UI dependency install failed; cannot build UI assets.")
            if _seed_runtime_dist_from_tracked():
                print("Using bundled UI dist fallback.")
                return 0
            return deps_code

    source_hash = _ui_source_hash()
    index_path = UI_RUNTIME_DIST_ROOT / "index.html"
    previous_hash = UI_BUILD_MARKER.read_text(encoding="utf-8").strip() if UI_BUILD_MARKER.exists() else ""
    if index_path.exists() and previous_hash == source_hash:
        return 0

    print("Building UI assets...")
    _repair_vite_exec_bits()
    code = _run([npm_exec, "run", "ui:build"])
    if code != 0:
        # code 127 usually means missing vite in older/misaligned installs.
        if code == 127:
            print("npm ui:build returned 127. Repairing UI dependencies and retrying...")
            deps_code = _install_ui_dependencies()
            if deps_code != 0:
                if _seed_runtime_dist_from_tracked():
                    print("Using bundled UI dist fallback.")
                    return 0
                return deps_code
            _repair_vite_exec_bits()
            code = _run([npm_exec, "run", "ui:build"])
        if code != 0:
            print("npm ui:build failed. Retrying via node + vite.js (permission-safe path)...")
            code = _run_ui_build_via_node()
    if code != 0:
        if _seed_runtime_dist_from_tracked():
            print("UI build failed; using bundled UI dist fallback.")
            return 0
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

    for vite_entry in _vite_entry_candidates():
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


def _read_dev_ports() -> tuple[int, int]:
    """Return (gateway_port, orchestrator_port) from runtime/agent-runs/ports.env, or (0, 0)."""
    ports_file = ROOT / "runtime" / "agent-runs" / "ports.env"
    if not ports_file.exists():
        return 0, 0
    gw, orch = 0, 0
    for line in ports_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("GATEWAY_PORT="):
            try:
                gw = int(line.split("=", 1)[1])
            except ValueError:
                pass
        elif line.startswith("ORCHESTRATOR_PORT="):
            try:
                orch = int(line.split("=", 1)[1])
            except ValueError:
                pass
    return gw, orch


def _stack_running() -> bool:
    # Check production ports (run mode: 8000/8001)
    gateway_ok, _ = _check_url("http://127.0.0.1:8000/health")
    orchestrator_ok, _ = _check_url("http://127.0.0.1:8001/health")
    if gateway_ok or orchestrator_ok:
        return True
    # Also check dev ports from ports.env (dev mode: typically 8010/8011)
    gw_port, orch_port = _read_dev_ports()
    if gw_port and gw_port not in (8000, 8001):
        ok, _ = _check_url(f"http://127.0.0.1:{gw_port}/health")
        if ok:
            return True
    if orch_port and orch_port not in (8000, 8001):
        ok, _ = _check_url(f"http://127.0.0.1:{orch_port}/health")
        if ok:
            return True
    return False


def _cleanup_generated_git_dist_changes() -> None:
    subprocess.run(
        ["git", "restore", "--worktree", "--staged", "apps/ui/dist/index.html"],
        cwd=str(ROOT),
        check=False,
        env=_env_with_pythonpath(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        ["git", "clean", "-fd", "apps/ui/dist/assets"],
        cwd=str(ROOT),
        check=False,
        env=_env_with_pythonpath(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def cmd_update() -> int:
    was_running = _stack_running()
    if was_running:
        print("Detected running stack. Stopping before update...")
        stop_code = cmd_down()
        if stop_code != 0:
            return stop_code

    _cleanup_generated_git_dist_changes()
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
    return _run([_bash_executable(), "scripts/dev_down.sh"])


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
    npm_exec = _npm_executable()
    if npm_exec is None:
        print("npm is required for ui:test. Install Node.js/npm and retry.")
        return 127
    return _run([npm_exec, "run", "ui:test"])


def _wait_for_http(url: str, retries: int = 45, delay_seconds: float = 1.0) -> bool:
    for _ in range(retries):
        try:
            with urlopen(url, timeout=1):
                return True
        except URLError:
            time.sleep(delay_seconds)
    return False


def _terminate_process(process: subprocess.Popen[bytes] | subprocess.Popen[str] | None) -> None:
    if process is None:
        return
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def _cmd_test_e2e_windows() -> int:
    npm_exec = _npm_executable()
    if npm_exec is None:
        print("npm is required for e2e tests. Install Node.js/npm and retry.")
        return 127

    python_exec = _venv_python()
    env = _env_with_pythonpath()
    env["OPENCOMMOTION_LLM_PROVIDER"] = "heuristic"
    env["OPENCOMMOTION_LLM_ALLOW_FALLBACK"] = "true"
    env["OPENCOMMOTION_STT_ENGINE"] = "auto"
    env["OPENCOMMOTION_TTS_ENGINE"] = "tone-fallback"
    env["OPENCOMMOTION_VOICE_REQUIRE_REAL_ENGINES"] = "false"
    env.setdefault("OPENCOMMOTION_USE_CURRENT_PYTHON", "1")
    env.setdefault("OPENCOMMOTION_PYTHON_BIN", python_exec.replace("\\", "/"))

    logs_dir = ROOT / "runtime" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    gateway_log = (logs_dir / "gateway.e2e.log").open("w", encoding="utf-8")
    orchestrator_log = (logs_dir / "orchestrator.e2e.log").open("w", encoding="utf-8")
    ui_log = (logs_dir / "ui.e2e.log").open("w", encoding="utf-8")

    gateway_process: subprocess.Popen[str] | None = None
    orchestrator_process: subprocess.Popen[str] | None = None
    ui_process: subprocess.Popen[str] | None = None

    try:
        gateway_process = subprocess.Popen(
            [python_exec, "-m", "uvicorn", "services.gateway.app.main:app", "--host", "127.0.0.1", "--port", "8000"],
            cwd=str(ROOT),
            env=env,
            stdout=gateway_log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        orchestrator_process = subprocess.Popen(
            [python_exec, "-m", "uvicorn", "services.orchestrator.app.main:app", "--host", "127.0.0.1", "--port", "8001"],
            cwd=str(ROOT),
            env=env,
            stdout=orchestrator_log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        ui_process = subprocess.Popen(
            [npm_exec, "--workspace", "@opencommotion/ui", "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173"],
            cwd=str(ROOT),
            env=env,
            stdout=ui_log,
            stderr=subprocess.STDOUT,
            text=True,
        )

        if not _wait_for_http("http://127.0.0.1:8000/health"):
            print("Gateway failed to become healthy on port 8000.")
            return 1
        if not _wait_for_http("http://127.0.0.1:8001/health"):
            print("Orchestrator failed to become healthy on port 8001.")
            return 1

        completed = subprocess.run([npm_exec, "run", "e2e"], cwd=str(ROOT), env=env, check=False)
        return int(completed.returncode)
    finally:
        _terminate_process(ui_process)
        _terminate_process(orchestrator_process)
        _terminate_process(gateway_process)
        gateway_log.close()
        orchestrator_log.close()
        ui_log.close()


def cmd_test_e2e() -> int:
    if os.name == "nt":
        return _cmd_test_e2e_windows()

    was_running = _stack_running()
    if was_running:
        print("Detected running stack. Temporarily stopping it for browser E2E.")
        stop_code = cmd_down()
        if stop_code != 0:
            return stop_code

    python_bin = shlex.quote(sys.executable.replace("\\", "/"))

    code = _run(
        [
            _bash_executable(),
            "-lc",
            (
                "set -euo pipefail; "
                "export OPENCOMMOTION_LLM_PROVIDER=heuristic; "
                "export OPENCOMMOTION_LLM_ALLOW_FALLBACK=true; "
                "export OPENCOMMOTION_STT_ENGINE=auto; "
                "export OPENCOMMOTION_TTS_ENGINE=tone-fallback; "
                "export OPENCOMMOTION_VOICE_REQUIRE_REAL_ENGINES=false; "
                "export OPENCOMMOTION_USE_CURRENT_PYTHON=1; "
                f"export OPENCOMMOTION_PYTHON_BIN={python_bin}; "
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

    if was_running:
        print("Restoring stack after browser E2E...")
        restart_code = cmd_run()
        if restart_code != 0 and code == 0:
            return restart_code
    return code


def cmd_test_complete() -> int:
    npm_exec = _npm_executable()

    def _cmd_test_security() -> int:
        code = _run([_venv_python(), "-m", "pip", "check"])
        if code != 0:
            return code
        code = _run([_venv_python(), "-m", "pip", "install", "-q", "pip-audit"])
        if code != 0:
            return code
        code = _run([_venv_python(), "-m", "pip_audit", "-r", "requirements.txt", "--no-deps", "--disable-pip", "--progress-spinner", "off", "--timeout", "10"])
        if code != 0:
            return code
        code = _run([_venv_python(), "-m", "pytest", "-q", "-s", "--capture=no", "tests/integration/test_security_baseline.py"])
        if code != 0:
            return code
        if npm_exec is None:
            print("npm is required for security audit. Install Node.js/npm and retry.")
            return 127
        return _run([npm_exec, "audit", "--audit-level=high"])

    def _cmd_test_perf() -> int:
        code = _run([_venv_python(), "-m", "pytest", "-q", "-s", "--capture=no", "tests/integration/test_performance_thresholds.py"])
        if code != 0:
            return code
        if npm_exec is None:
            print("npm is required for perf UI test. Install Node.js/npm and retry.")
            return 127
        return _run([npm_exec, "--workspace", "@opencommotion/ui", "run", "test", "--", "src/runtime/sceneRuntime.test.ts"])

    sequence = [
        ("test", cmd_test),
        ("test-ui", cmd_test_ui),
        ("test-e2e", cmd_test_e2e),
        ("security", _cmd_test_security),
        ("perf", _cmd_test_perf),
    ]
    for _, fn in sequence:
        code = fn()
        if code != 0:
            return code
    return 0


def cmd_fresh_agent_e2e() -> int:
    if os.name == "nt":
        python_bin = shlex.quote(_venv_python().replace("\\", "/"))
        return _run(
            [
                _bash_executable(),
                "-lc",
                (
                    "set -euo pipefail; "
                    "export OPENCOMMOTION_USE_CURRENT_PYTHON=1; "
                    f"export OPENCOMMOTION_PYTHON_BIN={python_bin}; "
                    "bash scripts/fresh_agent_consumer_e2e.sh"
                ),
            ]
        )
    return _run([_bash_executable(), "scripts/fresh_agent_consumer_e2e.sh"])


def cmd_voice_setup() -> int:
    if os.name != "nt":
        print("voice-setup currently automates Windows only.")
        print("Set OPENCOMMOTION_TTS_ENGINE=piper and configure Piper model/bin paths in .env.")
        return 0

    piper_bin = ROOT / PIPER_BIN_REL
    piper_model = ROOT / PIPER_MODEL_REL
    piper_config = ROOT / PIPER_CONFIG_REL

    if not piper_bin.exists():
        print("Installing Piper binary...")
        archive_path = ROOT / "runtime" / "tools" / "piper" / "piper_windows_amd64.zip"
        _download_file(PIPER_WINDOWS_URL, archive_path)
        shutil.unpack_archive(str(archive_path), str(archive_path.parent))
        archive_path.unlink(missing_ok=True)

    if not piper_model.exists():
        print("Downloading high-quality Piper model...")
        _download_file(PIPER_MODEL_URL, piper_model)
    if not piper_config.exists():
        _download_file(PIPER_CONFIG_URL, piper_config)

    _set_env_values(
        {
            "OPENCOMMOTION_TTS_ENGINE": "piper",
            "OPENCOMMOTION_PIPER_BIN": str(PIPER_BIN_REL).replace("\\", "/"),
            "OPENCOMMOTION_PIPER_MODEL": str(PIPER_MODEL_REL).replace("\\", "/"),
            "OPENCOMMOTION_PIPER_CONFIG": str(PIPER_CONFIG_REL).replace("\\", "/"),
            "OPENCOMMOTION_AUDIO_ROOT": "data/audio",
            "ARTIFACT_DB_PATH": "data/artifacts/artifacts.db",
            "ARTIFACT_BUNDLE_ROOT": "data/artifacts/bundles",
        }
    )
    print("Updated .env with high-quality Piper defaults.")

    verify_code = _verify_piper_engine()
    if verify_code != 0:
        print("Piper verification failed. Run 'opencommotion preflight' for details.")
        return verify_code

    print("Piper voice setup complete (engine=piper verified).")
    return 0


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


def cmd_version() -> int:
    print(_project_identity())
    return 0


def cmd_where() -> int:
    print(f"repo_root={ROOT}")
    print(f"cli={Path(__file__).resolve()}")
    print(f"launcher={ROOT / 'opencommotion'}")
    return 0


def _is_standard_install() -> bool:
    """Return True if ROOT looks like the standard install path (~/apps/opencommotion).

    We use this to gate the auto-delete in cmd_uninstall — we never want to
    silently delete a developer's working clone.
    """
    try:
        home = Path.home()
        standard = home / "apps" / "opencommotion"
        return ROOT.resolve() == standard.resolve()
    except Exception:  # noqa: BLE001
        return False


def cmd_uninstall() -> int:
    """Stop the stack, remove launcher shims, then delete the install directory."""
    print("Stopping OpenCommotion stack…")
    cmd_down()

    removed: list[str] = []
    not_found: list[str] = []

    # ── WSL / Linux launcher ──────────────────────────────────────────────────
    bash = _bash_executable()
    if bash is not None:
        try:
            r = subprocess.run(
                [bash, "-lc",
                 "if [ -f ~/.local/bin/opencommotion ]; then "
                 "rm -f ~/.local/bin/opencommotion && echo removed; "
                 "else echo missing; fi"],
                capture_output=True, text=True,
            )
            if "removed" in r.stdout:
                removed.append("~/.local/bin/opencommotion (WSL/Linux)")
            else:
                not_found.append("~/.local/bin/opencommotion (WSL/Linux)")
        except Exception:  # noqa: BLE001
            not_found.append("~/.local/bin/opencommotion (WSL — could not reach)")

    # ── Windows .cmd shim + PATH entry ────────────────────────────────────────
    if os.name == "nt":
        user_profile = os.environ.get("USERPROFILE", "")
        if user_profile:
            cmd_shim = Path(user_profile) / ".local" / "bin" / "opencommotion.cmd"
            if cmd_shim.exists():
                cmd_shim.unlink()
                removed.append(str(cmd_shim))
            else:
                not_found.append(str(cmd_shim))

        ps_snippet = (
            r"$dir = Join-Path $env:USERPROFILE '.local\bin'; "
            r"$p = [Environment]::GetEnvironmentVariable('Path','User'); "
            r"if ($p -match [Regex]::Escape($dir)) { "
            r"  $clean = ($p -split ';' | Where-Object { $_ -ne $dir }) -join ';'; "
            r"  [Environment]::SetEnvironmentVariable('Path',$clean,'User'); "
            r"  Write-Output 'path-cleaned' } else { Write-Output 'path-unchanged' }"
        )
        try:
            pr = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", ps_snippet],
                capture_output=True, text=True,
            )
            if "path-cleaned" in pr.stdout:
                print("Removed ~/.local/bin from Windows user PATH (restart PowerShell to take effect).")
        except Exception:  # noqa: BLE001
            pass

    for item in removed:
        print(f"  removed : {item}")
    for item in not_found:
        print(f"  skipped : {item} (not found)")

    # ── Delete the install directory ──────────────────────────────────────────
    print()
    if not _is_standard_install():
        # Running from a dev/custom clone — never auto-delete.
        print(f"Dev workspace detected at {ROOT}")
        print("Directory NOT deleted (only the standard install at ~/apps/opencommotion is auto-removed).")
        print("To remove manually: rm -rf <your-clone-path>")
        return 0

    # Standard install: schedule deferred deletion via a temp script so this
    # Python process can exit cleanly before the directory disappears.
    install_path = str(ROOT.resolve())
    print(f"Scheduling deletion of install directory: {install_path}")
    if bash is not None:
        # Escape path for shell safety
        safe_path = install_path.replace("'", "'\\''")
        defer_cmd = f"sleep 1; rm -rf '{safe_path}'; echo 'OpenCommotion uninstalled.'"
        try:
            subprocess.Popen(
                [bash, "-c", defer_cmd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            print("Install directory will be deleted in ~1 second.")
            print("Uninstall complete. You can close this terminal.")
        except Exception as exc:  # noqa: BLE001
            print(f"Could not schedule auto-delete: {exc}")
            print(f"Please delete manually: rm -rf '{install_path}'")
    else:
        print("No bash available — please delete manually:")
        print(f"  rm -rf '{install_path}'")
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
    print(f"{_project_identity()} @ {ROOT}")
    gw_port, orch_port = _read_dev_ports()
    checks: list[tuple[str, str]] = [
        ("gateway (run)",      "http://127.0.0.1:8000/health"),
        ("orchestrator (run)", "http://127.0.0.1:8001/health"),
        ("ui (run)",           "http://127.0.0.1:8000/"),
    ]
    if gw_port and gw_port not in (8000, 8001):
        checks.append((f"gateway (dev:{gw_port})", f"http://127.0.0.1:{gw_port}/health"))
    if orch_port and orch_port not in (8000, 8001):
        checks.append((f"orch (dev:{orch_port})", f"http://127.0.0.1:{orch_port}/health"))

    failures = 0
    for label, url in checks:
        ok, detail = _check_url(url)
        state = "ok" if ok else "down"
        print(f"{label:22} {state:4} {url} ({detail})")
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
    if command == "voice-setup":
        return cmd_voice_setup()
    if command == "doctor":
        return cmd_doctor()
    if command == "quickstart":
        return cmd_quickstart()
    if command == "version":
        return cmd_version()
    if command == "where":
        return cmd_where()
    if command == "uninstall":
        return cmd_uninstall()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
