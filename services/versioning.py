from __future__ import annotations

import json
import os
import subprocess
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def project_version() -> str:
    package_path = PROJECT_ROOT / "package.json"
    try:
        payload = json.loads(package_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "0.0.0"
    version = str(payload.get("version", "")).strip()
    return version or "0.0.0"


@lru_cache(maxsize=1)
def project_revision() -> str:
    env_value = str(os.getenv("OPENCOMMOTION_BUILD_REVISION", "")).strip()
    if env_value:
        return env_value
    try:
        revision = (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=PROJECT_ROOT,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            .strip()
        )
    except Exception:  # noqa: BLE001
        return "dev"
    return revision or "dev"
