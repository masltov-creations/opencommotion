# OpenCommotion

OpenCommotion is a local-first visual orchestration platform where text, voice, and visual agents produce one synchronized turn. Give it a prompt and you get narration, scene patches, and timeline-aware output from a single flow.

## What This Is

OpenCommotion is built for:
- Interactive visual explainers that need synchronized text + voice + animation
- Agent-driven content generation with deterministic patch playback
- Local development and testing of multi-modal orchestration patterns

Core services:
- `services/gateway`: FastAPI ingress (`REST + WebSocket`)
- `services/orchestrator`: turn planning and timeline merge
- `services/brush_engine`: intent-to-patch compiler
- `services/artifact_registry`: artifact save/search/recall
- `apps/ui`: React runtime for scene playback
- `packages/protocol` and `services/protocol`: shared contracts and schema validation

## How It Works (E2E Flow)

1. Client submits `POST /v1/orchestrate` with `session_id` + prompt.
2. Gateway wraps request into a turn envelope.
3. Orchestrator coordinates text, voice, and visual generation.
4. Brush engine compiles visual intents into deterministic scene patches.
5. Gateway emits final event envelope on `WS /v1/events/ws`.
6. UI/agent applies `visual_patches`, plays voice URI, and renders text.
7. Optional artifact lifecycle: save, search, recall, pin, archive.

## Quick Start (First Run)

Prereqs:
- Python 3.11+
- Node.js 20+
- npm

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install
cp .env.example .env
make dev
```

Open local endpoints:
- UI: `http://127.0.0.1:5173`
- Gateway docs: `http://127.0.0.1:8000/docs`
- Orchestrator docs: `http://127.0.0.1:8001/docs`

Stop stack:

```bash
make down
```

## End-to-End Smoke Test (Recommended)

Run one full orchestrated turn and validate output:

```bash
make dev
source .venv/bin/activate
curl -sS http://127.0.0.1:8000/health
curl -sS http://127.0.0.1:8001/health
python scripts/agent_examples/robust_turn_client.py \
  --session first-run \
  --prompt "quick onboarding verification turn" \
  --search onboarding
make down
```

Expected output includes:
- `source` (`websocket` or `rest-fallback`)
- `turn_id`
- `patch_count`
- `text`
- `voice_uri`

## How to Use It

Use OpenCommotion from:
- UI at `http://127.0.0.1:5173`
- REST + WebSocket APIs via custom clients
- Agent runtimes (Codex, Claude, LangGraph/AutoGen, custom workers)

Essential endpoints:
- `POST /v1/orchestrate`
- `POST /v1/brush/compile`
- `POST /v1/voice/transcribe`
- `POST /v1/voice/synthesize`
- `POST /v1/artifacts/save`
- `GET /v1/artifacts/search`
- `WS /v1/events/ws`

## Connect Agents

Default robust pattern:
1. Keep one websocket open to `ws://127.0.0.1:8000/v1/events/ws`.
2. Submit turns via `POST /v1/orchestrate`.
3. Correlate with `session_id + turn_id`.
4. Prefer websocket envelope for final synchronization.
5. Fallback to REST payload if websocket event is late/missing.

Run example agents:

```bash
source .venv/bin/activate
python scripts/agent_examples/robust_turn_client.py \
  --session codex-demo-1 \
  --prompt "moonwalk adoption chart with synchronized narration" \
  --search adoption
```

```bash
source .venv/bin/activate
python scripts/agent_examples/rest_ws_agent_client.py \
  --session baseline-demo-1 \
  --prompt "ufo landing with pie chart"
```

Multi-agent coordination bootstrap:

```bash
python3 scripts/spawn_expert_agents.py
python3 scripts/init_wave_context.py --run-id closeout-wave-01
```

This writes coordination files to `runtime/agent-runs/` for lane ownership, wave context, and handoff workflow.

## Tests and Validation

Backend tests:

```bash
make test
```

UI tests:

```bash
make test-ui
```

Backend + UI:

```bash
make test-all
```

Browser E2E:

```bash
make test-e2e
```

Full validation suite:

```bash
make test-complete
```

If Playwright dependencies are missing:

```bash
npx playwright install --with-deps chromium
```

## Docs You Want First

- Agent connection guide: `docs/AGENT_CONNECTION.md`
- Robust usage patterns: `docs/USAGE_PATTERNS.md`
- Architecture: `docs/ARCHITECTURE.md`
- Closeout plan: `docs/CLOSEOUT_PLAN.md`
- Agent scaffolds and templates: `agents/scaffolds/`

## Repository Structure

```text
apps/
  ui/
services/
  gateway/
  orchestrator/
  agents/
  brush_engine/
  artifact_registry/
  protocol/
packages/
  protocol/
  plugin-sdk/
runtime/
  agent-runs/
  orchestrator/
scripts/
  agent_examples/
```
