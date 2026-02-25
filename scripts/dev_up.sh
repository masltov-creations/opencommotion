#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

UI_MODE="${OPENCOMMOTION_UI_MODE:-dev}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ui-mode)
      UI_MODE="${2:-}"
      shift 2
      ;;
    --ui-mode=*)
      UI_MODE="${1#*=}"
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      echo "Usage: $0 [--ui-mode dev|dist|none]" >&2
      exit 1
      ;;
  esac
done

if [[ "$UI_MODE" != "dev" && "$UI_MODE" != "dist" && "$UI_MODE" != "none" ]]; then
  echo "Invalid --ui-mode '$UI_MODE'. Expected dev|dist|none." >&2
  exit 1
fi

mkdir -p runtime/logs runtime/agent-runs data/artifacts/bundles data/audio

if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -r requirements.txt >/dev/null

if command -v docker >/dev/null 2>&1; then
  docker compose up -d redis postgres >/dev/null 2>&1 || true
fi

export PYTHONPATH="$ROOT"

nohup python -m uvicorn services.gateway.app.main:app --host 127.0.0.1 --port 8000 > runtime/logs/gateway.log 2>&1 &
echo $! > runtime/agent-runs/gateway.pid

nohup python -m uvicorn services.orchestrator.app.main:app --host 127.0.0.1 --port 8001 > runtime/logs/orchestrator.log 2>&1 &
echo $! > runtime/agent-runs/orchestrator.pid

if [ "$UI_MODE" = "dev" ] && [ -f apps/ui/package.json ]; then
  npm install --silent >/dev/null
  (
    cd apps/ui
    npm install --silent >/dev/null
    nohup npm run dev -- --host 127.0.0.1 --port 5173 > "$ROOT/runtime/logs/ui.log" 2>&1 &
    echo $! > "$ROOT/runtime/agent-runs/ui.pid"
  )
fi

if [ "$UI_MODE" = "dist" ] && [ ! -f apps/ui/dist/index.html ]; then
  echo "Warning: apps/ui/dist/index.html not found. Build UI assets with: npm run ui:build" >&2
fi

echo "OpenCommotion dev stack started (ui-mode: $UI_MODE)"
