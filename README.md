# OpenCommotion

OpenCommotion is an app for generating synchronized text, voice, and visual animation from prompts.

## Start Here

Prereqs:
- Python 3.11+
- Node.js 20+
- npm

Install and run:

```bash
python3 scripts/opencommotion.py install
python3 scripts/opencommotion.py setup
python3 scripts/opencommotion.py run
```

Open:
- App UI: http://127.0.0.1:8000

Stop:

```bash
python3 scripts/opencommotion.py down
```

## Use The App

1. Open **Setup Wizard**.
2. Pick your LLM provider and voice policy.
3. Click **Validate Setup**, then **Save Setup**.
4. Enter a prompt and click **Run Turn**.
5. Watch text + voice + animation playback in sync.
6. Save useful outputs as artifacts.
7. Use **Agent Run Manager** for autonomous queues (`run_once|pause|resume|stop|drain`).

## Daily Workflow

Start app:

```bash
python3 scripts/opencommotion.py run
```

Check status:

```bash
python3 scripts/opencommotion.py status
```

Stop app:

```bash
python3 scripts/opencommotion.py down
```

## Connect Agents (Python)

Robust default client:

```bash
. .venv/bin/activate
python3 scripts/agent_examples/robust_turn_client.py \
  --session demo-1 \
  --prompt "moonwalk adoption chart with synchronized narration"
```

Codex/OpenClaw examples:

```bash
. .venv/bin/activate
python3 scripts/agent_examples/codex_cli_turn_client.py
python3 scripts/agent_examples/openclaw_cli_turn_client.py
python3 scripts/agent_examples/openclaw_openai_turn_client.py --base-url http://127.0.0.1:8002/v1
```

REST + websocket example:

```bash
. .venv/bin/activate
python3 scripts/agent_examples/rest_ws_agent_client.py \
  --session demo-2 \
  --prompt "ufo landing with pie chart"
```

## Defaults You Should Know

Auth defaults:
- `OPENCOMMOTION_AUTH_MODE=api-key`
- `OPENCOMMOTION_API_KEYS=dev-opencommotion-key`

Client auth:
- HTTP header: `x-api-key: <key>`
- WebSocket: `ws://127.0.0.1:8000/v1/events/ws?api_key=<key>`

LLM provider values:
- `heuristic|ollama|openai-compatible|codex-cli|openclaw-cli|openclaw-openai`

Voice engines:
- STT: `auto|faster-whisper|vosk|openai-compatible|text-fallback`
- TTS: `auto|piper|espeak|openai-compatible|tone-fallback`

## Health And Diagnostics

```bash
python3 scripts/opencommotion.py status
python3 scripts/opencommotion.py preflight
python3 scripts/opencommotion.py doctor
```

## API Surface

- `GET /v1/setup/state`
- `POST /v1/setup/validate`
- `POST /v1/setup/state`
- `POST /v1/agent-runs`
- `GET /v1/agent-runs`
- `GET /v1/agent-runs/{run_id}`
- `POST /v1/agent-runs/{run_id}/enqueue`
- `POST /v1/agent-runs/{run_id}/control`

WebSocket run events:
- `agent.run.state`
- `agent.turn.started`
- `agent.turn.completed`
- `agent.turn.failed`

## Production Deployment

Use:
- `docker-compose.prod.yml`
- `docker/Dockerfile.gateway`
- `docker/Dockerfile.orchestrator`
- `deploy/nginx/opencommotion.conf`
- `deploy/prometheus/*`
- `deploy/grafana/*`

Deploy steps:
1. Copy `.env.example` to `.env` and set production values.
2. Put TLS certs in `deploy/nginx/certs/` (`fullchain.pem`, `privkey.pem`).
3. Run `docker compose -f docker-compose.prod.yml up -d --build`.

## Backup And Restore

```bash
bash scripts/backup_runtime.sh
bash scripts/restore_runtime.sh <backup-tar.gz>
```

Backs up:
- `data/artifacts/artifacts.db`
- `data/artifacts/bundles/`
- `runtime/agent-runs/agent_manager.db`

## Test Gates

```bash
python3 scripts/opencommotion.py test
python3 scripts/opencommotion.py test-ui
python3 scripts/opencommotion.py test-e2e
python3 scripts/opencommotion.py test-complete
python3 scripts/opencommotion.py fresh-agent-e2e
```

## Customization

- Gateway APIs and run manager: `services/gateway/app/main.py`
- Orchestrator: `services/orchestrator/app/main.py`
- LLM adapters: `services/agents/text/adapters.py`
- Voice engines: `services/agents/voice/stt/worker.py`, `services/agents/voice/tts/worker.py`
- UI runtime and wizard: `apps/ui/src/App.tsx`

## More Docs

- `docs/AGENT_CONNECTION.md`
- `docs/USAGE_PATTERNS.md`
- `docs/ARCHITECTURE.md`
- `PROJECT.md`
- `RELEASE.md`
