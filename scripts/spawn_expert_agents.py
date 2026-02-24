#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "runtime" / "agent-runs"
RUN_DIR.mkdir(parents=True, exist_ok=True)

agents = [
    ("lead-orchestrator", "Program coordinator and merge gate owner"),
    ("platform-protocol", "Schema and shared type specialist"),
    ("api-gateway", "Gateway REST/WebSocket specialist"),
    ("services-orchestrator", "Turn planner and timeline coordinator"),
    ("ui-runtime", "Scene graph and deterministic renderer specialist"),
    ("ui-motion", "Motion graphics and narrative animation specialist"),
    ("voice-stt", "Streaming speech-to-text specialist"),
    ("voice-tts", "Local text-to-speech timing specialist"),
    ("agent-text", "Precise textual reasoning response specialist"),
    ("agent-visual", "Visual planning and brush-intent specialist"),
    ("brush-engine", "Intent-to-patch compiler specialist"),
    ("artifact-registry", "Artifact memory and recall specialist"),
    ("qa-security-perf", "Validation, security, and performance specialist"),
    ("docs-oss", "Open-source documentation specialist")
]

now = datetime.now(timezone.utc).isoformat()
for agent_id, role in agents:
    payload = {
        "id": agent_id,
        "role": role,
        "status": "running",
        "started_at": now,
        "updated_at": now,
        "logs": [
            "spawned in parallel expert wave",
            "assigned to OpenCommotion alpha foundation"
        ]
    }
    (RUN_DIR / f"{agent_id}.json").write_text(json.dumps(payload, indent=2))

print(f"Spawned {len(agents)} expert agent run files in {RUN_DIR}")
