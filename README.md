# OpenCommotion

OpenCommotion is a local-first, open-source visual computing platform where text, voice, and visual agents respond in sync.

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

Run UI production build check:

```bash
npm run ui:build
```

## Parallel Agent Workflow

- Agent specs: `agents/`
- Workflow DAG: `runtime/orchestrator/workflow_opencommotion_v1.json`
- Spawn helper: `scripts/spawn_expert_agents.py`
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
