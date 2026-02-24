# OpenCommotion

OpenCommotion is a local-first, open-source visual computing platform where text, voice, and visual agents respond in sync. Think: one prompt, three talents, no awkward timing collisions.

## Current Status

This repository is bootstrapped for parallel development tracks:

- `packages/protocol`: shared schemas for events and scene contracts
- `services/gateway`: FastAPI gateway (REST + WebSocket)
- `services/orchestrator`: orchestration API and timeline coordination stubs
- `services/brush_engine`: helper brush compiler (intent -> scene patches)
- `services/artifact_registry`: artifact memory service (SQLite + bundle files)
- `apps/ui`: React + Vite visual stage shell
- `runtime/agent-runs`: expert-agent run state files

## Quick Start

If this sequence runs cleanly, you’re ready to orchestrate. If not, the logs are honest and usually right.

```bash
cd /mnt/d/Dev/OpenCommotion
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install
cp .env.example .env
make dev
```

Open:

- UI: `http://127.0.0.1:5173`
- Gateway API docs: `http://127.0.0.1:8000/docs`
- Orchestrator API docs: `http://127.0.0.1:8001/docs`

## Testing

Trust, then verify:

Run backend unit/integration tests (includes full gateway-orchestrator-artifact E2E flow):

```bash
make test
```

Run UI tests:

```bash
make test-ui
```

Run all tests in one command:

```bash
make test-all
```

Run browser E2E (starts/stops local stack automatically):

```bash
make test-e2e
```

If Playwright system libraries are missing locally, install them with:

```bash
npx playwright install --with-deps chromium
```

Run full validation suite (backend + UI + browser E2E):

```bash
make test-complete
```

Run UI production build check:

```bash
npm run ui:build
```

## Closeout Execution Package

- Master plan: `docs/CLOSEOUT_PLAN.md`
- Skill scaffolds: `agents/scaffolds/`
- Closeout workflow DAG: `runtime/orchestrator/workflow_opencommotion_v2_closeout.json`

## Parallel Agent Workflow

This is the "many specialists, one release" lane.

- Agent specs: `agents/`
- Workflow DAG (foundation): `runtime/orchestrator/workflow_opencommotion_v1.json`
- Workflow DAG (closeout): `runtime/orchestrator/workflow_opencommotion_v2_closeout.json`
- Spawn helper: `scripts/spawn_expert_agents.py`
- Wave context initializer: `scripts/init_wave_context.py`
- Usage pattern guide (recommended): `docs/USAGE_PATTERNS.md`
- Agent connection guide: `docs/AGENT_CONNECTION.md`
- Agent coordination templates: `agents/scaffolds/templates/`
- Runnable agent client examples:
  - `scripts/agent_examples/robust_turn_client.py` (recommended default)
  - `scripts/agent_examples/rest_ws_agent_client.py` (minimal baseline)
- Runtime logs and status: `runtime/agent-runs/`

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
packages/
  protocol/
  plugin-sdk/
runtime/
  agent-runs/
  orchestrator/
```
