#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

UI_MODE="${OPENCOMMOTION_UI_MODE:-dev}"
# Ports are resolved after arg parsing: dev=8010/8011 (auto-scan), run=8000/8001

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

PYTHON_BIN="${OPENCOMMOTION_PYTHON_BIN:-}"
if [ -z "$PYTHON_BIN" ]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    echo "python3 or python is required" >&2
    exit 1
  fi
fi

_is_port_free() {
  local port="$1"
  "$PYTHON_BIN" - "$port" <<'PY' 2>/dev/null
import socket, sys
port = int(sys.argv[1])
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind(("127.0.0.1", port))
    s.close()
    sys.exit(0)
except OSError:
    sys.exit(1)
PY
}

find_free_port() {
  local port="$1"
  local tries=0
  while [ "$tries" -lt 20 ]; do
    if _is_port_free "$port"; then
      echo "$port"
      return 0
    fi
    port=$((port + 1))
    tries=$((tries + 1))
  done
  echo "No free port found starting from $1" >&2
  return 1
}

check_port_free() {
  local port="$1"
  local label="$2"
  if ! _is_port_free "$port"; then
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

# ── Resolve bind host and actual ports ──────────────────────────────────────
# Default to 0.0.0.0 so the app is reachable from Windows when running in WSL.
# Set OPENCOMMOTION_BIND_HOST=127.0.0.1 to restrict to loopback only.
BIND_HOST="${OPENCOMMOTION_BIND_HOST:-0.0.0.0}"

if [[ "$UI_MODE" == "dev" ]]; then
  # Auto-scan for free ports so multiple sessions (installed + dev) can coexist
  GATEWAY_PORT="$(find_free_port "${OPENCOMMOTION_GATEWAY_PORT:-8010}")"
  ORCHESTRATOR_PORT="$(find_free_port "${OPENCOMMOTION_ORCHESTRATOR_PORT:-8011}")"
  UI_DEV_PORT="$(find_free_port "${OPENCOMMOTION_UI_DEV_PORT:-5173}")"
  echo "Dev ports resolved: gateway=$GATEWAY_PORT, orchestrator=$ORCHESTRATOR_PORT, ui=$UI_DEV_PORT"
else
  # Prod/run mode: fixed ports, fail fast on conflict
  GATEWAY_PORT="${OPENCOMMOTION_GATEWAY_PORT:-8000}"
  ORCHESTRATOR_PORT="${OPENCOMMOTION_ORCHESTRATOR_PORT:-8001}"
  UI_DEV_PORT="${OPENCOMMOTION_UI_DEV_PORT:-5173}"
  check_port_free "$GATEWAY_PORT" "gateway"
  check_port_free "$ORCHESTRATOR_PORT" "orchestrator"
fi

mkdir -p runtime/logs runtime/agent-runs data/artifacts/bundles data/audio

# Persist chosen ports so dev_down, playwright, and status commands use the right ones
printf 'GATEWAY_PORT=%s\nORCHESTRATOR_PORT=%s\nUI_DEV_PORT=%s\nUI_MODE=%s\n' \
  "$GATEWAY_PORT" "$ORCHESTRATOR_PORT" "$UI_DEV_PORT" "$UI_MODE" \
  > runtime/agent-runs/ports.env

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

if [ "$UI_MODE" = "dist" ]; then
  UI_DIST_ROOT_EFFECTIVE="${OPENCOMMOTION_UI_DIST_ROOT:-runtime/ui-dist}"
  if [[ "$UI_DIST_ROOT_EFFECTIVE" != /* ]]; then
    UI_DIST_ROOT_EFFECTIVE="$ROOT/$UI_DIST_ROOT_EFFECTIVE"
  fi
  if [ ! -f "$UI_DIST_ROOT_EFFECTIVE/index.html" ] && [ -f "$ROOT/apps/ui/dist/index.html" ]; then
    export OPENCOMMOTION_UI_DIST_ROOT="$ROOT/apps/ui/dist"
    UI_DIST_ROOT_EFFECTIVE="$ROOT/apps/ui/dist"
    echo "Using bundled UI dist fallback: $UI_DIST_ROOT_EFFECTIVE"
  fi
fi

USE_CURRENT_PYTHON="${OPENCOMMOTION_USE_CURRENT_PYTHON:-false}"
if [[ "$USE_CURRENT_PYTHON" == "1" || "$USE_CURRENT_PYTHON" == "true" || "$USE_CURRENT_PYTHON" == "yes" || "$USE_CURRENT_PYTHON" == "on" ]]; then
  echo "Using current Python environment (OPENCOMMOTION_USE_CURRENT_PYTHON enabled)."
else
  if [ ! -x .venv/bin/python ]; then
    "$PYTHON_BIN" -m venv .venv
  fi

  source .venv/bin/activate
  pip install -r requirements.txt >/dev/null
fi

if command -v docker >/dev/null 2>&1; then
  docker compose up -d redis postgres >/dev/null 2>&1 || true
fi

export PYTHONPATH="$ROOT"
export ORCHESTRATOR_URL="http://127.0.0.1:$ORCHESTRATOR_PORT"

UVICORN_LOG_CONFIG="$ROOT/scripts/uvicorn_log_config.json"
UVICORN_LOG_CONFIG_ARGS=()
if [ -f "$UVICORN_LOG_CONFIG" ]; then
  UVICORN_LOG_CONFIG_ARGS=(--log-config "$UVICORN_LOG_CONFIG")
fi

nohup "$PYTHON_BIN" -m uvicorn services.gateway.app.main:app --host "$BIND_HOST" --port "$GATEWAY_PORT" "${UVICORN_LOG_CONFIG_ARGS[@]}" > runtime/logs/gateway.log 2>&1 &
echo $! > runtime/agent-runs/gateway.pid

nohup "$PYTHON_BIN" -m uvicorn services.orchestrator.app.main:app --host "$BIND_HOST" --port "$ORCHESTRATOR_PORT" "${UVICORN_LOG_CONFIG_ARGS[@]}" > runtime/logs/orchestrator.log 2>&1 &
echo $! > runtime/agent-runs/orchestrator.pid

if [ "$UI_MODE" = "dev" ] && [ -f apps/ui/package.json ]; then
  npm install --silent >/dev/null
  (
    cd apps/ui
    npm install --silent >/dev/null
    VITE_GATEWAY_URL="http://127.0.0.1:$GATEWAY_PORT" \
    nohup npm run dev -- --host "$BIND_HOST" --port "$UI_DEV_PORT" > "$ROOT/runtime/logs/ui.log" 2>&1 &
    echo $! > "$ROOT/runtime/agent-runs/ui.pid"
  )
fi

if [ "$UI_MODE" = "dist" ]; then
  UI_DIST_ROOT_EFFECTIVE="${OPENCOMMOTION_UI_DIST_ROOT:-runtime/ui-dist}"
  if [[ "$UI_DIST_ROOT_EFFECTIVE" != /* ]]; then
    UI_DIST_ROOT_EFFECTIVE="$ROOT/$UI_DIST_ROOT_EFFECTIVE"
  fi
  if [ ! -f "$UI_DIST_ROOT_EFFECTIVE/index.html" ]; then
    echo "Warning: UI dist not found at $UI_DIST_ROOT_EFFECTIVE/index.html. Build UI assets with: npm run ui:build" >&2
  fi
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
  if ! wait_for_url "http://127.0.0.1:$UI_DEV_PORT" 45 && ! wait_for_url "http://0.0.0.0:$UI_DEV_PORT" 5; then
    echo "UI dev server failed to start on port $UI_DEV_PORT." >&2
    tail -n 60 runtime/logs/ui.log >&2 || true
    bash scripts/dev_down.sh >/dev/null 2>&1 || true
    exit 1
  fi
fi

echo "OpenCommotion stack started (ui-mode: $UI_MODE, gateway: $GATEWAY_PORT, orchestrator: $ORCHESTRATOR_PORT)"
