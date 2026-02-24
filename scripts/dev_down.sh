#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

for f in runtime/agent-runs/gateway.pid runtime/agent-runs/orchestrator.pid runtime/agent-runs/ui.pid; do
  if [ -f "$f" ]; then
    kill "$(cat "$f")" >/dev/null 2>&1 || true
    rm -f "$f"
  fi
done

pkill -f "vite --host 127.0.0.1 --port 5173" >/dev/null 2>&1 || true

docker compose down >/dev/null 2>&1 || true

echo "OpenCommotion dev stack stopped"
