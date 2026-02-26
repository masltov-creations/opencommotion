#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_PLAN_PATH = ROOT / "PROJECT.md"


def _git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "git command failed")
    return completed.stdout.strip()


def _resolve_base_ref(explicit_base: str | None) -> str:
    if explicit_base:
        return explicit_base

    github_base_ref = os.getenv("GITHUB_BASE_REF", "").strip()
    if github_base_ref:
        return f"origin/{github_base_ref}"

    github_before = os.getenv("GITHUB_EVENT_BEFORE", "").strip()
    if github_before and github_before != "0000000000000000000000000000000000000000":
        return github_before

    return "HEAD~1"


def _merge_base(base_ref: str) -> str:
    return _git_output("merge-base", base_ref, "HEAD")


def _changed_files(base_ref: str) -> list[str]:
    try:
        merge_base = _merge_base(base_ref)
    except RuntimeError:
        fallback_base = "HEAD~1"
        merge_base = _merge_base(fallback_base)
        print(
            "project-plan-sync: base ref "
            f"'{base_ref}' not available in this checkout; falling back to '{fallback_base}'."
        )
    raw = _git_output("diff", "--name-only", f"{merge_base}..HEAD")
    if not raw:
        return []
    return [line.strip() for line in raw.splitlines() if line.strip()]


def _is_implementation_file(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized == "PROJECT.md":
        return False
    if normalized.startswith("docs/"):
        return False
    if normalized.endswith(".md"):
        return False

    implementation_prefixes = (
        "apps/",
        "services/",
        "scripts/",
        "tests/",
        "agents/",
        "deploy/",
        "docker/",
        "runtime/",
        "data/",
        ".github/workflows/",
    )
    if any(normalized.startswith(prefix) for prefix in implementation_prefixes):
        return True

    implementation_roots = {
        ".env.example",
        "requirements.txt",
        "package.json",
        "package-lock.json",
        "docker-compose.yml",
        "docker-compose.prod.yml",
        "Makefile",
    }
    if normalized in implementation_roots:
        return True

    return normalized.endswith((".py", ".sh", ".ts", ".tsx", ".js", ".css", ".json", ".yaml", ".yml"))


def _project_updated_date() -> str | None:
    if not PROJECT_PLAN_PATH.exists():
        return None
    for line in PROJECT_PLAN_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("Updated:"):
            return line.split(":", 1)[1].strip() or None
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail when implementation files changed without keeping PROJECT.md in sync."
    )
    parser.add_argument(
        "--base-ref",
        help="Git base ref/commit to compare against (defaults to PR base branch or HEAD~1).",
    )
    args = parser.parse_args()

    base_ref = _resolve_base_ref(args.base_ref)
    try:
        changed_files = _changed_files(base_ref)
    except RuntimeError as exc:
        print(f"project-plan-sync: unable to compute change set from '{base_ref}': {exc}")
        return 1

    if not changed_files:
        print("project-plan-sync: no changed files detected; skipping.")
        return 0

    implementation_changes = [path for path in changed_files if _is_implementation_file(path)]
    plan_changed = "PROJECT.md" in changed_files

    if implementation_changes and not plan_changed:
        print("project-plan-sync: implementation files changed but PROJECT.md was not updated.")
        for path in implementation_changes:
            print(f"  - {path}")
        print("Update PROJECT.md (status, checklist, active tasks, changelog) and rerun.")
        return 2

    if implementation_changes and plan_changed:
        today = dt.date.today().isoformat()
        updated_date = _project_updated_date()
        if updated_date != today:
            print(
                "project-plan-sync: PROJECT.md was changed, but `Updated:` is not current. "
                f"Expected '{today}', found '{updated_date}'."
            )
            return 3

    print("project-plan-sync: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
