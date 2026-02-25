# Agent Connection Guide

This guide explains how an external agent process connects to OpenCommotion services.

Recommended default integration pattern:
- `docs/USAGE_PATTERNS.md`
- `scripts/agent_examples/robust_turn_client.py`

## 0) New-agent bootstrap (copy/paste)

Use this exact flow if you have never run the repo before:

```bash
cd /mnt/d/Dev/OpenCommotion
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
npm install
cp .env.example .env
make setup-wizard
make dev
curl -sS http://127.0.0.1:8000/health
curl -sS http://127.0.0.1:8001/health
python scripts/agent_examples/robust_turn_client.py --session first-run --prompt "quick agent bootstrap check" --no-save
make down
```

Notes:
- Keep all Python calls on the project environment: `source .venv/bin/activate` or use `.venv/bin/python`.
- If `make dev` is running in one terminal, run client commands from a second terminal.
- For a full fresh-consumer proof in one command, run `make fresh-agent-e2e`.

## 1) Start the stack

```bash
cd /mnt/d/Dev/OpenCommotion
cp .env.example .env
make dev
```

Default endpoints:
- Gateway: `http://127.0.0.1:8000`
- Orchestrator: `http://127.0.0.1:8001`
- UI: `http://127.0.0.1:5173`
- Event stream (WebSocket): `ws://127.0.0.1:8000/v1/events/ws`
- Runtime capabilities (LLM + voice): `http://127.0.0.1:8000/v1/runtime/capabilities`

## 2) Health checks

```bash
curl -sS http://127.0.0.1:8000/health
curl -sS http://127.0.0.1:8001/health
```

## 3) Agent turn flow (REST + WS)

Typical flow for an agent client:
1. Open websocket to `/v1/events/ws`.
2. Keep connection alive by sending periodic text (`ping`).
3. Submit turn to `POST /v1/orchestrate` with `session_id` and `prompt`.
4. Receive the same turn envelope on websocket (`event_type: gateway.event`).
5. Read `payload.text`, `payload.voice`, and `payload.visual_patches`.

Example:

```bash
curl -sS -X POST http://127.0.0.1:8000/v1/orchestrate \
  -H 'content-type: application/json' \
  -d '{"session_id":"agent-session-1","prompt":"moonwalk adoption chart with voice"}'
```

## 4) Voice connection points

- Transcribe uploaded audio:

```bash
curl -sS -X POST http://127.0.0.1:8000/v1/voice/transcribe \
  -F "audio=@sample.wav"
```

- Synthesize text to audio segment metadata:

```bash
curl -sS -X POST http://127.0.0.1:8000/v1/voice/synthesize \
  -H 'content-type: application/json' \
  -d '{"text":"hello opencommotion"}'
```

The returned segment `audio_uri` is served by gateway under `/v1/audio/...`.

- Check voice engine readiness (recommended before strict runs):

```bash
curl -sS http://127.0.0.1:8000/v1/voice/capabilities
```

- Check full runtime readiness (LLM + STT + TTS):

```bash
curl -sS http://127.0.0.1:8000/v1/runtime/capabilities
```

Production note:
- Set `OPENCOMMOTION_VOICE_REQUIRE_REAL_ENGINES=true` to enforce real STT/TTS engines.
- In strict mode, voice endpoints and turn orchestration return `503` when only fallback engines are available.
- Run `make voice-preflight` before starting production agents.

## 5) Artifact memory connection points

- Save artifact:

```bash
curl -sS -X POST http://127.0.0.1:8000/v1/artifacts/save \
  -H 'content-type: application/json' \
  -d '{"title":"My Turn","summary":"adoption story","tags":["moonwalk","chart"],"saved_by":"agent"}'
```

- Search modes:
  - `mode=lexical`
  - `mode=semantic`
  - `mode=hybrid`

```bash
curl -sS "http://127.0.0.1:8000/v1/artifacts/search?q=uptake&mode=semantic"
```

## 6) Draw and animate interfaces

Agents have two ways to drive drawing/animation:

- High-level turn orchestration:
  - `POST /v1/orchestrate`
  - Send natural language prompt, receive generated `visual_strokes` + compiled `visual_patches`.
- Direct visual compilation:
  - `POST /v1/brush/compile`
  - Send explicit stroke intents, receive deterministic scene patches.

Supported stroke `kind` values:
- `spawnCharacter`
- `animateMoonwalk`
- `orbitGlobe`
- `ufoLandingBeat`
- `drawAdoptionCurve`
- `drawPieSaturation`
- `annotateInsight`
- `sceneMorph`

Direct compile example:

```bash
curl -sS -X POST http://127.0.0.1:8000/v1/brush/compile \
  -H 'content-type: application/json' \
  -d '{
    "strokes": [
      {
        "stroke_id": "spawn-guide",
        "kind": "spawnCharacter",
        "params": {"actor_id": "guide", "x": 180, "y": 190},
        "timing": {"start_ms": 0, "duration_ms": 200, "easing": "easeOutCubic"}
      },
      {
        "stroke_id": "moonwalk-guide",
        "kind": "animateMoonwalk",
        "params": {"actor_id": "guide"},
        "timing": {"start_ms": 250, "duration_ms": 1300, "easing": "easeInOutCubic"}
      },
      {
        "stroke_id": "insight",
        "kind": "annotateInsight",
        "params": {"text": "Synchronized visual cue active."},
        "timing": {"start_ms": 150, "duration_ms": 150, "easing": "linear"}
      }
    ]
  }'
```

The response returns patch ops (`add` / `replace` / `remove`) with JSON paths and optional `at_ms`.

Orchestrated animate example:

```bash
curl -sS -X POST http://127.0.0.1:8000/v1/orchestrate \
  -H 'content-type: application/json' \
  -d '{"session_id":"anim-agent-1","prompt":"show a moonwalk, orbiting globe, and adoption chart"}'
```

For realtime playback:
1. Subscribe to websocket `ws://127.0.0.1:8000/v1/events/ws`.
2. Read `payload.visual_patches` in event order.
3. Apply patches by `at_ms` against local scene state.

## 7) Local expert-agent coordination files

Repository agent specs live in `agents/*.json`.

Generate runtime state files:

```bash
python3 scripts/spawn_expert_agents.py
python3 scripts/init_wave_context.py --run-id main-wave-01
```

Runtime files are written to `runtime/agent-runs/` and can be used as local coordination state for parallel agent waves.

## 8) Event envelope shape (websocket)

Gateway websocket messages follow a base envelope:
- `event_type`
- `session_id`
- `turn_id`
- `timestamp`
- `actor`
- `payload` (turn payload)

Agent clients should treat `session_id + turn_id` as idempotency keys for deduping reconnect/replay events.

## 9) Example: Codex agent workflow

Use this when Codex is acting as an execution agent against OpenCommotion:

1. Start stack:

```bash
make dev
```

2. Run the robust example agent client:

```bash
. .venv/bin/activate
python scripts/agent_examples/robust_turn_client.py \
  --session codex-demo-1 \
  --prompt "moonwalk adoption chart with synchronized narration and deterministic replay cue" \
  --search "adoption"
```

3. Inspect output fields:
- `turn_id`
- `patch_count`
- `voice_uri`
- `text`

4. Stop stack:

```bash
make down
```

## 10) Example: Other agent runtimes

Any agent runtime (Claude, custom LangGraph/AutoGen workers, local scripts) can use the same APIs:

- Option A: use the robust Python example script:

```bash
. .venv/bin/activate
python scripts/agent_examples/robust_turn_client.py --session other-agent-1 --prompt "ufo landing with pie chart"
```

- Option A2: use the minimal baseline script:

```bash
. .venv/bin/activate
python scripts/agent_examples/rest_ws_agent_client.py --session other-agent-2 --prompt "globe orbit with insight"
```

- Option B: curl + websocket client pattern:
  - open websocket: `ws://127.0.0.1:8000/v1/events/ws`
  - post orchestrate via REST:

```bash
curl -sS -X POST http://127.0.0.1:8000/v1/orchestrate \
  -H 'content-type: application/json' \
  -d '{"session_id":"other-agent-3","prompt":"globe orbit with insight"}'
```

  - process websocket event where `session_id` and `turn_id` match the REST response.

## 11) Stop stack

```bash
make down
```

## 12) Multi-agent operating context (required before execution)

Before parallel execution, the `lead-orchestrator` should publish one shared context packet for the whole wave. Every agent works from this same packet.

Required context fields:
- `run_id`: unique wave id (example: `main-wave-01`)
- `objective`: one-line target outcome
- `scope_in`: explicit included work
- `scope_out`: explicit excluded work
- `interfaces_touched`: APIs/schemas/services expected to change
- `constraints`: non-negotiable rules (determinism, backward compatibility, etc.)
- `quality_gates`: exact commands and pass criteria
- `handoff_required`: evidence each agent must provide

Context packet template:

```json
{
  "run_id": "main-wave-01",
  "objective": "Ship stable typed+voice+visual turn flow with deterministic playback.",
  "scope_in": [
    "Schema-safe event envelopes",
    "Reliable orchestrate + websocket correlation",
    "UI patch playback and artifact lifecycle"
  ],
  "scope_out": [
    "Cross-region deployment",
    "Long-haul soak over 24h"
  ],
  "interfaces_touched": [
    "/v1/orchestrate",
    "/v1/events/ws",
    "/v1/brush/compile",
    "/v1/artifacts/*"
  ],
  "constraints": [
    "No schema-breaking changes without protocol versioning",
    "Patch ordering remains deterministic by at_ms",
    "No merge without test evidence"
  ],
  "quality_gates": [
    "make test-all",
    "make test-e2e",
    "make security-checks",
    "make perf-checks",
    "npm run ui:build"
  ],
  "handoff_required": [
    "changed file list",
    "behavior delta summary",
    "validation output",
    "open risks and owner"
  ]
}
```

Template file:
- `agents/scaffolds/templates/wave-context.example.json`

Recommended run record:
1. Initialize from template in one command:
```bash
python3 scripts/init_wave_context.py --run-id main-wave-01
```
2. Fill all fields before work starts.
3. Update only `lead-orchestrator` after each checkpoint.

## 13) Efficient orchestration protocol (hub-and-spoke)

Use this sequence for every implementation wave:
1. `lead-orchestrator` decomposes work by interface boundary, not by component preference.
2. Each specialist claims one lane and becomes single writer for that lane’s files.
3. Shared contracts (`packages/protocol`, gateway envelopes) are changed first and communicated before downstream edits.
4. Specialists execute in parallel and update status in `runtime/agent-runs/<agent>.json`.
5. Handoffs are accepted only with required evidence from `handoff_required`.
6. `qa-security-perf` runs gate checks; `lead-orchestrator` merges only after all gates pass.

Lane ownership template:
- `agents/scaffolds/templates/lane-ownership.example.json`

Recommended run record:
1. Initialize from template in one command:
```bash
python3 scripts/init_wave_context.py --run-id main-wave-01
```
2. Declare one writer per lane path set.
3. Record dependency edges before implementation starts.

Efficiency rules:
- Minimize cross-lane file overlap to reduce merge conflicts.
- Use idempotency keys (`session_id + turn_id`) across all turn-processing logic.
- Prefer additive schema changes and compatibility shims over breaking rewrites.
- Escalate blockers quickly with dependency + unblock request, not just error text.

## 14) Role operating model (best ability per agent)

- `lead-orchestrator`: own decomposition, dependency ordering, merge decisions, and risk tracking.
- `platform-protocol`: own schema definitions, versioning policy, and compatibility validation.
- `api-gateway`: own ingress validation, REST contracts, websocket envelope integrity.
- `services-orchestrator`: own fanout logic, timeline merge, and turn assembly.
- `agent-text`: own concise, structured response quality and payload text clarity.
- `agent-visual`: own visual planning semantics and stroke-intent quality.
- `brush-engine`: own deterministic intent-to-patch compilation.
- `ui-runtime`: own patch applier correctness and deterministic playback behavior.
- `ui-motion`: own timing and transition quality under deterministic schedules.
- `voice-stt` and `voice-tts`: own transcript/segment quality and synchronization timing.
- `artifact-registry`: own save/search/recall lifecycle consistency and recall relevance.
- `qa-security-perf`: own E2E confidence, security checks, and performance thresholds.
- `docs-oss`: own user/agent docs accuracy against actual runtime behavior.

## 15) Coordination artifacts and cadence

Use these files as coordination system-of-record:
- Agent role definitions: `agents/*.json`
- Runtime status and logs: `runtime/agent-runs/*.json`
- Implementation scaffolds: `agents/scaffolds/*.json`
- Context and handoff templates: `agents/scaffolds/templates/*`
- Workflow DAG: `runtime/orchestrator/workflow_opencommotion_v2_plan.json`

Recommended cadence:
1. Start of wave: publish context packet and lane ownership.
2. Mid-wave checkpoint: update blockers, dependency changes, and re-plan if needed.
3. Pre-merge checkpoint: attach validation evidence and unresolved risk list.
4. Post-merge: update docs/runbooks to match shipped behavior.

Handoff report template:
- `agents/scaffolds/templates/handoff-report.example.md`

## 16) Troubleshooting for first-time agents

- Health endpoint fails after `make dev`:
  - check `runtime/logs/gateway.log`
  - check `runtime/logs/orchestrator.log`
  - rerun `make down && make dev`
- Browser E2E fails with missing system libs (example: `libnspr4.so`):
  - run `bash scripts/ensure_playwright_libs.sh`
  - rerun `make test-e2e`
- Python module error (example: `No module named httpx`):
  - run `. .venv/bin/activate`
  - rerun command with `.venv/bin/python ...`
- Websocket event not received in time:
  - keep REST payload as fallback
  - confirm `session_id + turn_id` correlation logic
