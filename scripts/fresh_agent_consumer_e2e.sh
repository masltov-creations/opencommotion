#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

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

USE_CURRENT_PYTHON="${OPENCOMMOTION_USE_CURRENT_PYTHON:-false}"
if [[ "$USE_CURRENT_PYTHON" == "1" || "$USE_CURRENT_PYTHON" == "true" || "$USE_CURRENT_PYTHON" == "yes" || "$USE_CURRENT_PYTHON" == "on" ]]; then
  echo "Using current Python environment (OPENCOMMOTION_USE_CURRENT_PYTHON enabled)."
else
  if [[ ! -x .venv/bin/python ]]; then
    "$PYTHON_BIN" -m venv .venv
  fi

  source .venv/bin/activate
  pip install -r requirements.txt >/dev/null
fi
npm install --silent >/dev/null

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

export ARTIFACT_DB_PATH="${ARTIFACT_DB_PATH:-$ROOT/data/artifacts/artifacts.db}"
export ARTIFACT_BUNDLE_ROOT="${ARTIFACT_BUNDLE_ROOT:-$ROOT/data/artifacts/bundles}"
export OPENCOMMOTION_AUDIO_ROOT="${OPENCOMMOTION_AUDIO_ROOT:-$ROOT/data/audio}"

bash scripts/dev_up.sh
trap 'bash scripts/dev_down.sh || true' EXIT

for i in $(seq 1 45); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null && curl -fsS http://127.0.0.1:8001/health >/dev/null; then
    break
  fi
  sleep 1
done

SUMMARY_FILE="$(mktemp)"
"$PYTHON_BIN" scripts/agent_examples/robust_turn_client.py \
  --session "fresh-consumer-$(date +%s)" \
  --prompt "fresh agent consumer end-to-end verification turn with moonwalk and chart" \
  --search "moonwalk" > "$SUMMARY_FILE"

"$PYTHON_BIN" - "$SUMMARY_FILE" <<'PY'
from __future__ import annotations

import json
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as f:
    payload = json.load(f)

assert payload.get("turn_id"), "missing turn_id"
assert payload.get("patch_count", 0) > 0, "patch_count must be > 0"
assert payload.get("text"), "missing text"
assert payload.get("voice_uri"), "missing voice_uri"

print(
    json.dumps(
        {
            "status": "ok",
            "source": payload.get("source"),
            "turn_id": payload.get("turn_id"),
            "patch_count": payload.get("patch_count"),
            "voice_uri": payload.get("voice_uri"),
        },
        indent=2,
    )
)
PY

rm -f "$SUMMARY_FILE"
echo "fresh-agent-e2e: pass"
