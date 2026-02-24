Project: OpenCommotion

Updated: 2026-02-24

Objective:
- Build a local-first, open-source visual computing platform with synchronized text, voice, and visual agent outputs.
- Enable reusable visual artifact memory with smart save and fast recall.

Current implemented baseline:
- Fresh rebuild completed after reset; prior incomplete implementation archived at:
  - `/home/mashuri/.openclaw/workspace/agent-runs/opencommotion-reset-20260223T211232`
- Monorepo scaffold with UI, gateway, orchestrator, brush engine, artifact registry, protocol schemas, and tests.
- Parallel expert-agent definitions under `agents/`.
- Runtime expert-agent run state files under `runtime/agent-runs/`.
- Workflow DAG at `runtime/orchestrator/workflow_opencommotion_v1.json`.

Implemented services and contracts:
- Gateway: `services/gateway/app/main.py`
  - Health endpoint
  - WebSocket broadcast endpoint
  - Brush compile endpoint
  - Artifact save/search/pin/archive/recall endpoints
  - Orchestrate endpoint delegating to orchestrator
- Orchestrator: `services/orchestrator/app/main.py`
  - Health endpoint
  - Basic multi-agent turn output (text + visual strokes + voice segments)
- Brush engine: `services/brush_engine/opencommotion_brush/compiler.py`
  - Intent-to-patch compiler for:
    - `spawnCharacter`
    - `animateMoonwalk`
    - `orbitGlobe`
    - `ufoLandingBeat`
    - `drawAdoptionCurve`
    - `drawPieSaturation`
    - `annotateInsight`
    - `sceneMorph`
- Artifact registry: `services/artifact_registry/opencommotion_artifacts/registry.py`
  - SQLite metadata index
  - Bundle manifest persistence
  - Search/pin/archive/lookup
- Protocol schemas:
  - `packages/protocol/schemas/events/`
  - `packages/protocol/schemas/types/`

UI baseline:
- React + Vite shell at `apps/ui/`
- Prompt submission to gateway orchestrate endpoint
- Live patch count display
- Manual artifact save and search panel

Parallel execution assets:
- Agent specs: `agents/*.json`
- Spawn script: `scripts/spawn_expert_agents.py`
- Parallel wave runner: `scripts/run_parallel_wave.sh`

Validation coverage:
- Unit: `tests/unit/test_brush_compiler.py`
- Integration:
  - `tests/integration/test_gateway_health.py`
  - `tests/integration/test_orchestrator_health.py`

Runbook:
1. `python3 -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. `npm install`
4. `cp .env.example .env`
5. `make dev`

Immediate next implementation wave:
1. Replace placeholder STT/TTS workers with production local engines.
2. Add event schema validation at gateway ingress.
3. Add embedding-backed semantic artifact recall.
4. Extend UI stage renderer from static SVG to patch-driven runtime.
5. Add end-to-end tests for full typed + voice + artifact recall loop.

Closeout execution package:
- Master closeout plan: `docs/CLOSEOUT_PLAN.md`
- Skill scaffolds: `agents/scaffolds/`
- Closeout workflow DAG: `runtime/orchestrator/workflow_opencommotion_v2_closeout.json`

Closeout implementation progress (2026-02-24):
- Completed:
  - Gateway/orchestrator schema validation integration
  - Voice transcribe/synthesize API endpoints and local audio artifact serving
  - Artifact semantic/hybrid recall and pin/archive API endpoints
  - Patch-driven UI runtime with websocket event ingestion and playback controls
  - Expanded backend integration tests, UI behavior tests, and browser E2E spec
- Remaining environment dependency:
  - Install Playwright system libs on local machine for browser E2E execution:
    - `npx playwright install --with-deps chromium`
