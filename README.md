# OpenCommotion

OpenCommotion is a local-first visual orchestration app: one prompt in, synchronized text + voice + visual patches out.

## Use It In Practice

### 1) First-time setup (guided)

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
make setup-wizard
```

The wizard configures your LLM/STT/TTS stack in `.env`.

### 2) Start and open the app

```bash
make dev
```

Open:
- UI: `http://127.0.0.1:5173`
- Gateway docs: `http://127.0.0.1:8000/docs`
- Orchestrator docs: `http://127.0.0.1:8001/docs`

In the UI, check **Setup Status**. It shows runtime readiness from:
- `GET /v1/runtime/capabilities`

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
make down
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
make voice-preflight
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
make dev
source .venv/bin/activate
curl -sS http://127.0.0.1:8000/health
curl -sS http://127.0.0.1:8001/health
python scripts/agent_examples/robust_turn_client.py --session smoke --prompt "quick onboarding verification turn"
make down
```

Full gates:

```bash
make test-complete
make fresh-agent-e2e
```

## Customize And Extend

If you want to tailor providers, policies, or internal behavior, start here.

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

## Docs

- Practical integration guide: `docs/AGENT_CONNECTION.md`
- Runtime usage patterns: `docs/USAGE_PATTERNS.md`
- Architecture: `docs/ARCHITECTURE.md`
- Active plan/status: `PROJECT.md`
- Release runbook: `RELEASE.md`
- Contributing: `CONTRIBUTING.md`
