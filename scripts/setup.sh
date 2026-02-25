#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

AUTO_RUN=1
AUTO_OPEN=1
AUTO_CLI_SETUP=0
APP_URL="http://127.0.0.1:8000"
SETUP_URL="$APP_URL/?setup=1"
OPENCOMMOTION_CMD="$ROOT/opencommotion"

for arg in "$@"; do
  case "$arg" in
    --no-run)
      AUTO_RUN=0
      ;;
    --no-open)
      AUTO_OPEN=0
      ;;
    --with-cli-setup)
      AUTO_CLI_SETUP=1
      ;;
    -h|--help)
      echo "Usage: ./scripts/setup.sh [--no-run] [--no-open] [--with-cli-setup]"
      echo "  --no-run         complete install only; do not start services"
      echo "  --no-open  do not prompt/open browser after startup"
      echo "  --with-cli-setup run terminal setup wizard before startup"
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      echo "Usage: ./scripts/setup.sh [--no-run] [--no-open] [--with-cli-setup]" >&2
      exit 1
      ;;
  esac
done

open_browser() {
  local url="$1"
  if command -v wslview >/dev/null 2>&1; then
    wslview "$url" >/dev/null 2>&1 && return 0
  fi
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url" >/dev/null 2>&1 && return 0
  fi
  if command -v open >/dev/null 2>&1; then
    open "$url" >/dev/null 2>&1 && return 0
  fi
  if command -v powershell.exe >/dev/null 2>&1; then
    powershell.exe -NoProfile -Command "Start-Process \"$url\"" >/dev/null 2>&1 && return 0
  fi
  if command -v cmd.exe >/dev/null 2>&1; then
    cmd.exe /c start "" "$url" >/dev/null 2>&1 && return 0
  fi
  return 1
}

run_opencommotion() {
  # Use bash explicitly so setup works even if repo file mode does not preserve +x on pull.
  bash "$OPENCOMMOTION_CMD" "$@"
}

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required" >&2
  exit 1
fi

run_opencommotion -install

if [[ "$AUTO_CLI_SETUP" -eq 1 ]]; then
  if [[ ! -t 0 ]]; then
    echo "CLI setup wizard requires an interactive terminal." >&2
    echo "Run this command in an interactive shell: bash scripts/setup.sh --with-cli-setup" >&2
    exit 1
  fi
  run_opencommotion -setup
fi

if [[ "$AUTO_RUN" -eq 1 ]]; then
  run_opencommotion -run
  echo "Configure providers in setup mode: $SETUP_URL"
  if [[ "$AUTO_OPEN" -eq 1 ]]; then
    should_open="yes"
    if [[ -t 0 ]]; then
      read -r -p "Open browser now? [Y/n]: " open_reply
      open_reply="${open_reply:-Y}"
      case "${open_reply,,}" in
        y|yes) should_open="yes" ;;
        *) should_open="no" ;;
      esac
    fi
    if [[ "$should_open" == "yes" ]]; then
      if open_browser "$SETUP_URL"; then
        echo "Opened browser: $SETUP_URL"
      else
        echo "Could not auto-open browser. Open manually: $SETUP_URL"
      fi
    else
      echo "Open manually: $SETUP_URL"
    fi
  else
    echo "Setup complete. Open: $SETUP_URL"
  fi
else
  echo "Setup complete."
  if [[ "$AUTO_CLI_SETUP" -eq 0 ]]; then
    echo "Configure providers in setup mode: $SETUP_URL"
  fi
  echo "Run: opencommotion -run"
fi
