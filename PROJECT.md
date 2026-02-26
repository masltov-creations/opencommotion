Project: OpenCommotion

Updated: 2026-02-26

Source of truth:
- This file is the active implementation plan + status tracker.
- Do not treat other files as completion state.

Plan update protocol (required):
- Update this file at the end of every implementation session that changes code, tests, docs, or release state.
- Always update all of the following together:
  - `Updated:` date
  - `Current status`
  - `Progress checklist` (check/uncheck accurately)
  - `Active tasks` (add/remove/reorder as needed)
  - `Change log` (append dated entries)
- Do not mark anything as done without evidence (test command, artifact path, or reproducible validation step).
- If work is partial, mark as in progress/pending and capture the blocker explicitly in `Active tasks`.
- Keep this file truthful even when other docs lag.

Interruption-safe checkpoint format (required):
- For any task currently being implemented, include a checkpoint block in `Active tasks` with:
  - `planned`
  - `done in this session`
  - `in progress / not finished`
  - `remaining`
- Add enough detail that another agent can resume without prior context.
- Keep stale checkpoints out: remove or close blocks when the task is fully complete.

Current status:
- Overall project status: in progress
- Production readiness sign-off: pending final deployment validation
- Latest verification run on this branch:
  - `python3 scripts/opencommotion.py test-complete`
  - `python3 scripts/opencommotion.py fresh-agent-e2e`
  - `python3 scripts/opencommotion.py doctor`
- Plan tracker status:
  - `PROJECT.md`: authoritative and current
  - `docs/VISUAL_INTELLIGENCE_PLAN.md`: synchronized summary + scenario requirements
  - `docs/TOOL_ENHANCEMENT_BACKLOG.md`: enhancement/status ledger for discovered tool gaps

Primary objectives:
- Local-first visual orchestration with synchronized text, voice, and patch animation.
- Stable integration surface for external agents and consumers.
- Production-ready operations path for Linux VM deployment.

Visual intelligence v2 plan:
- Canonical plan doc: `docs/VISUAL_INTELLIGENCE_PLAN.md`
- Tool enhancement tracker: `docs/TOOL_ENHANCEMENT_BACKLOG.md`
- Execution model: parallel lanes (contract/schema, compiler/runtime, UI rendering, QA, docs).
- Base constituent parts (generic/reusable):
  - actors
  - fx
  - materials
  - environment
  - camera
  - render mode (`2d`/`3d`)
- Stretch scenario requirements are tracked in the same plan (not separate):
  - Scenario D fish-in-bowl cinematic (`D-2D`, `D-3D`) with shader guardrails and deterministic timing.

Implemented baseline (available now):
- Gateway (`services/gateway/app/main.py`)
  - REST + websocket event fanout
  - setup APIs (`/v1/setup/*`)
  - autonomous run manager APIs (`/v1/agent-runs*`)
  - auth middleware (API key + network-trust modes)
  - Prometheus metrics endpoint (`/metrics`)
- Orchestrator (`services/orchestrator/app/main.py`)
  - multi-channel turn assembly
  - LLM runtime capability probe
  - Prometheus metrics endpoint
- Text provider adapters (`services/agents/text/adapters.py`)
  - `heuristic`, `ollama`, `openai-compatible`
  - `codex-cli`, `openclaw-cli`, `openclaw-openai`
- Voice workers (`services/agents/voice/*`)
  - local STT/TTS engines
  - OpenAI-compatible STT/TTS cloud path
  - strict real-engine enforcement support
- Agent runtime manager (`services/agent_runtime/manager.py`)
  - durable SQLite run/queue state
  - run controls (`run_once|pause|resume|stop|drain`)
  - lifecycle websocket event emission
- UI runtime (`apps/ui/src/App.tsx`)
  - setup wizard UI
  - run manager UI
  - typed/voice/artifact flow with realtime playback
- Deployment/ops assets
  - production compose: `docker-compose.prod.yml`
  - Dockerfiles: `docker/Dockerfile.*`
  - reverse proxy + TLS config: `deploy/nginx/*`
  - Prometheus/Grafana configs + dashboard: `deploy/prometheus/*`, `deploy/grafana/*`
  - backup/restore scripts: `scripts/backup_runtime.sh`, `scripts/restore_runtime.sh`

Progress checklist:
- [x] End-to-end typed turn path
- [x] End-to-end voice + visual turn path
- [x] Extended LLM provider path (Codex/OpenClaw included)
- [x] Hybrid local+cloud voice policy
- [x] Setup APIs + UI wizard + CLI fallback
- [x] Autonomous backend run manager with websocket lifecycle events
- [x] API-key auth baseline + optional network-trust mode
- [x] Prometheus metrics endpoints and Grafana dashboard assets
- [x] Production compose + TLS reverse-proxy scaffolding
- [x] Backup/restore scripts for runtime/artifact state
- [x] CI + test coverage updates for new surfaces
- [x] Automated restart-recovery and 10-session concurrency gate coverage
- [x] Provider adapter execution tests for Codex/OpenClaw paths
- [x] Generic visual primitive contract lane (`setRenderMode`, `spawnSceneActor`, `setActorMotion`, `emitFx`, etc.)
- [x] Stretch Scenario D baseline implementation (fish bowl cinematic primitives + tests)
- [x] Prompt-probe required scenario baseline (A/B/C/D path expectations pass with seed set)
- [x] V2 scene-state scaffolding: schema family, `/v2/*` API surface, deterministic op apply engine, scene snapshot endpoints
- [x] Plan-tracking enforcement gate (CI check requires `PROJECT.md` sync on implementation changes)
- [x] Local update resilience for generated UI dist conflicts (`runtime/ui-dist` runtime build path + pull-safe update flow)
- [ ] Long-haul soak/recovery evidence in production-like environment
- [ ] Final production readiness sign-off

Active tasks:
1. Production soak + recovery validation:
 - run 10-session concurrency soak in deployment target
 - verify restart behavior during in-flight run queues
2. Ops hardening closeout:
 - wire alert delivery targets for Prometheus rules
 - replace default dev keys/certs with production secrets + cert automation
3. Final release package:
 - publish release notes + version tag
 - capture final acceptance evidence bundle
4. Visual v2 closeout:
 - certify Scenario A/B/C in both 2D and 3D tracks under v2 contract
 - certify Scenario D (`D-2D`, `D-3D`) as stretch gate when enabled
 - complete GPU/shader runtime hardening and perf budget gates
5. Tool enhancement governance:
 - keep `docs/TOOL_ENHANCEMENT_BACKLOG.md` current for any discovered blocker/degradation
 - require acceptance evidence link before marking tool enhancements done
6. Prompt probe triage loop:
 - run `python3 scripts/prompt_compat_probe.py --inprocess --seed 23`
 - triage required failures as bugs and exploratory misses as enhancement candidates
 - update `docs/TOOL_ENHANCEMENT_BACKLOG.md` with status + acceptance criteria
7. Composable visual constituent parts:
 - continue refactoring prompt handlers to reusable actor/motion/material scene builders
 - keep quantity-aware noun mapping generic (multi-instance scenes should not require bespoke one-offs)
 - gate with unit tests + prompt probe snapshots for regression control
8. Prompt-context pipeline hardening (in progress):
 - planned:
   - first-turn prompt rewrite with explicit context + skill reference + examples before rendering
   - follow-up prompt rewrite with scene-delta context and continuity rules
   - scene-request loop so agent can request current scene context before final rewrite
 - done in this session:
   - tightened rewrite contract to explicit runtime execution language (imperative draw/update semantics) in text worker (`services/agents/text/worker.py`)
   - expanded gateway v2 rewrite context with invocation phase + capability hints (`services/gateway/app/main.py`)
   - added narration invocation wrapper so non-heuristic providers are told exactly how OpenCommotion invokes them (`services/agents/text/worker.py`)
   - added non-actionable response guard (clarification/refusal text gets forced-progress narration) in text worker (`services/agents/text/worker.py`)
   - added unit coverage for CLI invocation wrapper and clarification fallback behavior (`tests/unit/test_text_worker.py`)
   - validation evidence:
     - `.venv/bin/python -m pytest -q -s tests/unit/test_text_worker.py` (14 passed)
     - `.venv/bin/python -m pytest -q -s tests/integration/test_gateway_v2_scene_state.py::test_v2_orchestrate_applies_prompt_rewrite_and_scene_request_flow tests/integration/test_gateway_v2_scene_state.py::test_v2_turn_without_visual_delta_emits_agent_context_reminder` (2 passed)
     - `.venv/bin/python scripts/opencommotion.py test-complete` (pass)
     - `.venv/bin/python scripts/opencommotion.py fresh-agent-e2e` (pass)
 - in progress / not finished:
   - follow-up scene-delta optimization coverage needs additional integration assertions for multi-turn mutation prompts
 - remaining:
   - extend integration tests for “agent asks question” and “no scene update then reminder” under codex/openclaw provider simulations
   - close task only after end-to-end prompt runs confirm scene updates on first and follow-up turns

Validation commands:
- `python3 scripts/opencommotion.py test`
- `python3 scripts/opencommotion.py test-ui`
- `python3 scripts/opencommotion.py test-e2e`
- `python3 scripts/opencommotion.py test-complete`
- `python3 scripts/opencommotion.py fresh-agent-e2e`
- `python3 scripts/opencommotion.py preflight`
- `python3 scripts/opencommotion.py doctor`

Execution docs:
- `README.md`
- `docs/AGENT_CONNECTION.md`
- `docs/USAGE_PATTERNS.md`
- `docs/ARCHITECTURE.md`
- `docs/TOOL_ENHANCEMENT_BACKLOG.md`
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
- 2026-02-25: Added no-make operator CLI expansion (test/e2e/doctor/quickstart) and fixed PYTHONPATH preflight path.
- 2026-02-25: Added LLM adapters for `codex-cli`, `openclaw-cli`, and `openclaw-openai`.
- 2026-02-25: Added OpenAI-compatible STT/TTS support in voice workers.
- 2026-02-25: Added setup APIs and backend autonomous run manager APIs/events.
- 2026-02-25: Added API-key/network-trust auth middleware and Prometheus metrics.
- 2026-02-25: Added production deployment assets (compose, Dockerfiles, proxy, Prometheus, Grafana) and backup/restore scripts.
- 2026-02-25: Added automated restart-recovery + 10-session run-manager concurrency tests.
- 2026-02-25: Added provider execution tests for `codex-cli`, `openclaw-cli`, and `openclaw-openai`.
- 2026-02-25: Added websocket auth enforcement tests and run-control lifecycle coverage.
- 2026-02-25: Added visual-intelligence-v2 plan doc and generic visual primitive lane, including fish-bowl stretch scenario requirements and tests.
- 2026-02-25: Added tool enhancement backlog tracking doc and linked governance tasks in source-of-truth plan.
- 2026-02-25: Added prompt compatibility probe script and triaged scenario A/B tool gaps plus exploratory prompt enhancement candidate.
- 2026-02-25: Implemented scenario A (cow/moon lyric+bouncing-ball) and scenario B (day/night transition) baseline support; prompt probe required failures reduced to zero.
- 2026-02-26: Added V2 scene-state contract + gateway endpoints (`/v2/orchestrate`, `/v2/events/ws`, `/v2/runtime/capabilities`, `/v2/scenes/*`), deterministic op engine/store, and UI default switch to `/v2` with legacy patch compatibility lane.
- 2026-02-26: Refactored visual worker with reusable scene-builder primitives for actor spawn/motion and added quantity-aware bouncing-ball composition so plural prompts map to composable multi-actor output.
- 2026-02-26: Added prompt-to-backend lifecycle visibility in UI (turn status pill with running timer + completed/failed state messaging) and test coverage for status transitions.
- 2026-02-26: Changed visual fallback policy so any non-empty prompt produces scene primitives (not text-only), and tightened noun extraction + interface-primitives routing annotations for generic prompt coverage.
- 2026-02-26: Disabled legacy canned scene templates by default (opt-in via `OPENCOMMOTION_ENABLE_LEGACY_TEMPLATE_SCENES=1`), strengthened narration-agent context to avoid clarification loops, and updated default UI prompt to a non-template scene.
- 2026-02-26: Added v2 “no scene update” guard: gateway now applies an agent-context reminder retry when a turn yields no visual delta, surfaces reminder warnings to UI, and logs reminder status in the backend agent thread.
- 2026-02-26: Checkpointed in-progress prompt-context rewrite pipeline work (gateway+text-worker partial wiring) with explicit planned/done/in-progress/remaining status to preserve interruption recovery.
- 2026-02-26: Added enforced plan-sync guard (`scripts/check_project_plan_sync.py`) and CI workflow validation so implementation changes require synchronized `PROJECT.md` updates with current `Updated:` date.
- 2026-02-26: Formalized interruption-safe checkpoint format in `PROJECT.md` so every in-flight task captures planned/done/in-progress/remaining for handoff continuity.
- 2026-02-26: Hardened LLM invocation context for narration/rewrite (explicit runtime contract + capability-aware context + forced-progress handling for clarification/refusal responses) and added unit tests for CLI provider wrapper behavior.
- 2026-02-26: Completed full validation gate (`test-complete`) plus fresh-agent consumer E2E (`fresh-agent-e2e`) after context-hardening changes; both passed on this branch.
- 2026-02-26: Moved runtime UI build output to `runtime/ui-dist` (untracked), added gateway/dev-start fallback to bundled dist, hardened `opencommotion update` to clean generated tracked dist churn, and updated bootstrap instructions to avoid pull failures from local generated assets.
