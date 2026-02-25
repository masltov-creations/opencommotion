Project: OpenCommotion

Updated: 2026-02-24

Source of truth:
- This file is the active implementation plan and status tracker.
- Do not treat any other file as project completion status.

Current status:
- Overall project status: in progress
- Production readiness sign-off: pending
- Latest verification run on this branch:
  - `make test-complete`
  - `make fresh-agent-e2e`
  - `make voice-preflight`

Primary objectives:
- Build a local-first visual orchestration platform with synchronized text, voice, and visual outputs.
- Support reusable artifact memory with lexical + semantic recall.
- Provide a stable integration surface for external agents and consumers.

Implemented baseline (available now):
- Gateway (`services/gateway/app/main.py`)
  - REST ingress + websocket event fanout
  - Schema validation and stable error envelopes
  - Voice, orchestrate, brush compile, and artifact lifecycle endpoints
- Orchestrator (`services/orchestrator/app/main.py`)
  - Multi-channel turn assembly (text + voice + visual strokes)
  - Timeline metadata composition
- Brush engine (`services/brush_engine/opencommotion_brush/compiler.py`)
  - Deterministic intent-to-patch compilation
- Artifact registry (`services/artifact_registry/opencommotion_artifacts/registry.py`)
  - SQLite index + bundle manifests
  - Lexical, semantic, and hybrid recall
  - Pin/archive lifecycle support
- UI runtime (`apps/ui/src/App.tsx`, `apps/ui/src/runtime/sceneRuntime.ts`)
  - Realtime websocket ingestion
  - Patch-driven scene construction and playback controls
  - Voice input upload + transcript-assisted turn flow
- Protocol validation (`services/protocol/schema_validation.py`)
  - Schema guardrails for strokes, patches, events, and artifact bundles

Progress checklist:
- [x] End-to-end typed turn path
- [x] End-to-end voice + visual turn path (with configurable engine policy)
- [x] Configurable LLM provider path (`heuristic`/`ollama`/`openai-compatible`) with runtime capabilities API
- [x] Guided setup wizard for LLM/STT/TTS configuration (`make setup-wizard`)
- [x] Schema validation enforcement in runtime services
- [x] UI realtime patch playback
- [x] Artifact memory lifecycle + hybrid recall
- [x] Gate commands and CI checks wired (`test/e2e/security/perf`)
- [ ] Production deployment hardening (network/TLS/secrets/runtime config policy)
- [ ] Observability baseline (structured logs, metrics, alert routing)
- [ ] Soak and recovery evidence (long-running/restart/disconnect scenarios)
- [ ] Final production readiness sign-off

Active tasks:
1. Finalize voice engine provisioning for production environments.
 - Pin chosen STT/TTS engine + model artifacts per environment.
 - Validate strict mode (`OPENCOMMOTION_VOICE_REQUIRE_REAL_ENGINES=true`) in deployment target.
2. Harden deployment path.
 - Define reverse proxy/TLS baseline and secret handling.
 - Add documented backup/restore steps for artifacts DB + bundles.
3. Add operational confidence checks.
 - Add restart/reconnect reliability tests.
 - Add basic runtime metrics and failure dashboards.
4. Keep docs synchronized after each change.
 - Update `README.md`, `docs/AGENT_CONNECTION.md`, and `docs/USAGE_PATTERNS.md` with each behavior change.

Validation commands:
- `make test-all`
- `make test-e2e`
- `make security-checks`
- `make perf-checks`
- `make test-complete`
- `make fresh-agent-e2e`
- `make voice-preflight`

Execution docs:
- `README.md`
- `docs/AGENT_CONNECTION.md`
- `docs/USAGE_PATTERNS.md`
- `docs/ARCHITECTURE.md`
- `RELEASE.md`
- `CONTRIBUTING.md`

Agent assets:
- Agent specs: `agents/*.json`
- Skill scaffolds: `agents/scaffolds/`
- Coordination templates: `agents/scaffolds/templates/`
- Workflow DAGs:
  - `runtime/orchestrator/workflow_opencommotion_v1.json`
  - `runtime/orchestrator/workflow_opencommotion_v2_plan.json`

Change log:
- 2026-02-24: Removed standalone legacy status-plan tracking and consolidated active plan into `PROJECT.md`.
- 2026-02-24: Added strict voice engine policy and preflight visibility.
- 2026-02-24: Added schema validator migration away from deprecated resolver path.
- 2026-02-24: Added guided setup wizard and runtime capability visibility for user-selected LLM/STT/TTS stacks.
