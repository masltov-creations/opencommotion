# OpenCommotion

OpenCommotion is a local-first visual orchestration app: one prompt in, synchronized text + voice + visual patches out.
And now for something completely practical.

## Use It In Practice

### 1) First-time setup (guided)

Prereqs:
- Python 3.11+

```bash
python3 scripts/opencommotion.py install
python3 scripts/opencommotion.py setup
```

The wizard configures your LLM/STT/TTS stack in `.env`.
No shrubbery required.

### 2) Start and open the app

```bash
python3 scripts/opencommotion.py run
```

Open:
- UI: `http://127.0.0.1:8000`
- Gateway docs: `http://127.0.0.1:8000/docs`
- Orchestrator docs: `http://127.0.0.1:8001/docs`

In the UI, check **Setup Status**. It shows runtime readiness from:
- `GET /v1/runtime/capabilities`

For contributor mode with hot-reload UI, install Node.js 20+ and use `python3 scripts/opencommotion.py dev` (UI at `http://127.0.0.1:5173`).

### 3) Run a turn

In UI:
1. Enter prompt.
2. Click `Run Turn`.
3. Optional: upload audio and click `Transcribe Audio`.
4. Optional: save/search artifacts.

Expected:
- text response
- voice segment with `audio_uri`
- visual patches applied and animated timeline
- no dead parrots in the response path

### 4) Use as an agent/client

Recommended robust client:

```bash
source .venv/bin/activate
python scripts/agent_examples/robust_turn_client.py \
  --session first-run \
  --prompt "moonwalk adoption chart with synchronized narration" \
  --search onboarding
```

Alternative minimal client:

```bash
source .venv/bin/activate
python scripts/agent_examples/rest_ws_agent_client.py \
  --session baseline-demo-1 \
  --prompt "ufo landing with pie chart"
```

### 5) Stop

```bash
python3 scripts/opencommotion.py down
```

## Smart Defaults (Open Source)

Recommended defaults for quality + practicality:
- LLM: `ollama` + `qwen2.5:7b-instruct`
- STT: `faster-whisper` (`small.en`, `int8`)
- TTS: `piper` if model is available, else `espeak`

Useful alternatives:
- LLM: openai-compatible local servers (`llama.cpp`, `vLLM`, `LocalAI`)
- STT: `vosk` (lighter, fully offline)
- TTS: `espeak`/`espeak-ng` (fast setup fallback)

Preflight checks:

```bash
python3 scripts/opencommotion.py preflight
curl -sS http://127.0.0.1:8000/v1/runtime/capabilities
```

## Core Endpoints

- `POST /v1/orchestrate`
- `POST /v1/brush/compile`
- `POST /v1/voice/transcribe`
- `POST /v1/voice/synthesize`
- `GET /v1/voice/capabilities`
- `GET /v1/runtime/capabilities`
- `POST /v1/artifacts/save`
- `GET /v1/artifacts/search`
- `WS /v1/events/ws`

## Validate It Works

Fast smoke:

```bash
python3 scripts/opencommotion.py run
source .venv/bin/activate
curl -sS http://127.0.0.1:8000/health
curl -sS http://127.0.0.1:8001/health
python scripts/agent_examples/robust_turn_client.py --session smoke --prompt "quick onboarding verification turn"
python3 scripts/opencommotion.py down
```

If a health check fails, it is not just a flesh wound. Check `runtime/logs/` and rerun.

Full gates:

```bash
make test-complete
make fresh-agent-e2e
```

## Customize And Extend

If you want to tailor providers, policies, or internal behavior, start here.
You are now entering the Ministry of Silly Configs (but with sane defaults).

### LLM provider config

- `OPENCOMMOTION_LLM_PROVIDER`: `ollama`, `openai-compatible`, `heuristic`
- `OPENCOMMOTION_LLM_MODEL`
- `OPENCOMMOTION_LLM_ALLOW_FALLBACK`
- `OPENCOMMOTION_OLLAMA_URL`
- `OPENCOMMOTION_OPENAI_BASE_URL`
- `OPENCOMMOTION_OPENAI_API_KEY`

### Voice engine config

- `OPENCOMMOTION_STT_ENGINE`: `auto`, `faster-whisper`, `vosk`, `text-fallback`
- `OPENCOMMOTION_TTS_ENGINE`: `auto`, `piper`, `espeak`, `tone-fallback`
- `OPENCOMMOTION_VOICE_REQUIRE_REAL_ENGINES=true` for strict production mode

When strict mode is on, voice/turn requests fail with `503` if fallback-only.

### Extend behavior

- Text generation: `services/agents/text/worker.py`
- Voice STT/TTS workers: `services/agents/voice/*`
- Orchestration flow: `services/orchestrator/app/main.py`
- API surface: `services/gateway/app/main.py`
- UI runtime: `apps/ui/src/App.tsx`, `apps/ui/src/runtime/sceneRuntime.ts`

### Multi-agent coordination

```bash
python3 scripts/spawn_expert_agents.py
python3 scripts/init_wave_context.py --run-id main-wave-01
```

Artifacts are written under `runtime/agent-runs/`.

### Contributor/dev mode

If you are changing UI/runtime code and want hot reload:
1. Install Node.js 20+ and npm.
2. Run `npm install`.
3. Run `python3 scripts/opencommotion.py dev`.
4. Open `http://127.0.0.1:5173`.

### Makefile (optional)

If you have `make` installed, all commands above are also available as make targets (`make install`, `make run`, etc.).

## Docs

- Practical integration guide: `docs/AGENT_CONNECTION.md`
- Runtime usage patterns: `docs/USAGE_PATTERNS.md`
- Architecture: `docs/ARCHITECTURE.md`
- Active plan/status: `PROJECT.md`
- Release runbook: `RELEASE.md`
- Contributing: `CONTRIBUTING.md`
