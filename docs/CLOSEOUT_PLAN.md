# OpenCommotion Closeout Plan

Last updated: 2026-02-24

## Goal

Ship OpenCommotion from scaffold/demo to release-candidate quality with:
- Production-capable local voice loop (STT + TTS + UI playback/record path)
- Protocol-enforced gateway/orchestrator/event contracts
- Patch-driven real-time UI runtime
- Semantic artifact recall
- Full system E2E, security/perf gates, and release docs

## Definition of Complete

Implementation is considered complete only when all of the following are true:
- Typed and voice turns both work end-to-end through gateway, orchestrator, brush compile, UI, and artifact memory.
- Gateway rejects invalid payloads via schema validation and returns stable error envelopes.
- UI stage applies incoming patches from realtime events, not static placeholder scene primitives.
- Artifact recall supports lexical plus embedding similarity and deterministic recall ranking.
- CI gates pass for backend tests, UI tests, browser E2E, schema validation, and baseline perf/security checks.
- Release runbook exists and a fresh machine can run setup, dev, test, and demo paths without manual debugging.

## Critical Path

1. Protocol validation and event envelope stabilization.
2. Production STT/TTS pipeline with timing metadata.
3. Patch-driven UI runtime connected to websocket stream.
4. Semantic artifact indexing and recall ranking.
5. True browser E2E and release-quality gates.

## Timeline

## Phase 0: Alignment and Freeze (2026-02-24 to 2026-02-25)
- Freeze schema versions for closeout scope.
- Create feature branches per skill scaffold.
- Confirm local engine selections for STT/TTS and embedding backend.
- Lock acceptance criteria for all workstreams.

## Phase 1: Core Runtime Completion (2026-02-25 to 2026-02-28)
- Implement schema validation at gateway ingress/egress.
- Replace placeholder STT/TTS workers with local production engines.
- Add gateway voice endpoints and orchestrator timeline metadata.

## Phase 2: UI + Memory Completion (2026-03-01 to 2026-03-04)
- Replace static stage with patch applier runtime.
- Add websocket session subscription and timeline playback controls.
- Add embedding index and semantic recall API path.

## Phase 3: Quality Gates (2026-03-05 to 2026-03-07)
- Add browser E2E tests for typed + voice + artifact recall loop.
- Add perf smoke thresholds and security checks into CI.
- Run hardening and bugfix loop.

## Phase 4: Release Candidate (2026-03-08)
- Final docs + runbook + architecture updates.
- Tag release candidate and publish demo script.

## Workstream Ownership

- `platform-protocol`: schema freeze, versioning, validators
- `api-gateway`: ingress validation, error envelopes, voice endpoints
- `services-orchestrator`: multi-channel timeline merge and event composition
- `voice-stt`: local STT implementation + streaming partial/final states
- `voice-tts`: local TTS generation + timing marks
- `ui-runtime`: patch applier and websocket-driven stage
- `ui-motion`: timeline sync, transitions, playback UX
- `artifact-registry`: embedding index + semantic retrieval
- `brush-engine`: patch determinism and additional intent coverage
- `qa-security-perf`: browser E2E, perf budgets, security checks
- `docs-oss`: release runbook, contributor and operator docs
- `lead-orchestrator`: dependency tracking and merge gate enforcement

## Merge Gates

All streams must meet these required gates before closeout:
- `tests_pass`: `make test-all` and browser E2E suite green
- `schema_validation_pass`: strict schema checks in gateway/orchestrator
- `security_checks_pass`: dependency audit + baseline API hardening checks
- `performance_thresholds_pass`: median turn latency and UI patch-apply time within target

## Execution Rhythm

- Daily: each stream updates status and blocker list in runtime agent-run files.
- Every 48h: integration checkpoint branch merged behind feature flags if needed.
- End of each phase: run full CI + manual demo script on clean environment.

## Skill Scaffolds

Execution scaffolds are in `agents/scaffolds/`:
- `skill-voice-production.json`
- `skill-schema-validation.json`
- `skill-ui-patch-runtime.json`
- `skill-artifact-semantic-recall.json`
- `skill-e2e-realtime.json`
- `skill-security-ops.json`
- `skill-release-docs.json`

Use these files as the source of truth for each stream's scope, checklist, validation commands, and definition of done.
