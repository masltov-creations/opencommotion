# OpenCommotion Usage Patterns

This document defines a simple, robust end-to-end usage pattern for:
- Agent clients (Codex/Claude/custom workers)
- Consumer clients (UI/mobile/web app consumers)

Use this as the default integration design.

## 1) Design goals

- Keep the first integration under 30 minutes.
- Keep runtime behavior deterministic for visual patch playback.
- Keep client logic resilient under disconnects and transient service failures.
- Keep interfaces stable and easy to reason about.

## 2) Canonical architecture pattern

Use a two-channel model for all clients:
- Command channel (REST): submit actions and receive immediate response.
- Event channel (WebSocket): subscribe to authoritative realtime event envelopes.

Required endpoints:
- `POST /v1/orchestrate`
- `POST /v1/brush/compile`
- `POST /v1/voice/transcribe`
- `POST /v1/voice/synthesize`
- `GET /v1/voice/capabilities`
- `GET /v1/runtime/capabilities`
- `POST /v1/artifacts/save`
- `GET /v1/artifacts/search`
- `POST /v1/artifacts/recall/{artifact_id}`
- `POST /v1/artifacts/pin/{artifact_id}`
- `POST /v1/artifacts/archive/{artifact_id}`
- `WS /v1/events/ws`

## 3) Quick-start lane (agents)

1. Check `GET /health` on gateway and orchestrator.
2. Check `GET /v1/runtime/capabilities` before first turn to confirm LLM/STT/TTS readiness.
3. Open websocket and send heartbeat `ping` every 10s.
4. Submit `POST /v1/orchestrate` with `session_id` + prompt.
5. Correlate websocket events by `session_id + turn_id`.
6. Execute output:
- read `payload.text`
- render `payload.visual_patches` by `at_ms`
- play `payload.voice.segments[*].audio_uri`
7. Optionally save and search artifacts.

Recommended script:
- `scripts/agent_examples/robust_turn_client.py`

## 4) Quick-start lane (consumers)

1. Create/restore a persistent `session_id` per user journey.
2. Keep one websocket open per active session view.
3. On submit, optimistically show pending state until REST returns.
4. Prefer websocket event for final render synchronization.
5. If websocket event is late/missing, fallback to REST response payload.
6. Allow replay by applying patches from `at_ms=0` to target time.

UI state machine:
- `idle`
- `running`
- `syncing_event`
- `ready`
- `error`

## 5) Robust defaults

Use these defaults unless you have stricter requirements:
- Health-check timeout: 2s
- Orchestrate timeout: 30s
- Websocket heartbeat interval: 10s
- Websocket receive timeout for correlated turn event: 20s
- REST retry attempts (network/5xx): 3
- Retry backoff: 0.6s, 1.2s, 2.4s
- Artifact search mode default: `hybrid`

## 6) Reliability rules

- Use `session_id + turn_id` as dedupe key for event processing.
- Do not apply the same turn twice.
- Keep patch application deterministic by sorting on `at_ms`.
- Treat websocket as source of timing truth when available.
- If websocket misses a turn event, use REST payload and continue.

## 7) Error-handling matrix

- REST `4xx`:
  - Do not auto-retry.
  - Surface error and request correction.
- REST `5xx`:
  - Retry up to configured attempts.
- Websocket disconnect:
  - Reconnect with backoff.
  - Resume and dedupe by `session_id + turn_id`.
- Voice synthesis/transcribe failure:
  - If strict voice mode is enabled, treat `503` as deployment/config failure and halt.
  - If strict mode is disabled, continue text+visual turn and mark voice state degraded.
- Schema validation failure:
  - Treat as contract bug.
  - Log payload + schema path and halt processing for that request.

## 8) Draw/animate strategy

Choose mode per use case:
- `orchestrate` mode: best for natural-language, low-effort generation.
- `brush/compile` mode: best for deterministic authored animation sequences.

When using `brush/compile`:
- always include `stroke_id`, `kind`, `params`, `timing`
- validate kinds against protocol list
- keep `at_ms` scheduling monotonic where possible

## 9) Artifact strategy

- Save noteworthy turns immediately after completion.
- For recall UX, default to `mode=hybrid`.
- Use `semantic` mode when query intent is conceptual (no exact title/tag expected).
- Use pin/archive to curate signal over time.

## 10) Consumer and agent onboarding checklist

- Stack starts with `python3 scripts/opencommotion.py run` (or `python3 scripts/opencommotion.py dev` for contributor hot reload).
- Health checks pass.
- Run one typed turn and verify render output.
- Run one voice synth call and verify audio URI playback.
- Run one artifact save/search/recall cycle.
- Simulate one websocket reconnect and confirm recovery.
- Run quality gates (`make test-complete`).
- Run fresh consumer agent proof (`make fresh-agent-e2e`).
- Run voice preflight (`make voice-preflight`).

## 11) Minimal run commands

```bash
python3 scripts/opencommotion.py run
. .venv/bin/activate
python scripts/agent_examples/robust_turn_client.py --session demo-1 --prompt "moonwalk adoption chart"
python3 scripts/opencommotion.py down
```

## 12) Multi-agent execution mode (implementation waves)

When multiple specialist agents are active, use one shared operating model:
1. Publish one wave context packet (objective, scope, constraints, gates).
2. Assign lane ownership from `agents/*.json` and keep one writer per lane.
3. Execute scaffolds in `agents/scaffolds/INDEX.md` order.
4. Use checkpoint cadence: start-of-wave, mid-wave, pre-merge, post-merge.
5. Merge only with evidence from tests, contracts, and docs updates.

Reference details:
- `docs/AGENT_CONNECTION.md` sections 12-15
- `agents/scaffolds/skill-agent-orchestration-ops.json`
- `agents/scaffolds/templates/wave-context.example.json`
- `agents/scaffolds/templates/lane-ownership.example.json`
- `agents/scaffolds/templates/handoff-report.example.md`
