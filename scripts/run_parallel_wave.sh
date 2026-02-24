#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT/runtime/agent-runs"

python3 "$ROOT/scripts/spawn_expert_agents.py"

for f in "$RUN_DIR"/*.json; do
  python3 - <<'PY' "$f"
import json, sys, time
from datetime import datetime, timezone
p = sys.argv[1]
with open(p) as fh:
    data = json.load(fh)
data["status"] = "running"
data.setdefault("logs", []).append("wave execution started")
data["updated_at"] = datetime.now(timezone.utc).isoformat()
with open(p, "w") as fh:
    json.dump(data, fh, indent=2)
PY
done

echo "Parallel expert wave initialized"
