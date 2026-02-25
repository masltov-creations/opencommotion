#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

UI_MODE="${OPENCOMMOTION_UI_MODE:-dev}"
GATEWAY_PORT=8000
ORCHESTRATOR_PORT=8001
UI_DEV_PORT=5173

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

check_port_free() {
  local port="$1"
  local label="$2"
  if ! python3 - "$port" <<'PY'
import socket
import sys

port = int(sys.argv[1])
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    sock.bind(("127.0.0.1", port))
except OSError:
    sys.exit(1)
finally:
    sock.close()
sys.exit(0)
PY
  then
    echo "Port conflict: $label needs 127.0.0.1:$port, but it is already in use." >&2
    echo "Try: opencommotion -stop" >&2
    exit 1
  fi
}

wait_for_url() {
  local url="$1"
  local retries="${2:-30}"
  for _ in $(seq 1 "$retries"); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

check_port_free "$GATEWAY_PORT" "gateway"
check_port_free "$ORCHESTRATOR_PORT" "orchestrator"
if [[ "$UI_MODE" = "dev" ]]; then
  check_port_free "$UI_DEV_PORT" "ui-dev"
fi

mkdir -p runtime/logs runtime/agent-runs data/artifacts/bundles data/audio

if [ -f .env ]; then
  # Load .env values as defaults only. Explicit environment variables win.
  while IFS= read -r raw || [ -n "$raw" ]; do
    line="$(printf '%s' "$raw" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    if [ -z "$line" ] || [[ "$line" == \#* ]] || [[ "$line" != *=* ]]; then
      continue
    fi
    key="$(printf '%s' "${line%%=*}" | sed -e 's/[[:space:]]*$//')"
    value="${line#*=}"
    if [ -z "$key" ]; then
      continue
    fi
    if [ -z "${!key+x}" ]; then
      export "$key=$value"
    fi
  done < .env
fi

if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -r requirements.txt >/dev/null

if command -v docker >/dev/null 2>&1; then
  docker compose up -d redis postgres >/dev/null 2>&1 || true
fi

export PYTHONPATH="$ROOT"

nohup python -m uvicorn services.gateway.app.main:app --host 127.0.0.1 --port "$GATEWAY_PORT" > runtime/logs/gateway.log 2>&1 &
echo $! > runtime/agent-runs/gateway.pid

nohup python -m uvicorn services.orchestrator.app.main:app --host 127.0.0.1 --port "$ORCHESTRATOR_PORT" > runtime/logs/orchestrator.log 2>&1 &
echo $! > runtime/agent-runs/orchestrator.pid

if [ "$UI_MODE" = "dev" ] && [ -f apps/ui/package.json ]; then
  npm install --silent >/dev/null
  (
    cd apps/ui
    npm install --silent >/dev/null
    nohup npm run dev -- --host 127.0.0.1 --port "$UI_DEV_PORT" > "$ROOT/runtime/logs/ui.log" 2>&1 &
    echo $! > "$ROOT/runtime/agent-runs/ui.pid"
  )
fi

if [ "$UI_MODE" = "dist" ] && [ ! -f apps/ui/dist/index.html ]; then
  echo "Warning: apps/ui/dist/index.html not found. Build UI assets with: npm run ui:build" >&2
fi

if ! wait_for_url "http://127.0.0.1:$GATEWAY_PORT/health" 30; then
  echo "Gateway failed to start on port $GATEWAY_PORT." >&2
  tail -n 60 runtime/logs/gateway.log >&2 || true
  bash scripts/dev_down.sh >/dev/null 2>&1 || true
  exit 1
fi

if ! wait_for_url "http://127.0.0.1:$ORCHESTRATOR_PORT/health" 30; then
  echo "Orchestrator failed to start on port $ORCHESTRATOR_PORT." >&2
  tail -n 60 runtime/logs/orchestrator.log >&2 || true
  bash scripts/dev_down.sh >/dev/null 2>&1 || true
  exit 1
fi

if [ "$UI_MODE" = "dev" ] && [ -f apps/ui/package.json ]; then
  if ! wait_for_url "http://127.0.0.1:$UI_DEV_PORT" 45; then
    echo "UI dev server failed to start on port $UI_DEV_PORT." >&2
    tail -n 60 runtime/logs/ui.log >&2 || true
    bash scripts/dev_down.sh >/dev/null 2>&1 || true
    exit 1
  fi
fi

echo "OpenCommotion dev stack started (ui-mode: $UI_MODE)"
