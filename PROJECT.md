Project: OpenCommotion

Updated: 2026-02-25

Source of truth:
- This file is the active implementation plan + status tracker.
- Do not treat other files as completion state.

Current status:
- Overall project status: in progress
- Production readiness sign-off: pending final deployment validation
- Latest verification run on this branch:
  - `python3 scripts/opencommotion.py test-complete`
  - `python3 scripts/opencommotion.py fresh-agent-e2e`
  - `python3 scripts/opencommotion.py doctor`

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
